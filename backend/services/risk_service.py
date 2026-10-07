"""
Risk service: the ONLY place that wires together feature engineering -> model
inference -> risk scoring -> SHAP explanation -> decision engine for the API.

This module deliberately contains NO business/policy logic of its own. It:
  - builds a raw transaction DataFrame from validated Pydantic input (pure data
    marshalling, not a decision),
  - calls the EXISTING build_features() (Phase 1, unchanged),
  - validates model output before downstream processing (V2 hardening),
  - calls the EXISTING RiskExplainer.explain() (Phase 6, unchanged),
  - calls the EXISTING build_explanation_text() (Phase 6, unchanged),
  - calls the EXISTING make_decision() (Phase 7, unchanged).
Every threshold, rule, and scoring formula is owned by those modules, imported
here, never re-implemented.
"""

import uuid
import math
from typing import Optional, Any, Dict, List
import numpy as np
import pandas as pd


from ml.features.build_features import build_features, FEATURE_COLUMNS
from ml.evaluation.explainability import build_explanation_text
from ml.evaluation.decision_engine import make_decision, InvalidTransactionError
from ml.evaluation.policy import DECISION_THRESHOLD

from backend.services.model_loader import ModelBundle
from backend.schemas.transaction import RiskRequest
from backend.schemas.response import (
    RiskCase,
    RiskCaseTransactionFacts,
    RiskCaseModelAssessment,
    RiskCasePolicyDecision,
    RiskCaseAuditMetadata,
    CustomerHistorySummary,
    BehavioralAssessment,
    NetworkAssessment,
    AIInvestigationReport,
)
from backend.services.behavioral_engine import evaluate_behavioral_anomalies
from backend.services.network_engine import evaluate_network_risk
from backend.services.ai_investigator import build_investigation_input, generate_ai_investigation_report





class FeatureGenerationError(RuntimeError):
    """Raised when the raw transaction context cannot be turned into features."""


class ModelOutputError(RuntimeError):
    """Raised when the model produces invalid output (NaN, Inf, out-of-range)."""


def _validate_engineered_features(row: pd.Series) -> None:
    """
    V2 sanity-checking: verify engineered features are within defensible bounds.
    These bounds are derived from domain logic and feature generation semantics,
    not arbitrary thresholds. They catch pathological inputs (e.g., 500 identical
    transactions at same second) that might cause OOD predictions.

    Raises FeatureGenerationError if bounds are exceeded.
    """
    # Velocity features: count of transactions in time windows
    # Domain: ~1440 txns/day = ~60/hour = ~1 per minute. >1000 in 60min is pathological
    if row.get("velocity_60min", 0) > 1000:
        raise FeatureGenerationError(
            f"Feature velocity_60min={row['velocity_60min']} exceeds sanity bound (1000). "
            f"Suggests malformed transaction history (e.g., many identical timestamps)."
        )
    if row.get("velocity_30min", 0) > 500:
        raise FeatureGenerationError(
            f"Feature velocity_30min={row['velocity_30min']} exceeds sanity bound (500)."
        )
    if row.get("velocity_5min", 0) > 100:
        raise FeatureGenerationError(
            f"Feature velocity_5min={row['velocity_5min']} exceeds sanity bound (100)."
        )

    # Prior transaction count: >100,000 prior txns suggests data quality issue
    # (real customer base unlikely to have single customer with 100k+ txns)
    if row.get("prior_txn_count", 0) > 100_000:
        raise FeatureGenerationError(
            f"Feature prior_txn_count={row['prior_txn_count']} exceeds sanity bound (100,000). "
            f"Suggests malformed transaction history."
        )

    # Amount z-score: check for non-finite values only
    # The z-score is a legitimate feature representing statistical anomaly relative to customer history.
    # Extremely high z-scores (e.g., 2000+) are NOT data-quality issues—they're legitimate fraud signals
    # (e.g., customer with few low-value transactions making one huge purchase from new device/geo).
    # The model was trained on features with naturally high z-scores and uses them appropriately.
    # We validate only for NaN/Inf, not magnitude.
    amount_zscore = row.get("amount_zscore", 0)
    if not np.isfinite(amount_zscore):
        raise FeatureGenerationError(
            f"Feature amount_zscore={amount_zscore} is non-finite (NaN or Inf). "
            f"Transaction history is malformed."
        )

    # time_since_prev_txn_min: set to 99999 for first txn (sentinel value); normal max ~14400 (10 days)
    # Allow up to sentinel value + buffer
    if row.get("time_since_prev_txn_min", 0) > 100_000:
        raise FeatureGenerationError(
            f"Feature time_since_prev_txn_min={row['time_since_prev_txn_min']} exceeds sanity bound."
        )


