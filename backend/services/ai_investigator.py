"""
AI Risk Investigator for RISKOVA AI (Phase 4).

PURPOSE:
Provides grounded, AI-assisted investigation synthesis explaining WHY a transaction
is risky, what behavioral and network evidence supports that conclusion, and what
mitigating facts exist.

CRITICAL ARCHITECTURAL BOUNDARY:
- The AI Investigator is an EXPLAINER / INVESTIGATION layer only.
- It is NOT the fraud model, NOT the decision engine, and NOT an autonomous controller.
- AI output NEVER changes model probability, SHAP values, risk scores, or policy actions (ALLOW/MONITOR/STEP_UP/BLOCK).
- The primary engine is a 100% deterministic, grounded synthesizer (zero external dependencies).
- An optional provider-agnostic HTTP adapter is supported with strict timeouts, JSON schema validation,
  and deterministic post-generation entity grounding verification.
"""

import os
import re
import json
import logging
from typing import Optional, List, Dict, Any, Set
import httpx

from backend.schemas.investigation import RiskInvestigationInput
from backend.schemas.response import AIInvestigationReport, RiskDriverItem

logger = logging.getLogger(__name__)


def build_investigation_input(
    request,
    row,
    customer_summary: Dict[str, Any],
    behavioral_assessment: Optional[Dict[str, Any]],
    network_assessment: Optional[Dict[str, Any]],
    decision,
    explanation: Optional[Dict[str, Any]],
) -> RiskInvestigationInput:
    """Builds the strictly grounded RiskInvestigationInput schema from evaluated components."""
    current_txn = request.transaction
    top_shap = explanation.get("reasons", []) if explanation else []
    cold_start_ctx = explanation.get("cold_start_context") if explanation else None

    beh_status = behavioral_assessment.get("overall_status", "NOMINAL") if behavioral_assessment else "NOMINAL"
    beh_anomalies = behavioral_assessment.get("anomalies", []) if behavioral_assessment else []

    net_status = network_assessment.get("overall_status", "ISOLATED_TRANSACTION") if network_assessment else "ISOLATED_TRANSACTION"
    net_links = network_assessment.get("links", []) if network_assessment else []

    return RiskInvestigationInput(
        transaction_id=current_txn.transaction_id,
        customer_id=current_txn.customer_id,
        amount=float(current_txn.amount),
        timestamp=current_txn.timestamp.isoformat() if hasattr(current_txn.timestamp, "isoformat") else str(current_txn.timestamp),
        merchant_id=current_txn.merchant_id,
        merchant_category=current_txn.merchant_category,
        device_id=current_txn.device_id,
        geo_region=current_txn.geo_region,
        payment_method=current_txn.payment_method,
        fraud_probability=float(decision.fraud_probability),
        decision_threshold=float(decision.threshold),
        risk_score=int(decision.risk_score),
        risk_category=str(decision.risk_category),
        top_shap_reasons=top_shap,
        cold_start_context=cold_start_ctx,
        prior_transaction_count=int(customer_summary.get("prior_transaction_count", 0)),
        historical_avg_amount=customer_summary.get("historical_avg_amount"),
        historical_max_amount=customer_summary.get("historical_max_amount"),
        account_age_days=float(customer_summary.get("account_age_days", 0.0)),
        known_devices_count=len(customer_summary.get("known_devices", [])),
        known_geos_count=len(customer_summary.get("known_geos", [])),
        behavioral_overall_status=beh_status,
        behavioral_anomalies=beh_anomalies,
        network_overall_status=net_status,
        network_links=net_links,
        recommended_action=str(decision.action),
        policy_rule_id=str(decision.policy_rule_id),
        policy_reason=str(decision.policy_reason),
    )


