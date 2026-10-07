from typing import Optional, List
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: Optional[str] = None


class ModelInfoResponse(BaseModel):
    model_version: str
    model_file: str
    decision_threshold: float
    selection_rule: str
    validation_metrics_at_threshold: dict
    test_metrics_at_frozen_threshold: dict
    feature_columns: List[str]


class RiskScoreResponse(BaseModel):
    transaction_id: str
    model_version: str
    fraud_probability: float
    risk_score: int
    risk_category: str


class ContributionItem(BaseModel):
    feature: str
    value: float
    shap_value: float
    direction: str
    magnitude: float


class RiskExplainResponse(BaseModel):
    transaction_id: str
    model_version: str
    fraud_probability: float
    additivity_check_passed: bool
    header: str
    reasons: List[str]
    contributions: List[ContributionItem]
    cold_start_context: Optional[str] = None  # V2: contextual signal for 0 prior txns (NOT a SHAP contribution)


class CustomerHistorySummary(BaseModel):
    prior_transaction_count: int
    historical_avg_amount: Optional[float] = None
    historical_std_amount: Optional[float] = None
    historical_min_amount: Optional[float] = None
    historical_max_amount: Optional[float] = None
    account_age_days: float
    known_devices: List[str] = []
    known_geos: List[str] = []
    first_seen_timestamp: Optional[str] = None
    last_seen_timestamp: Optional[str] = None


class BehavioralSignals(BaseModel):
    status: str  # "ESTABLISHED_HISTORY" | "INSUFFICIENT_HISTORY"
    amount_deviation: Optional[dict] = None
    velocity: dict
    device_novelty: dict
    geo_novelty: dict
    recent_failure_rate: float
    timing: dict


class InvestigationFinding(BaseModel):
    signal_type: str
    severity: str  # "HIGH" | "MEDIUM" | "LOW" | "INFO"
    description: str
    evidence: dict


class BehavioralAnomalyItem(BaseModel):
    dimension: str  # "AMOUNT", "VELOCITY", "INTERVAL", "DEVICE", "LOCATION", "FAILURE_BURST"
    is_anomaly: bool
    severity: str   # "CRITICAL", "HIGH", "MEDIUM", "LOW", "NORMAL"
    description: str
    baseline_summary: str
    observed_summary: str
    evidence: dict


class BehavioralAssessment(BaseModel):
    overall_status: str  # "CRITICAL_ANOMALIES", "ELEVATED_ANOMALIES", "MODERATE_ANOMALIES", "NOMINAL", "INSUFFICIENT_HISTORY"
    anomaly_count: int
    anomalies: List[BehavioralAnomalyItem]


class NetworkLinkItem(BaseModel):
    entity_type: str  # "DEVICE", "MERCHANT", "PAYMENT_METHOD"
    link_type: str    # "DEVICE_SHARING_LINK", "DEVICE_HISTORY_DEPTH", "MERCHANT_CONCENTRATION", "PAYMENT_METHOD_DIVERGENCE"
    related_entity_count: int
    severity: str     # "CRITICAL", "HIGH", "MEDIUM", "LOW", "NORMAL"
    description: str
    evidence: dict


class NetworkAssessment(BaseModel):
    overall_status: str  # "CRITICAL_NETWORK_RISK", "ELEVATED_NETWORK_RISK", "MODERATE_NETWORK_RISK", "ISOLATED_TRANSACTION", "INSUFFICIENT_HISTORY"
    total_links_identified: int
    links: List[NetworkLinkItem]
    summary: str


class RiskDriverItem(BaseModel):
    driver_type: str        # "BEHAVIORAL" | "NETWORK" | "MODEL" | "VELOCITY"
    severity: str           # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    finding: str            # Concise finding statement
    supporting_evidence: str # Concrete cited metric


class AIInvestigationReport(BaseModel):
    status: str                         # "GENERATED" | "DETERMINISTIC_SYNTHESIS" | "UNAVAILABLE"
    executive_summary: str              # 2-3 sentence grounded risk synthesis
    risk_drivers: List[RiskDriverItem]  # Specific driving risk signals
    mitigating_factors: List[str]       # Grounded evidence against fraud
    analyst_action_guidance: str        # Actionable checklist within bounded policy action
    grounding_verification_passed: bool # Verification status flag proving zero hallucinated entities


class InvestigationContext(BaseModel):
    status: str  # "AVAILABLE" | "INSUFFICIENT_HISTORY"
    customer_summary: CustomerHistorySummary
    behavioral_signals: BehavioralSignals
    key_findings: List[InvestigationFinding]
    behavioral_assessment: Optional[BehavioralAssessment] = None      # Phase 2: Structured Behavioral Anomaly Assessment
    network_assessment: Optional[NetworkAssessment] = None            # Phase 3: Related-Transaction / Network Risk Assessment
    ai_investigation_report: Optional[AIInvestigationReport] = None  # Phase 4: AI Risk Investigator Report
    customer_id: str
    current_transaction_id: str


class RiskCaseTransactionFacts(BaseModel):
    transaction_id: str
    customer_id: str
    amount: float
    timestamp: str
    merchant_id: str
    merchant_category: str
    device_id: str
    geo_region: str
    payment_method: str


class RiskCaseModelAssessment(BaseModel):
    fraud_probability: float
    risk_score: int
    risk_category: str
    decision_threshold: float
    top_shap_reasons: List[str]
    cold_start_context: Optional[str] = None


class RiskCasePolicyDecision(BaseModel):
    action: str
    policy_rule_id: str
    policy_reason: str


class RiskCaseAuditMetadata(BaseModel):
    request_id: str
    decision_timestamp: str
    source: str
    audit_persisted: bool
    audit_error: Optional[str] = None


class RiskCase(BaseModel):
    """
    Unified, auditable Risk Case artifact assembling grounded evidence
    from Phases 1–4 without risk recalculation.
    """
    case_id: str
    created_at: str
    model_version: str
    transaction_facts: RiskCaseTransactionFacts
    model_assessment: RiskCaseModelAssessment
    customer_context: CustomerHistorySummary
    behavioral_assessment: Optional[BehavioralAssessment] = None
    network_assessment: Optional[NetworkAssessment] = None
    ai_investigation: Optional[AIInvestigationReport] = None
    policy_decision: RiskCasePolicyDecision
    audit_metadata: RiskCaseAuditMetadata


class RiskEvaluateResponse(BaseModel):
    request_id: str
    transaction_id: str
    model_version: str
    fraud_probability: float
    threshold: float
    risk_score: int
    risk_category: str
    action: str
    policy_rule_id: str
    policy_reason: str
    explanation_header: str
    reasons: List[str]
    explanation_available: bool = True  # V2: indicates if SHAP succeeded
    cold_start_context: Optional[str] = None  # V2: contextual signal for 0 prior txns (NOT a SHAP contribution)
    timestamp: str
    signal_quality: Optional[dict] = None  # V2: historical context quality {"level", "prior_transaction_count", "message"}
    prior_transaction_count: int = 0  # V2: count of prior transactions provided
    audit_persisted: bool
    audit_error: Optional[str] = None
    investigation_context: Optional[InvestigationContext] = None  # Rich transaction investigation context
    risk_case: Optional[RiskCase] = None                          # Phase 5: Final Auditable Risk Case



class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: Optional[str] = None