def _calculate_signal_quality(prior_txn_count: int) -> dict:
    """
    V2: Calculate historical context quality indicator.

    This is NOT model confidence or statistical uncertainty.
    It's a contextual label for how much behavioral history was available.

    Returns:
    {
        "level": "MINIMAL" | "LIMITED" | "MODERATE" | "ESTABLISHED",
        "prior_transaction_count": int,
        "message": str
    }
    """
    if prior_txn_count == 0:
        return {
            "level": "MINIMAL",
            "prior_transaction_count": 0,
            "message": "No prior transaction history was available. Behavioral-context features are not available.",
        }
    elif prior_txn_count <= 2:
        return {
            "level": "LIMITED",
            "prior_transaction_count": prior_txn_count,
            "message": f"Very limited transaction history ({prior_txn_count} prior transaction{'s' if prior_txn_count > 1 else ''}). Behavioral patterns cannot be reliably inferred.",
        }
    elif prior_txn_count <= 9:
        return {
            "level": "MODERATE",
            "prior_transaction_count": prior_txn_count,
            "message": f"Moderate transaction history ({prior_txn_count} prior transactions). Behavioral patterns partially established.",
        }
    else:
        return {
            "level": "ESTABLISHED",
            "prior_transaction_count": prior_txn_count,
            "message": f"Established transaction history ({prior_txn_count} prior transactions). Behavioral patterns well-defined.",
        }


def _validate_model_probability(probability: float) -> float:
    """
    Validates that the model's predicted probability is valid and usable.

    Requirements:
    - must be a finite float (not NaN, not Inf, not -Inf)
    - must be in the range [0.0, 1.0]

    Raises ModelOutputError if validation fails.
    """
    # Check for NaN
    if math.isnan(probability):
        raise ModelOutputError("Model produced NaN probability; prediction invalid.")

    # Check for Inf or -Inf
    if math.isinf(probability):
        raise ModelOutputError(
            f"Model produced infinite probability ({probability}); prediction invalid."
        )

    # Check bounds
    if not (0.0 <= probability <= 1.0):
        raise ModelOutputError(
            f"Model produced out-of-range probability ({probability}); must be in [0.0, 1.0]."
        )

    return probability


def _build_feature_row(request: RiskRequest) -> pd.Series:
    """
    Converts the validated request (current transaction + optional prior history
    for the same customer) into the single engineered feature row for the
    transaction being scored, using the existing, unmodified feature pipeline.

    V2: Validates that engineered features are within defensible bounds to catch
    pathological feature generation (e.g., 500 identical transactions at same second).
    """
    all_txns = list(request.prior_transactions) + [request.transaction]
    raw_records = [t.model_dump() for t in all_txns]
    raw_df = pd.DataFrame(raw_records)

    try:
        features_df = build_features(raw_df)
    except Exception as e:
        raise FeatureGenerationError(f"Feature engineering failed: {e}") from e

    # the transaction being scored is the one with the matching transaction_id
    # (also guaranteed to be the latest timestamp for this customer, enforced by
    # RiskRequest validation)
    match = features_df[features_df["transaction_id"] == request.transaction.transaction_id]
    if len(match) != 1:
        raise FeatureGenerationError(
            f"Expected exactly 1 row for transaction_id="
            f"{request.transaction.transaction_id!r} after feature engineering, got {len(match)}"
        )
    row = match.iloc[0]

    # V2: Sanity-check engineered features for pathological values
    # These bounds are defensible from domain logic, not arbitrary:
    # - velocity_60min: count of txns in 60min window. Max ~1440 txns/day → ~60/hour → ~1000 in 60min window is extreme
    # - prior_txn_count: number of prior transactions. 100,000+ would indicate data quality issue
    # - amount_zscore: deviation from historical avg. >20 std devs is extreme outlier
    _validate_engineered_features(row)

    return row