def deterministic_synthesizer(inp: RiskInvestigationInput) -> AIInvestigationReport:
    """
    Primary, zero-dependency, 100% grounded investigation report synthesizer.
    Translates structured facts into a balanced, clear analyst report.
    """
    is_cold_start = inp.prior_transaction_count == 0
    risk_drivers: List[RiskDriverItem] = []
    mitigating_factors: List[str] = []

    # 1. Harvest Risk Drivers from Behavioral Anomalies
    for a in inp.behavioral_anomalies:
        if a.get("is_anomaly") and a.get("severity") in ("CRITICAL", "HIGH", "MEDIUM"):
            risk_drivers.append(
                RiskDriverItem(
                    driver_type="BEHAVIORAL",
                    severity=a.get("severity", "MEDIUM"),
                    finding=a.get("description", ""),
                    supporting_evidence=a.get("observed_summary", ""),
                )
            )

    # 2. Harvest Risk Drivers from Network Links
    for l in inp.network_links:
        if l.get("severity") in ("CRITICAL", "HIGH", "MEDIUM"):
            risk_drivers.append(
                RiskDriverItem(
                    driver_type="NETWORK",
                    severity=l.get("severity", "MEDIUM"),
                    finding=l.get("description", ""),
                    supporting_evidence=f"{l.get('entity_type', 'ENTITY')} link count: {l.get('related_entity_count', 0)}",
                )
            )

    # 3. Model Level Evidence Driver
    if inp.fraud_probability >= inp.decision_threshold:
        model_sev = "CRITICAL" if inp.fraud_probability >= 0.80 else "HIGH"
        shap_summary = "; ".join(inp.top_shap_reasons[:2]) if inp.top_shap_reasons else f"Risk score {inp.risk_score}/100"
        risk_drivers.append(
            RiskDriverItem(
                driver_type="MODEL",
                severity=model_sev,
                finding=f"LightGBM fraud probability {inp.fraud_probability:.1%} exceeds decision threshold {inp.decision_threshold:.0%}.",
                supporting_evidence=shap_summary,
            )
        )

    # 4. Harvest Grounded Mitigating Factors
    if not is_cold_start:
        # Check device recognition
        dev_anom = next((a for a in inp.behavioral_anomalies if a.get("dimension") == "DEVICE"), None)
        if dev_anom and not dev_anom.get("is_anomaly"):
            mitigating_factors.append(f"Transaction initiated from recognized device '{inp.device_id}'.")

        # Check geo recognition
        geo_anom = next((a for a in inp.behavioral_anomalies if a.get("dimension") == "LOCATION"), None)
        if geo_anom and not geo_anom.get("is_anomaly"):
            mitigating_factors.append(f"Geographic region '{inp.geo_region}' matches customer's established activity.")

        # Account maturity
        if inp.account_age_days >= 30:
            mitigating_factors.append(f"Customer account has {inp.account_age_days:.0f} days of established history.")

        # Payment method recognition
        pay_link = next((l for l in inp.network_links if l.get("link_type") == "PAYMENT_METHOD_DIVERGENCE"), None)
        if pay_link and pay_link.get("severity") == "NORMAL":
            mitigating_factors.append(f"Payment method '{inp.payment_method}' matches established customer payment rail.")

        # Network isolation
        if inp.network_overall_status in ("ISOLATED_TRANSACTION", "NOMINAL"):
            mitigating_factors.append("No cross-customer device sharing or merchant velocity bursts detected.")
    else:
        mitigating_factors.append("Clean first-time transaction submission with no prior negative history or failure records.")

    if not mitigating_factors:
        mitigating_factors.append("No significant mitigating evidence was identified in the supplied context.")

    # 5. Formulate Executive Summary
    if is_cold_start:
        exec_summary = (
            f"First-time transaction for customer '{inp.customer_id}' (₹{inp.amount:,.2f} on device '{inp.device_id}'). "
            f"Evaluated under cold-start baseline with zero prior history, resulting in bounded policy recommendation '{inp.recommended_action}'."
        )
    elif risk_drivers:
        primary_driver = risk_drivers[0].finding
        mitigating_note = mitigating_factors[0] if mitigating_factors else "No mitigating factors."
        exec_summary = (
            f"Transaction of ₹{inp.amount:,.2f} for customer '{inp.customer_id}' evaluated as '{inp.recommended_action}' "
            f"(Risk Score: {inp.risk_score}/100, Fraud Probability: {inp.fraud_probability:.1%}). "
            f"Primary risk driver: {primary_driver} Mitigating observation: {mitigating_note}"
        )
    else:
        exec_summary = (
            f"Transaction of ₹{inp.amount:,.2f} for customer '{inp.customer_id}' demonstrates nominal behavior across all evaluated dimensions. "
            f"Recommended policy action is '{inp.recommended_action}' (Risk Score: {inp.risk_score}/100) with no anomalous risk drivers detected."
        )

    # 6. Formulate Analyst Action Guidance (Strictly bounded to existing RISKOVA AI evidence)
    if inp.recommended_action == "BLOCK":
        guidance = (
            f"Review the critical risk drivers and policy rule '{inp.policy_rule_id}' "
            f"that triggered the automated block recommendation."
        )
    elif inp.recommended_action == "STEP_UP":
        guidance = (
            f"Review elevated behavioral/network anomalies and verify step-up authentication "
            f"signals for transaction '{inp.transaction_id}'."
        )
    elif inp.recommended_action == "MONITOR":
        guidance = (
            f"Examine moderate deviation flags and monitor subsequent transaction frequency "
            f"for customer '{inp.customer_id}'."
        )
    else:
        guidance = (
            f"Transaction is consistent with customer baseline; no investigative escalation required."
        )

    return AIInvestigationReport(
        status="DETERMINISTIC_SYNTHESIS",
        executive_summary=exec_summary,
        risk_drivers=risk_drivers,
        mitigating_factors=mitigating_factors,
        analyst_action_guidance=guidance,
        grounding_verification_passed=True,
    )


