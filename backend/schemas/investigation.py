"""
Investigation schemas for AI Risk Investigator (Phase 4).

Defines the structured input contract containing ONLY grounded facts
and evidence already produced by MerchantShield.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class RiskInvestigationInput(BaseModel):
    """
    Structured evidence package supplied to the AI Risk Investigator.
    Contains ONLY grounded values already calculated by MerchantShield.
    """
    # 1. FACTS (Directly observed transaction inputs)
    transaction_id: str
    customer_id: str
    amount: float
    timestamp: str
    merchant_id: str
    merchant_category: str
    device_id: str
    geo_region: str
    payment_method: str

    # 2. MODEL EVIDENCE (LightGBM + SHAP)
    fraud_probability: float
    decision_threshold: float
    risk_score: int
    risk_category: str
    top_shap_reasons: List[str] = Field(default_factory=list)
    cold_start_context: Optional[str] = None

    # 3. CUSTOMER BASELINE FACTS
    prior_transaction_count: int
    historical_avg_amount: Optional[float] = None
    historical_max_amount: Optional[float] = None
    account_age_days: float
    known_devices_count: int
    known_geos_count: int

    # 4. BEHAVIORAL EVIDENCE (Phase 2)
    behavioral_overall_status: str
    behavioral_anomalies: List[Dict[str, Any]] = Field(default_factory=list)

    # 5. NETWORK EVIDENCE (Phase 3)
    network_overall_status: str
    network_links: List[Dict[str, Any]] = Field(default_factory=list)

    # 6. POLICY RESULT (Deterministic action)
    recommended_action: str
    policy_rule_id: str
    policy_reason: str