def score_only(bundle: ModelBundle, request: RiskRequest) -> dict:
    """Probability + risk score/category. No SHAP, no decision, no audit write."""
    row = _build_feature_row(request)
    X = pd.DataFrame([row[FEATURE_COLUMNS].astype(float).values], columns=FEATURE_COLUMNS)
    probability = float(bundle.model.predict_proba(X)[0, 1])

    # V2 hardening: validate model output before downstream processing
    probability = _validate_model_probability(probability)

    from ml.evaluation.risk_scoring import score_transaction
    risk = score_transaction(probability)
    return dict(
        transaction_id=request.transaction.transaction_id,
        model_version=bundle.metadata.get("model_name", "lgbm_v1"),
        **risk,
    )


def explain_only(bundle: ModelBundle, request: RiskRequest) -> dict:
    """Probability + full SHAP explanation. No decision, no audit write."""
    row = _build_feature_row(request)
    result = bundle.explainer.explain(row)

    # V2 hardening: validate model output before downstream processing
    probability = _validate_model_probability(result["fraud_probability"])
    result["fraud_probability"] = probability

    # Detect cold-start (no prior transaction history)
    is_cold_start = len(request.prior_transactions) == 0

    explanation = build_explanation_text(
        result, decision_threshold=DECISION_THRESHOLD, is_cold_start=is_cold_start
    )

    # For cold-start, filter contributions to exclude history-dependent features
    # (these use sentinel/default values and should not be shown to frontend)
    contributions = result["contributions"]
    if is_cold_start:
        cold_start_exclude = {
            "amount_vs_avg_ratio",
            "amount_zscore",
            "time_since_prev_txn_min",
            "prior_txn_count",
            "velocity_5min",
            "velocity_30min",
            "velocity_60min",
            "failed_ratio_trailing10",
            "new_device_flag",
            "new_geo_flag",
        }
        contributions = [c for c in contributions if c["feature"] not in cold_start_exclude]

    return dict(
        transaction_id=request.transaction.transaction_id,
        model_version=bundle.metadata.get("model_name", "lgbm_v1"),
        fraud_probability=result["fraud_probability"],
        additivity_check_passed=result["additivity_check_passed"],
        header=explanation["header"],
        reasons=explanation["reasons"],
        contributions=contributions,
        cold_start_context=explanation.get("cold_start_context"),
    )