def verify_grounding(report: AIInvestigationReport, inp: RiskInvestigationInput) -> bool:
    """
    Deterministic post-generation entity grounding validator.
    Ensures that generated narrative text does not invent entity identifiers,
    unsupported customers, merchants, devices, or hallucinated probabilities.
    """
    # Build set of allowed entity tokens
    allowed_tokens: Set[str] = {
        inp.transaction_id.lower(),
        inp.customer_id.lower(),
        inp.merchant_id.lower(),
        inp.device_id.lower(),
        inp.geo_region.lower(),
        inp.payment_method.lower(),
        inp.policy_rule_id.lower(),
        inp.recommended_action.lower(),
    }

    # Also add known customer devices / regions from evidence
    for link in inp.network_links:
        ev = link.get("evidence", {})
        for cid in ev.get("customer_ids", []):
            allowed_tokens.add(str(cid).lower())
        if "device_id" in ev:
            allowed_tokens.add(str(ev["device_id"]).lower())
        if "merchant_id" in ev:
            allowed_tokens.add(str(ev["merchant_id"]).lower())

    full_text = " ".join([
        report.executive_summary,
        " ".join(d.finding + " " + d.supporting_evidence for d in report.risk_drivers),
        " ".join(report.mitigating_factors),
        report.analyst_action_guidance,
    ]).lower()

    # Pattern match entity ID shapes (e.g. dev_*, merch_*, cust_*, txn_*)
    entity_pattern = re.compile(r'\b(dev_[a-zA-Z0-9_\-]+|merch_[a-zA-Z0-9_\-]+|cust_[a-zA-Z0-9_\-]+|txn_[a-zA-Z0-9_\-]+|demo_txn_[a-zA-Z0-9_\-]+|region_\d+)\b')
    extracted_entities = entity_pattern.findall(full_text)

    for ent in extracted_entities:
        if ent not in allowed_tokens:
            logger.warning("Grounding verification failed: ungrounded entity '%s' detected in report.", ent)
            return False

    # Probability grounding: check for claimed fraud probabilities like "XX%"
    prob_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*%\s*(?:fraud|probability|risk)')
    for match in prob_pattern.finditer(full_text):
        claimed_val = float(match.group(1))
        # Expected probability in percentage
        expected_pct = inp.fraud_probability * 100.0
        # If claimed percentage differs by more than 5% from actual model probability, reject as hallucination
        if abs(claimed_val - expected_pct) > 5.0 and abs(claimed_val - inp.decision_threshold * 100.0) > 5.0:
            logger.warning("Grounding verification failed: claimed probability %.1f%% diverges from actual %.1f%%.", claimed_val, expected_pct)
            return False

    return True


def optional_llm_adapter(inp: RiskInvestigationInput) -> Optional[AIInvestigationReport]:
    """
    Optional provider-agnostic HTTP adapter using standard httpx.
    Activated only if RISKOVA_LLM_URL environment variable is configured.
    Falls back gracefully on timeout, malformed response, or grounding failure.
    """
    llm_url = os.environ.get("RISKOVA_LLM_URL")
    if not llm_url:
        return None

    api_key = os.environ.get("RISKOVA_LLM_API_KEY", "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": os.environ.get("RISKOVA_LLM_MODEL", "risk-investigator"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the RISKOVA AI Risk Investigator. You provide grounded risk investigation "
                    "reports based strictly on the supplied evidence. Never invent entities, customers, devices, "
                    "or probabilities. Return valid JSON matching the AIInvestigationReport schema."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(inp.model_dump()),
            },
        ],
        "temperature": 0.0,
    }

    try:
        with httpx.Client(timeout=1.5) as client:
            resp = client.post(llm_url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.warning("LLM provider returned status code %d", resp.status_code)
                return None

            data = resp.json()
            # Extract content (handling standard OpenAI/REST format)
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                return None

            parsed = json.loads(content)
            report = AIInvestigationReport(**parsed)
            report.status = "GENERATED"

            if not verify_grounding(report, inp):
                logger.warning("Generated LLM report failed entity grounding verification; falling back.")
                return None

            report.grounding_verification_passed = True
            return report

    except Exception as e:
        logger.warning("LLM adapter failed (%s); falling back to deterministic synthesis.", e)
        return None


def generate_ai_investigation_report(inp: RiskInvestigationInput) -> AIInvestigationReport:
    """
    Main entry point for Phase 4 AI Risk Investigation.
    Attempts optional LLM generation with strict verification;
    guarantees deterministic grounded synthesis on any failure.
    """
    llm_report = optional_llm_adapter(inp)
    if llm_report is not None:
        return llm_report

    return deterministic_synthesizer(inp)
