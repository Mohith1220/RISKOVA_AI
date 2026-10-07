"""
Related-Transaction & Network Risk Investigation Engine for RISKOVA AI.

PURPOSE (Phase 3):
Evaluates entity-level linkages and related-transaction clustering (Device Sharing,
Device Usage Depth, Merchant Concentration, Payment Rail Divergence) using ONLY
existing historical transactions and schema fields.

DETERMINISTIC & EVIDENCE-GROUNDED:
- Operates strictly as an investigation layer — produces no numeric fraud probability
  and does NOT alter the LightGBM score, SHAP explainer, or deterministic policy action.
- Enforces strict leakage safety: every historical relationship evaluation requires
  t.timestamp < current_transaction.timestamp.
- Classifications are transparent deterministic heuristics for risk analysts.
"""

from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone
from backend.schemas.transaction import RiskRequest, TransactionInput


def _ensure_utc(dt: datetime) -> datetime:
    """Ensures datetime object is timezone-aware in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def evaluate_network_risk(
    request: RiskRequest,
    customer_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluates entity-level linkages and related-transaction evidence deterministically.

    Returns:
    {
        "overall_status": "CRITICAL_NETWORK_RISK" | "ELEVATED_NETWORK_RISK" | "MODERATE_NETWORK_RISK" | "ISOLATED_TRANSACTION" | "INSUFFICIENT_HISTORY",
        "total_links_identified": int,
        "links": List[dict],
        "summary": str,
    }
    """
    current_txn = request.transaction
    curr_ts = _ensure_utc(current_txn.timestamp)

    # Strictly prior transactions for customer
    prior_txns = [t for t in request.prior_transactions if _ensure_utc(t.timestamp) < curr_ts]
    prior_count = len(prior_txns)

    # Strictly prior related transactions (cross-customer or cross-entity)
    related_txns = [t for t in request.related_transactions if _ensure_utc(t.timestamp) < curr_ts]
    related_count = len(related_txns)

    # All prior history combined
    all_prior_txns = prior_txns + related_txns

    # Cold-start check
    if prior_count == 0 and related_count == 0:
        cold_links = [
            {
                "entity_type": "DEVICE",
                "link_type": "DEVICE_SHARING_LINK",
                "related_entity_count": 0,
                "severity": "NORMAL",
                "description": f"No prior historical records for device '{current_txn.device_id}'.",
                "evidence": {"device_id": current_txn.device_id, "distinct_customer_count": 0, "customer_ids": []},
            },
            {
                "entity_type": "DEVICE",
                "link_type": "DEVICE_HISTORY_DEPTH",
                "related_entity_count": 0,
                "severity": "NORMAL",
                "description": "First observed transaction for customer (cold start).",
                "evidence": {"device_id": current_txn.device_id, "customer_id": current_txn.customer_id, "successful_txns_on_device": 0, "total_prior_txns": 0},
            },
            {
                "entity_type": "MERCHANT",
                "link_type": "MERCHANT_CONCENTRATION",
                "related_entity_count": 0,
                "severity": "NORMAL",
                "description": f"First transaction to merchant '{current_txn.merchant_id}'.",
                "evidence": {"merchant_id": current_txn.merchant_id, "merchant_txns_1h": 0, "merchant_txns_24h": 0},
            },
            {
                "entity_type": "PAYMENT_METHOD",
                "link_type": "PAYMENT_METHOD_DIVERGENCE",
                "related_entity_count": 0,
                "severity": "NORMAL",
                "description": f"Initial payment method '{current_txn.payment_method}' recorded for new customer.",
                "evidence": {"current_payment_method": current_txn.payment_method, "known_payment_methods": []},
            },
        ]
        return {
            "overall_status": "INSUFFICIENT_HISTORY",
            "total_links_identified": 0,
            "links": cold_links,
            "summary": "Insufficient prior transaction history to establish entity linkages.",
        }

    links: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # 1. DEVICE_SHARING_LINK
    # Evaluates multi-customer linkage to the same hardware device fingerprint
    # -------------------------------------------------------------------------
    matching_device_txns = [t for t in all_prior_txns if t.device_id == current_txn.device_id]
    distinct_customers: Set[str] = set(t.customer_id for t in matching_device_txns)
    device_cust_count = len(distinct_customers)

    if device_cust_count >= 4:
        dev_share_sev = "CRITICAL"
        dev_share_desc = (
            f"High-density device sharing: device '{current_txn.device_id}' was historically "
            f"associated with {device_cust_count} distinct customer accounts."
        )
    elif device_cust_count >= 2:
        dev_share_sev = "HIGH"
        dev_share_desc = (
            f"Multi-account device linkage: device '{current_txn.device_id}' was historically "
            f"associated with {device_cust_count} distinct customer accounts."
        )
    elif device_cust_count == 1:
        dev_share_sev = "NORMAL"
        dev_share_desc = (
            f"Single-account device: device '{current_txn.device_id}' is exclusively associated "
            f"with 1 customer account in historical records."
        )
    else:
        dev_share_sev = "NORMAL"
        dev_share_desc = f"No prior historical cross-account association for device '{current_txn.device_id}'."

    links.append({
        "entity_type": "DEVICE",
        "link_type": "DEVICE_SHARING_LINK",
        "related_entity_count": device_cust_count,
        "severity": dev_share_sev,
        "description": dev_share_desc,
        "evidence": {
            "device_id": current_txn.device_id,
            "distinct_customer_count": device_cust_count,
            "customer_ids": sorted(list(distinct_customers)),
        },
    })

    # -------------------------------------------------------------------------
    # 2. DEVICE_HISTORY_DEPTH
    # Evaluates prior successful transactions for THIS customer on THIS device
    # -------------------------------------------------------------------------
    cust_device_success_txns = [
        t for t in prior_txns
        if t.device_id == current_txn.device_id and t.status == "success"
    ]
    depth_count = len(cust_device_success_txns)

    if prior_count > 0 and depth_count == 0:
        depth_sev = "MEDIUM"
        depth_desc = (
            f"Novel device for customer: 0 prior successful transactions on device "
            f"'{current_txn.device_id}' despite {prior_count} prior customer transaction(s)."
        )
    elif prior_count == 0:
        depth_sev = "NORMAL"
        depth_desc = "First observed transaction for customer (cold start)."
    else:
        depth_sev = "NORMAL"
        depth_desc = (
            f"Established device relationship: {depth_count} prior successful transaction(s) "
            f"recorded on device '{current_txn.device_id}' for this customer."
        )

    links.append({
        "entity_type": "DEVICE",
        "link_type": "DEVICE_HISTORY_DEPTH",
        "related_entity_count": depth_count,
        "severity": depth_sev,
        "description": depth_desc,
        "evidence": {
            "device_id": current_txn.device_id,
            "customer_id": current_txn.customer_id,
            "successful_txns_on_device": depth_count,
            "total_prior_txns": prior_count,
        },
    })

    # -------------------------------------------------------------------------
    # 3. MERCHANT_CONCENTRATION
    # Evaluates transaction clustering at the current merchant
    # -------------------------------------------------------------------------
    m_1h = 0
    m_24h = 0
    for t in prior_txns:
        if t.merchant_id == current_txn.merchant_id:
            delta_s = (curr_ts - _ensure_utc(t.timestamp)).total_seconds()
            if 0 <= delta_s <= 3600:
                m_1h += 1
            if 0 <= delta_s <= 86400:
                m_24h += 1

    if m_1h >= 4:
        merch_sev = "HIGH"
        merch_desc = (
            f"Rapid merchant velocity: {m_1h} transactions to merchant "
            f"'{current_txn.merchant_id}' in trailing 1 hour."
        )
    elif m_1h >= 2:
        merch_sev = "MEDIUM"
        merch_desc = (
            f"Elevated merchant concentration: {m_1h} transactions to merchant "
            f"'{current_txn.merchant_id}' in trailing 1 hour."
        )
    else:
        merch_sev = "NORMAL"
        merch_desc = (
            f"Normal merchant distribution ({m_1h} in trailing 1h, {m_24h} in trailing 24h "
            f"to merchant '{current_txn.merchant_id}')."
        )

    links.append({
        "entity_type": "MERCHANT",
        "link_type": "MERCHANT_CONCENTRATION",
        "related_entity_count": m_1h,
        "severity": merch_sev,
        "description": merch_desc,
        "evidence": {
            "merchant_id": current_txn.merchant_id,
            "merchant_txns_1h": m_1h,
            "merchant_txns_24h": m_24h,
        },
    })

    # -------------------------------------------------------------------------
    # 4. PAYMENT_METHOD_DIVERGENCE
    # Evaluates whether the payment method is novel for this customer
    # -------------------------------------------------------------------------
    known_methods: Set[str] = set(t.payment_method for t in prior_txns)

    if prior_count == 0:
        pay_sev = "NORMAL"
        pay_desc = f"Initial payment method '{current_txn.payment_method}' recorded for new customer."
    elif current_txn.payment_method not in known_methods:
        pay_sev = "MEDIUM"
        pay_desc = (
            f"Payment rail divergence: current transaction uses '{current_txn.payment_method}', "
            f"whereas customer previously used {sorted(list(known_methods))}."
        )
    else:
        pay_sev = "NORMAL"
        pay_desc = f"Payment method '{current_txn.payment_method}' matches customer's established payment habits."

    links.append({
        "entity_type": "PAYMENT_METHOD",
        "link_type": "PAYMENT_METHOD_DIVERGENCE",
        "related_entity_count": len(known_methods),
        "severity": pay_sev,
        "description": pay_desc,
        "evidence": {
            "current_payment_method": current_txn.payment_method,
            "known_payment_methods": sorted(list(known_methods)),
        },
    })

    # -------------------------------------------------------------------------
    # Overall Network Status Aggregation
    # -------------------------------------------------------------------------
    active_links = [l for l in links if l["severity"] in ("CRITICAL", "HIGH", "MEDIUM")]
    active_count = len(active_links)

    critical_count = sum(1 for l in links if l["severity"] == "CRITICAL")
    high_count = sum(1 for l in links if l["severity"] == "HIGH")
    medium_count = sum(1 for l in links if l["severity"] == "MEDIUM")

    if critical_count >= 1:
        overall_status = "CRITICAL_NETWORK_RISK"
        summary = f"Critical entity risk: {critical_count} critical network link(s) detected across shared infrastructure."
    elif high_count >= 1:
        overall_status = "ELEVATED_NETWORK_RISK"
        summary = f"Elevated network risk: {high_count} high-severity entity link(s) detected."
    elif medium_count >= 1:
        overall_status = "MODERATE_NETWORK_RISK"
        summary = f"Moderate entity divergence: {medium_count} moderate entity/method divergence flag(s) observed."
    else:
        overall_status = "ISOLATED_TRANSACTION"
        summary = "No anomalous cross-entity linkages or merchant velocity bursts detected."

    return {
        "overall_status": overall_status,
        "total_links_identified": active_count,
        "links": links,
        "summary": summary,
    }