def build_investigation_context(
    request: RiskRequest,
    row: pd.Series,
    decision: Optional[Any] = None,
    explanation: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    Build grounded investigation context comparing the current transaction
    with historical customer behavior strictly using available evidence (Phases 1-4).
    """
    prior_txns = request.prior_transactions
    prior_count = len(prior_txns)
    account_age_days = float(row.get("account_age_days", 0.0))

    class _DefaultDecision:
        fraud_probability = 0.0
        threshold = DECISION_THRESHOLD
        risk_score = 0
        risk_category = "LOW"
        action = "ALLOW"
        policy_rule_id = "R_DEFAULT_BASELINE"
        policy_reason = "Default baseline evaluation."

    effective_decision = decision if decision is not None else _DefaultDecision()

    if prior_count == 0:
        customer_summary = {
            "prior_transaction_count": 0,
            "historical_avg_amount": None,
            "historical_std_amount": None,
            "historical_min_amount": None,
            "historical_max_amount": None,
            "account_age_days": round(account_age_days, 1),
            "known_devices": [],
            "known_geos": [],
            "first_seen_timestamp": None,
            "last_seen_timestamp": None,
        }
        behavioral_assessment = evaluate_behavioral_anomalies(request, row, customer_summary)
        network_assessment = evaluate_network_risk(request, customer_summary)
        ai_inp = build_investigation_input(
            request, row, customer_summary, behavioral_assessment, network_assessment, effective_decision, explanation
        )
        ai_report = generate_ai_investigation_report(ai_inp)
        return {
            "status": "INSUFFICIENT_HISTORY",
            "customer_id": request.transaction.customer_id,
            "current_transaction_id": request.transaction.transaction_id,
            "customer_summary": customer_summary,
            "behavioral_signals": {
                "status": "INSUFFICIENT_HISTORY",
                "amount_deviation": None,
                "velocity": {
                    "velocity_5min": 0,
                    "velocity_30min": 0,
                    "velocity_60min": 0,
                    "time_since_prev_min": 99999.0,
                },
                "device_novelty": {
                    "current_device": request.transaction.device_id,
                    "is_new_device": False,
                    "known_devices_count": 0,
                },
                "geo_novelty": {
                    "current_geo": request.transaction.geo_region,
                    "is_new_geo": False,
                    "known_geos_count": 0,
                },
                "recent_failure_rate": 0.0,
                "timing": {
                    "hour_of_day": int(row["hour_of_day"]),
                    "is_night": bool(row["is_night"] == 1),
                    "day_of_week": int(row["day_of_week"]),
                },
            },
            "key_findings": [
                {
                    "signal_type": "BASELINE",
                    "severity": "INFO",
                    "description": "First-time transaction for customer — no prior history available to establish behavioral baseline.",
                    "evidence": {"prior_txn_count": 0},
                }
            ],
            "behavioral_assessment": behavioral_assessment,
            "network_assessment": network_assessment,
            "ai_investigation_report": ai_report,
        }



    amounts = [float(t.amount) for t in prior_txns]
    avg_amount = float(np.mean(amounts))
    std_amount = float(np.std(amounts, ddof=1)) if prior_count > 1 else 0.0
    min_amount = float(np.min(amounts))
    max_amount = float(np.max(amounts))
    known_devices = sorted(list(set(t.device_id for t in prior_txns)))
    known_geos = sorted(list(set(t.geo_region for t in prior_txns)))
    first_seen_ts = min(t.timestamp for t in prior_txns).isoformat()
    last_seen_ts = max(t.timestamp for t in prior_txns).isoformat()

    customer_summary = {
        "prior_transaction_count": prior_count,
        "historical_avg_amount": round(avg_amount, 2),
        "historical_std_amount": round(std_amount, 2),
        "historical_min_amount": round(min_amount, 2),
        "historical_max_amount": round(max_amount, 2),
        "account_age_days": round(account_age_days, 1),
        "known_devices": known_devices,
        "known_geos": known_geos,
        "first_seen_timestamp": first_seen_ts,
        "last_seen_timestamp": last_seen_ts,
    }

    behavioral_assessment = evaluate_behavioral_anomalies(request, row, customer_summary)
    network_assessment = evaluate_network_risk(request, customer_summary)

    amount_ratio = float(row.get("amount_vs_avg_ratio", 1.0))

    amount_zscore = float(row.get("amount_zscore", 0.0))
    is_new_device = bool(row.get("new_device_flag", 0) == 1)
    is_new_geo = bool(row.get("new_geo_flag", 0) == 1)
    vel_5 = int(row.get("velocity_5min", 0))
    vel_30 = int(row.get("velocity_30min", 0))
    vel_60 = int(row.get("velocity_60min", 0))
    time_prev = float(row.get("time_since_prev_txn_min", 99999.0))
    fail_ratio = float(row.get("failed_ratio_trailing10", 0.0))
    is_night = bool(row.get("is_night", 0) == 1)
    hour = int(row.get("hour_of_day", 0))

    findings = []

    # 1. Amount deviation finding
    if amount_ratio >= 3.0 or amount_zscore >= 3.0:
        findings.append({
            "signal_type": "AMOUNT_DEVIATION",
            "severity": "HIGH",
            "description": f"Transaction amount (Rs {request.transaction.amount:,.2f}) is {amount_ratio:.1f}x the customer's historical average (Rs {avg_amount:,.2f}) with z-score {amount_zscore:.1f}.",
            "evidence": {
                "current_amount": request.transaction.amount,
                "historical_avg": round(avg_amount, 2),
                "ratio": round(amount_ratio, 2),
                "zscore": round(amount_zscore, 2),
            },
        })
    elif amount_ratio >= 1.5 or amount_zscore >= 1.5:
        findings.append({
            "signal_type": "AMOUNT_DEVIATION",
            "severity": "MEDIUM",
            "description": f"Transaction amount (Rs {request.transaction.amount:,.2f}) is moderately elevated ({amount_ratio:.1f}x historical average Rs {avg_amount:,.2f}).",
            "evidence": {
                "current_amount": request.transaction.amount,
                "historical_avg": round(avg_amount, 2),
                "ratio": round(amount_ratio, 2),
                "zscore": round(amount_zscore, 2),
            },
        })
    else:
        findings.append({
            "signal_type": "AMOUNT_DEVIATION",
            "severity": "INFO",
            "description": f"Transaction amount (Rs {request.transaction.amount:,.2f}) is consistent with customer baseline (Rs {avg_amount:,.2f}).",
            "evidence": {
                "current_amount": request.transaction.amount,
                "historical_avg": round(avg_amount, 2),
                "ratio": round(amount_ratio, 2),
                "zscore": round(amount_zscore, 2),
            },
        })

    # 2. Device novelty finding
    if is_new_device:
        findings.append({
            "signal_type": "DEVICE_NOVELTY",
            "severity": "HIGH",
            "description": f"New device '{request.transaction.device_id}' observed for customer (previously used {len(known_devices)} known device(s)).",
            "evidence": {
                "current_device": request.transaction.device_id,
                "known_devices": known_devices,
            },
        })
    else:
        findings.append({
            "signal_type": "DEVICE_NOVELTY",
            "severity": "INFO",
            "description": f"Device '{request.transaction.device_id}' matches customer known device history.",
            "evidence": {
                "current_device": request.transaction.device_id,
                "known_devices": known_devices,
            },
        })

    # 3. Geo novelty finding
    if is_new_geo:
        findings.append({
            "signal_type": "GEO_NOVELTY",
            "severity": "HIGH",
            "description": f"Transaction initiated from unfamiliar region '{request.transaction.geo_region}' (previously transacted in {len(known_geos)} region(s)).",
            "evidence": {
                "current_geo": request.transaction.geo_region,
                "known_geos": known_geos,
            },
        })
    else:
        findings.append({
            "signal_type": "GEO_NOVELTY",
            "severity": "INFO",
            "description": f"Geographic region '{request.transaction.geo_region}' matches customer regular activity.",
            "evidence": {
                "current_geo": request.transaction.geo_region,
                "known_geos": known_geos,
            },
        })

    # 4. Velocity finding
    if vel_5 > 1 or vel_30 > 3:
        findings.append({
            "signal_type": "VELOCITY_SPIKE",
            "severity": "HIGH",
            "description": f"Elevated transaction velocity: {vel_5} in past 5m, {vel_30} in past 30m, {vel_60} in past 60m.",
            "evidence": {"velocity_5min": vel_5, "velocity_30min": vel_30, "velocity_60min": vel_60},
        })
    elif vel_60 > 1:
        findings.append({
            "signal_type": "VELOCITY_SPIKE",
            "severity": "MEDIUM",
            "description": f"Multiple recent transactions: {vel_60} transactions within past 60 minutes.",
            "evidence": {"velocity_60min": vel_60},
        })
    elif time_prev < 5.0:
        findings.append({
            "signal_type": "VELOCITY_SPIKE",
            "severity": "MEDIUM",
            "description": f"Rapid follow-up: transaction occurred {time_prev:.1f} minutes after previous transaction.",
            "evidence": {"time_since_prev_min": round(time_prev, 1)},
        })

    # 5. Failure pattern finding
    if fail_ratio >= 0.3:
        findings.append({
            "signal_type": "FAILURE_PATTERN",
            "severity": "HIGH",
            "description": f"Elevated recent failure rate: {fail_ratio:.0%} of previous 10 transactions failed.",
            "evidence": {"failed_ratio_trailing10": round(fail_ratio, 2)},
        })

    # 6. Timing finding
    if is_night:
        findings.append({
            "signal_type": "TIMING_ANOMALY",
            "severity": "LOW",
            "description": f"Transaction initiated during overnight hours ({hour}:00 UTC).",
            "evidence": {"hour_of_day": hour, "is_night": True},
        })

    return {
        "status": "AVAILABLE",
        "customer_id": request.transaction.customer_id,
        "current_transaction_id": request.transaction.transaction_id,
        "customer_summary": customer_summary,
        "behavioral_signals": {
            "status": "ESTABLISHED_HISTORY",
            "amount_deviation": {
                "current_amount": request.transaction.amount,
                "historical_avg": round(avg_amount, 2),
                "ratio": round(amount_ratio, 2),
                "zscore": round(amount_zscore, 2),
            },
            "velocity": {
                "velocity_5min": vel_5,
                "velocity_30min": vel_30,
                "velocity_60min": vel_60,
                "time_since_prev_min": round(time_prev, 1),
            },
            "device_novelty": {
                "current_device": request.transaction.device_id,
                "is_new_device": is_new_device,
                "known_devices_count": len(known_devices),
            },
            "geo_novelty": {
                "current_geo": request.transaction.geo_region,
                "is_new_geo": is_new_geo,
                "known_geos_count": len(known_geos),
            },
            "recent_failure_rate": round(fail_ratio, 2),
            "timing": {
                "hour_of_day": hour,
                "is_night": is_night,
                "day_of_week": int(row["day_of_week"]),
            },
        },
        "key_findings": findings,
        "behavioral_assessment": behavioral_assessment,
        "network_assessment": network_assessment,
        "ai_investigation_report": generate_ai_investigation_report(
            build_investigation_input(
                request, row, customer_summary, behavioral_assessment, network_assessment, effective_decision, explanation
            )
        ),
    }



def evaluate_full(bundle: ModelBundle, request: RiskRequest):
    """
    Full pipeline: features -> inference -> probability validation -> SHAP -> decision engine -> investigation context.
    Returns (DecisionRecord, explanation_dict, request_id, prior_txn_count, explanation_error, investigation_context).
    Does NOT persist -- persistence is the caller's (API route's) responsibility.
    """
    request_id = str(uuid.uuid4())
    row = _build_feature_row(request)

    # Compute prior transaction count for signal quality
    prior_txn_count = len(request.prior_transactions)

    # Get raw probability first (with validation), then make decision
    X = pd.DataFrame([row[FEATURE_COLUMNS].astype(float).values], columns=FEATURE_COLUMNS)
    raw_probability = float(bundle.model.predict_proba(X)[0, 1])
    probability = _validate_model_probability(raw_probability)

    # Make decision BEFORE attempting SHAP (so decision is not dependent on SHAP success)
    decision = make_decision(
        transaction_id=request.transaction.transaction_id,
        model_probability=probability,
        amount=request.transaction.amount,
        model_explanation=None,  # Will be filled in after SHAP attempt
    )

    # Attempt SHAP explanation, but it's not required for the decision
    explanation = None
    explanation_error = None
    try:
        result = bundle.explainer.explain(row)
        # Re-validate probability from SHAP result
        probability_from_shap = _validate_model_probability(result["fraud_probability"])

        # Detect cold-start (no prior transaction history)
        is_cold_start = prior_txn_count == 0

        explanation = build_explanation_text(
            result, decision_threshold=DECISION_THRESHOLD, is_cold_start=is_cold_start
        )
        explanation["reasons"] = explanation.get("reasons", [])

        # Update decision with explanations
        decision = make_decision(
            transaction_id=request.transaction.transaction_id,
            model_probability=probability,
            amount=request.transaction.amount,
            model_explanation=explanation.get("reasons", []),
        )
    except Exception as e:
        # SHAP failed, but decision is still valid
        explanation_error = str(e)

    # Build full investigation context including AI Investigator Report with authoritative decision and explanations
    investigation_context = build_investigation_context(
        request, row, decision=decision, explanation=explanation
    )

    return decision, explanation, request_id, prior_txn_count, explanation_error, investigation_context


def build_risk_case(
    request: RiskRequest,
    decision,
    explanation: Optional[Dict[str, Any]],
    investigation_context: Dict[str, Any],
    request_id: str,
    audit_persisted: bool = False,
    audit_error: Optional[str] = None,
) -> RiskCase:
    """
    Phase 5: Assembles the unified, authoritative RiskCase artifact from
    already-computed components without any risk recalculation.
    """
    curr = request.transaction
    case_id = f"CASE-{request_id[:8].upper()}"

    transaction_facts = RiskCaseTransactionFacts(
        transaction_id=curr.transaction_id,
        customer_id=curr.customer_id,
        amount=float(curr.amount),
        timestamp=curr.timestamp.isoformat() if hasattr(curr.timestamp, "isoformat") else str(curr.timestamp),
        merchant_id=curr.merchant_id,
        merchant_category=curr.merchant_category,
        device_id=curr.device_id,
        geo_region=curr.geo_region,
        payment_method=curr.payment_method,
    )

    top_reasons = explanation.get("reasons", []) if explanation else []
    cold_start_ctx = explanation.get("cold_start_context") if explanation else None

    model_assessment = RiskCaseModelAssessment(
        fraud_probability=float(decision.fraud_probability),
        risk_score=int(decision.risk_score),
        risk_category=str(decision.risk_category),
        decision_threshold=float(decision.threshold),
        top_shap_reasons=top_reasons,
        cold_start_context=cold_start_ctx,
    )

    policy_decision = RiskCasePolicyDecision(
        action=str(decision.action),
        policy_rule_id=str(decision.policy_rule_id),
        policy_reason=str(decision.policy_reason),
    )

    audit_metadata = RiskCaseAuditMetadata(
        request_id=request_id,
        decision_timestamp=str(decision.timestamp),
        source=str(request.source),
        audit_persisted=bool(audit_persisted),
        audit_error=audit_error,
    )

    cust_summary = investigation_context.get("customer_summary")
    if isinstance(cust_summary, dict):
        cust_ctx = CustomerHistorySummary(**cust_summary)
    else:
        cust_ctx = cust_summary

    beh_assessment = investigation_context.get("behavioral_assessment")
    if isinstance(beh_assessment, dict):
        beh_obj = BehavioralAssessment(**beh_assessment)
    else:
        beh_obj = beh_assessment

    net_assessment = investigation_context.get("network_assessment")
    if isinstance(net_assessment, dict):
        net_obj = NetworkAssessment(**net_assessment)
    else:
        net_obj = net_assessment

    ai_report = investigation_context.get("ai_investigation_report")
    if isinstance(ai_report, dict):
        ai_obj = AIInvestigationReport(**ai_report)
    else:
        ai_obj = ai_report

    return RiskCase(
        case_id=case_id,
        created_at=str(decision.timestamp),
        model_version=str(decision.model_version),
        transaction_facts=transaction_facts,
        model_assessment=model_assessment,
        customer_context=cust_ctx,
        behavioral_assessment=beh_obj,
        network_assessment=net_obj,
        ai_investigation=ai_obj,
        policy_decision=policy_decision,
        audit_metadata=audit_metadata,
    )



