"""
Behavioral Anomaly Investigation Engine for RISKOVA AI.

PURPOSE (Phase 2):
Analyzes the customer's transaction against their available historical baseline
across 6 distinct behavioral dimensions (Amount, Velocity, Interval, Device,
Location, and Failure Burst).

DETERMINISTIC & EVIDENCE-GROUNDED:
- Operates strictly on: current transaction + customer's prior transaction history +
  engineered features (from build_features.py).
- No arbitrary probability calculations or ML models.
- Does NOT alter the deterministic policy action (which is keyed strictly on ML probability + amount).
- Explicit cold-start protection: if prior history is empty, reports INSUFFICIENT_HISTORY
  and does not fabricate baseline statistics or false anomalies.
"""

from typing import List, Dict, Any, Optional
import pandas as pd
from backend.schemas.transaction import RiskRequest


def evaluate_behavioral_anomalies(
    request: RiskRequest,
    row: pd.Series,
    customer_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Evaluates 6 behavioral dimensions deterministically.

    Returns:
    {
        "overall_status": "CRITICAL_ANOMALIES" | "ELEVATED_ANOMALIES" | "MODERATE_ANOMALIES" | "NOMINAL" | "INSUFFICIENT_HISTORY",
        "anomaly_count": int,
        "anomalies": List[dict]
    }
    """
    prior_txns = request.prior_transactions
    prior_count = len(prior_txns)
    current_txn = request.transaction

    # Cold-start case: no historical baseline available
    if prior_count == 0:
        dimensions = ["AMOUNT", "VELOCITY", "INTERVAL", "DEVICE", "LOCATION", "FAILURE_BURST"]
        cold_anomalies = [
            {
                "dimension": dim,
                "is_anomaly": False,
                "severity": "NORMAL",
                "description": "No prior transaction history available to evaluate anomaly status.",
                "baseline_summary": "No prior transactions on record",
                "observed_summary": "First observed transaction for customer",
                "evidence": {"prior_txn_count": 0},
            }
            for dim in dimensions
        ]
        return {
            "overall_status": "INSUFFICIENT_HISTORY",
            "anomaly_count": 0,
            "anomalies": cold_anomalies,
        }

    # Extract historical baseline metrics from customer_summary
    avg_amount = float(customer_summary.get("historical_avg_amount") or current_txn.amount)
    max_amount = float(customer_summary.get("historical_max_amount") or current_txn.amount)
    std_amount = float(customer_summary.get("historical_std_amount") or 0.0)
    known_devices = customer_summary.get("known_devices") or []
    known_geos = customer_summary.get("known_geos") or []

    # Extract strictly-prior engineered feature values from row
    amount_ratio = float(row.get("amount_vs_avg_ratio", 1.0))
    amount_zscore = float(row.get("amount_zscore", 0.0))
    vel_5 = int(row.get("velocity_5min", 0))
    vel_30 = int(row.get("velocity_30min", 0))
    vel_60 = int(row.get("velocity_60min", 0))
    time_prev = float(row.get("time_since_prev_txn_min", 99999.0))
    is_new_device = bool(row.get("new_device_flag", 0) == 1)
    is_new_geo = bool(row.get("new_geo_flag", 0) == 1)
    fail_ratio = float(row.get("failed_ratio_trailing10", 0.0))

    anomalies: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # 1. AMOUNT ANOMALY
    # Evaluates transaction amount vs historical average and standard deviations
    # (Statistical z-score is evaluated only when customer history has non-zero variance)
    # -------------------------------------------------------------------------
    has_meaningful_std = std_amount >= 1.0
    effective_zscore = amount_zscore if has_meaningful_std else 0.0

    if amount_ratio >= 5.0 or effective_zscore >= 5.0:
        amt_sev = "CRITICAL"
        amt_anomaly = True
        amt_desc = f"Extreme amount surge: transaction amount (₹{current_txn.amount:,.2f}) is {amount_ratio:.1f}x the customer's average (₹{avg_amount:,.2f}) with z-score {amount_zscore:.1f}σ."
    elif amount_ratio >= 2.5 or effective_zscore >= 2.5:
        amt_sev = "HIGH"
        amt_anomaly = True
        amt_desc = f"Substantial amount surge: transaction amount (₹{current_txn.amount:,.2f}) is {amount_ratio:.1f}x the customer's average (₹{avg_amount:,.2f}) with z-score {amount_zscore:.1f}σ."
    elif amount_ratio >= 1.5 or effective_zscore >= 1.5:
        amt_sev = "MEDIUM"
        amt_anomaly = True
        amt_desc = f"Moderate amount elevation: transaction amount (₹{current_txn.amount:,.2f}) is {amount_ratio:.1f}x the customer's average (₹{avg_amount:,.2f})."
    else:
        amt_sev = "NORMAL"
        amt_anomaly = False
        amt_desc = f"Transaction amount (₹{current_txn.amount:,.2f}) is consistent with normal customer spending (avg ₹{avg_amount:,.2f})."


    anomalies.append({
        "dimension": "AMOUNT",
        "is_anomaly": amt_anomaly,
        "severity": amt_sev,
        "description": amt_desc,
        "baseline_summary": f"Historical avg ₹{avg_amount:,.2f} (max ₹{max_amount:,.2f} across {prior_count} txns)",
        "observed_summary": f"Current ₹{current_txn.amount:,.2f} ({amount_ratio:.1f}x avg, {amount_zscore:.1f}σ)",
        "evidence": {
            "current_amount": current_txn.amount,
            "historical_avg": round(avg_amount, 2),
            "ratio": round(amount_ratio, 2),
            "zscore": round(amount_zscore, 2),
        },
    })

    # -------------------------------------------------------------------------
    # 2. VELOCITY ANOMALY
    # Evaluates rapid burst transaction clustering across 5m, 30m, and 60m windows
    # -------------------------------------------------------------------------
    if vel_5 >= 3 or vel_30 >= 5 or vel_60 >= 8:
        vel_sev = "CRITICAL"
        vel_anomaly = True
        vel_desc = f"Critical velocity burst: {vel_5} in past 5m, {vel_30} in past 30m, {vel_60} in past 60m."
    elif vel_5 >= 2 or vel_30 >= 3 or vel_60 >= 4:
        vel_sev = "HIGH"
        vel_anomaly = True
        vel_desc = f"High transaction velocity: {vel_5} in past 5m, {vel_30} in past 30m, {vel_60} in past 60m."
    elif vel_60 >= 2:
        vel_sev = "MEDIUM"
        vel_anomaly = True
        vel_desc = f"Elevated frequency: {vel_60} transactions occurred in the past 60 minutes."
    else:
        vel_sev = "NORMAL"
        vel_anomaly = False
        vel_desc = "Transaction frequency is normal; no rapid transaction clustering observed."

    anomalies.append({
        "dimension": "VELOCITY",
        "is_anomaly": vel_anomaly,
        "severity": vel_sev,
        "description": vel_desc,
        "baseline_summary": "Historical baseline: normal isolated transactions",
        "observed_summary": f"{vel_5} in past 5m · {vel_30} in past 30m · {vel_60} in past 60m",
        "evidence": {
            "velocity_5min": vel_5,
            "velocity_30min": vel_30,
            "velocity_60min": vel_60,
        },
    })

    # -------------------------------------------------------------------------
    # 3. INTERVAL ANOMALY
    # Evaluates elapsed time since previous transaction
    # -------------------------------------------------------------------------
    if time_prev <= 1.0:
        int_sev = "HIGH"
        int_anomaly = True
        int_desc = f"Automated/rapid succession: only {time_prev*60:.0f} seconds ({time_prev:.2f} min) since previous transaction."
    elif time_prev <= 5.0:
        int_sev = "MEDIUM"
        int_anomaly = True
        int_desc = f"Rapid follow-up: transaction occurred {time_prev:.1f} minutes after previous transaction."
    else:
        int_sev = "NORMAL"
        int_anomaly = False
        int_desc = f"Elapsed interval ({time_prev:.1f} min) since previous transaction is normal."

    anomalies.append({
        "dimension": "INTERVAL",
        "is_anomaly": int_anomaly,
        "severity": int_sev,
        "description": int_desc,
        "baseline_summary": f"Previous transaction recorded for customer",
        "observed_summary": f"{time_prev:.1f} minutes elapsed since previous transaction",
        "evidence": {
            "time_since_prev_txn_min": round(time_prev, 2),
        },
    })

    # -------------------------------------------------------------------------
    # 4. DEVICE ANOMALY
    # Evaluates novelty of current device against customer's known devices
    # -------------------------------------------------------------------------
    if is_new_device:
        dev_sev = "HIGH"
        dev_anomaly = True
        dev_desc = f"Unseen device '{current_txn.device_id}' detected (customer previously transacted with {len(known_devices)} known device(s))."
    else:
        dev_sev = "NORMAL"
        dev_anomaly = False
        dev_desc = f"Device '{current_txn.device_id}' matches customer's recognized device history."

    anomalies.append({
        "dimension": "DEVICE",
        "is_anomaly": dev_anomaly,
        "severity": dev_sev,
        "description": dev_desc,
        "baseline_summary": f"{len(known_devices)} known device(s) on file",
        "observed_summary": f"{'⚠️ Novel device' if is_new_device else '✓ Recognized device'}: {current_txn.device_id}",
        "evidence": {
            "current_device": current_txn.device_id,
            "is_new_device": is_new_device,
            "known_devices_count": len(known_devices),
        },
    })

    # -------------------------------------------------------------------------
    # 5. LOCATION ANOMALY
    # Evaluates novelty of geographic region against customer's history
    # -------------------------------------------------------------------------
    if is_new_geo:
        geo_sev = "HIGH"
        geo_anomaly = True
        geo_desc = f"Unfamiliar region '{current_txn.geo_region}' detected (customer previously transacted in {len(known_geos)} known region(s))."
    else:
        geo_sev = "NORMAL"
        geo_anomaly = False
        geo_desc = f"Geographic region '{current_txn.geo_region}' matches customer's established activity."

    anomalies.append({
        "dimension": "LOCATION",
        "is_anomaly": geo_anomaly,
        "severity": geo_sev,
        "description": geo_desc,
        "baseline_summary": f"{len(known_geos)} known region(s) on file",
        "observed_summary": f"{'⚠️ Novel region' if is_new_geo else '✓ Recognized region'}: {current_txn.geo_region}",
        "evidence": {
            "current_geo": current_txn.geo_region,
            "is_new_geo": is_new_geo,
            "known_geos_count": len(known_geos),
        },
    })

    # -------------------------------------------------------------------------
    # 6. FAILURE BURST ANOMALY
    # Evaluates trailing failure rate for card testing or authorization stress
    # -------------------------------------------------------------------------
    if fail_ratio >= 0.5:
        fail_sev = "CRITICAL"
        fail_anomaly = True
        fail_desc = f"Severe failure spike: {fail_ratio:.0%} of the last 10 transactions failed."
    elif fail_ratio >= 0.3:
        fail_sev = "HIGH"
        fail_anomaly = True
        fail_desc = f"Elevated failure rate: {fail_ratio:.0%} of recent transactions failed."
    elif fail_ratio > 0.0:
        fail_sev = "MEDIUM"
        fail_anomaly = True
        fail_desc = f"Intermittent failures: {fail_ratio:.0%} of recent transactions failed."
    else:
        fail_sev = "NORMAL"
        fail_anomaly = False
        fail_desc = "Clean transaction history with 0% recent transaction failures."

    anomalies.append({
        "dimension": "FAILURE_BURST",
        "is_anomaly": fail_anomaly,
        "severity": fail_sev,
        "description": fail_desc,
        "baseline_summary": "Historical baseline: 0% recent failures",
        "observed_summary": f"{fail_ratio:.0%} failed in trailing 10 transactions",
        "evidence": {
            "failed_ratio_trailing10": round(fail_ratio, 2),
        },
    })

    # Compute overall behavioral anomaly classification
    active_anomalies = [a for a in anomalies if a["is_anomaly"]]
    anomaly_count = len(active_anomalies)
    critical_count = sum(1 for a in active_anomalies if a["severity"] == "CRITICAL")
    high_count = sum(1 for a in active_anomalies if a["severity"] == "HIGH")
    medium_count = sum(1 for a in active_anomalies if a["severity"] == "MEDIUM")

    if critical_count >= 1 or high_count >= 3:
        overall_status = "CRITICAL_ANOMALIES"
    elif high_count >= 1 or medium_count >= 2:
        overall_status = "ELEVATED_ANOMALIES"
    elif medium_count >= 1:
        overall_status = "MODERATE_ANOMALIES"
    else:
        overall_status = "NOMINAL"

    return {
        "overall_status": overall_status,
        "anomaly_count": anomaly_count,
        "anomalies": anomalies,
    }
