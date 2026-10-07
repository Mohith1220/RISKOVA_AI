import React, { useState } from "react";
import { formatCurrency, friendlyFeatureLabel } from "../utils/presentation";

function SeverityBadge({ severity }) {
  const sev = (severity || "INFO").toUpperCase();
  const styles = {
    CRITICAL: { background: "rgba(255, 77, 94, 0.15)", color: "#FF4D5E", border: "1px solid rgba(255, 77, 94, 0.35)" },
    HIGH: { background: "rgba(255, 138, 61, 0.15)", color: "#FF8A3D", border: "1px solid rgba(255, 138, 61, 0.35)" },
    MEDIUM: { background: "rgba(245, 185, 66, 0.15)", color: "#F5B942", border: "1px solid rgba(245, 185, 66, 0.35)" },
    LOW: { background: "rgba(39, 209, 127, 0.15)", color: "#27D17F", border: "1px solid rgba(39, 209, 127, 0.35)" },
    INFO: { background: "rgba(143, 161, 184, 0.12)", color: "#8FA1B8", border: "1px solid #26344A" },
    NORMAL: { background: "rgba(39, 209, 127, 0.15)", color: "#27D17F", border: "1px solid rgba(39, 209, 127, 0.35)" },
  };

  const current = styles[sev] || styles.INFO;

  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 7px",
        borderRadius: "3px",
        fontSize: "10.5px",
        fontWeight: "700",
        letterSpacing: "0.02em",
        ...current,
      }}
    >
      {sev}
    </span>
  );
}

const DIMENSION_LABELS = {
  AMOUNT: "Amount Deviation",
  VELOCITY: "Transaction Velocity",
  INTERVAL: "Transaction Interval",
  DEVICE: "Device Novelty",
  LOCATION: "Location Novelty",
  FAILURE_BURST: "Failure Burst / Card Testing",
};

const NETWORK_LINK_LABELS = {
  DEVICE_SHARING_LINK: "Device Sharing Linkage",
  DEVICE_HISTORY_DEPTH: "Device Usage Depth",
  MERCHANT_CONCENTRATION: "Merchant Concentration",
  PAYMENT_METHOD_DIVERGENCE: "Payment Rail Profile",
};

function ContributionBar({ contribution }) {
  const isIncrease = contribution.direction === "increases_risk";
  const widthPct = Math.min(50, Math.abs(contribution.magnitude) * 40 + 6);

  return (
    <div className="contribution-bar-row">
      <div className="contribution-bar-label">
        <span>{friendlyFeatureLabel(contribution.feature)}</span>
        <span
          className={`contribution-bar-direction ${isIncrease ? "contribution-increase" : "contribution-decrease"}`}
        >
          {isIncrease ? "↑ increases risk" : "↓ decreases risk"}
        </span>
      </div>
      <div className="contribution-bar-track" aria-hidden="true">
        <div className="contribution-bar-midline" />
        <div
          className={`contribution-bar-fill ${isIncrease ? "increase" : "decrease"}`}
          style={{ width: `${widthPct}%` }}
        />
      </div>
    </div>
  );
}

function AccordionSection({ title, subtitle, badge, isOpen, onToggle, children }) {
  return (
    <div className={`accordion-card ${isOpen ? "open" : "closed"}`}>
      <button
        type="button"
        className="accordion-header-btn"
        onClick={onToggle}
        aria-expanded={isOpen}
      >
        <div className="accordion-header-left">
          <span className="accordion-chevron" aria-hidden="true">
            {isOpen ? "▼" : "▶"}
          </span>
          <span className="accordion-title">{title}</span>
          {subtitle && <span className="accordion-subtitle">{subtitle}</span>}
        </div>
        {badge && <div className="accordion-header-right">{badge}</div>}
      </button>

      {isOpen && <div className="accordion-content">{children}</div>}
    </div>
  );
}

export default function DetailedEvidenceAccordion({ result, explanation, payload }) {
  const [openSections, setOpenSections] = useState({
    context: true,
    behavioral: true,
    network: true,
    shap: false,
    policy: false,
  });

  const toggleSection = (key) => {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (!result) return null;

  const invCtx = result.investigation_context || {};
  const customerSummary = invCtx.customer_summary || {};
  const behavioralAssessment = invCtx.behavioral_assessment || {};
  const anomalies = behavioralAssessment.anomalies || [];
  const networkAssessment = invCtx.network_assessment || {};
  const networkLinks = networkAssessment.links || [];
  const txnFacts = result.risk_case?.transaction_facts || payload?.transaction || {};

  const topContributions = explanation?.contributions
    ? [...explanation.contributions].sort((a, b) => b.magnitude - a.magnitude).slice(0, 6)
    : [];

  return (
    <div className="detailed-evidence-container">
      <div className="detailed-evidence-header">
        <span className="detailed-evidence-title">DETAILED SUPPORTING EVIDENCE</span>
        <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>
          Expand sections to inspect raw features, baselines, and linkages
        </span>
      </div>

      <div className="accordion-stack">
        {/* Section 1: Transaction & Customer Context */}
        <AccordionSection
          title="Transaction & Customer Context"
          subtitle={`Customer ${txnFacts.customer_id || "—"}`}
          badge={
            <span className="accordion-pill">
              {customerSummary.prior_transaction_count || 0} prior txns
            </span>
          }
          isOpen={openSections.context}
          onToggle={() => toggleSection("context")}
        >
          {/* Transaction facts grid */}
          <div className="evidence-facts-grid">
            <div className="fact-item">
              <span className="fact-label">Transaction ID</span>
              <span className="fact-value mono">{txnFacts.transaction_id || "—"}</span>
            </div>
            <div className="fact-item">
              <span className="fact-label">Amount</span>
              <span className="fact-value">{formatCurrency(txnFacts.amount)}</span>
            </div>
            <div className="fact-item">
              <span className="fact-label">Payment Method</span>
              <span className="fact-value" style={{ textTransform: "capitalize" }}>
                {txnFacts.payment_method || "—"}
              </span>
            </div>
            <div className="fact-item">
              <span className="fact-label">Merchant ID &amp; Cat</span>
              <span className="fact-value">
                {txnFacts.merchant_id || "—"} ({txnFacts.merchant_category || "—"})
              </span>
            </div>
            <div className="fact-item">
              <span className="fact-label">Device ID</span>
              <span className="fact-value mono">{txnFacts.device_id || "—"}</span>
            </div>
            <div className="fact-item">
              <span className="fact-label">Geo Region</span>
              <span className="fact-value mono">{txnFacts.geo_region || "—"}</span>
            </div>
          </div>

          {/* Customer baseline box */}
          <div className="customer-baseline-box">
            <div className="baseline-box-title">CUSTOMER HISTORICAL PROFILE</div>
            <div className="baseline-grid">
              <div>
                <span className="base-label">Prior Transactions:</span>{" "}
                <strong className="text-primary">{customerSummary.prior_transaction_count ?? 0}</strong>
              </div>
              <div>
                <span className="base-label">Historical Average:</span>{" "}
                <strong className="text-primary">{formatCurrency(customerSummary.historical_avg_amount)}</strong>
              </div>
              <div>
                <span className="base-label">Historical Range:</span>{" "}
                <strong className="text-primary">
                  {customerSummary.historical_min_amount !== null && customerSummary.historical_min_amount !== undefined
                    ? `${formatCurrency(customerSummary.historical_min_amount)} – ${formatCurrency(customerSummary.historical_max_amount)}`
                    : "—"}
                </strong>
              </div>
              <div>
                <span className="base-label">Account Age:</span>{" "}
                <strong className="text-primary">{customerSummary.account_age_days ?? "—"} days</strong>
              </div>
              <div>
                <span className="base-label">Known Devices:</span>{" "}
                <strong className="text-primary">{customerSummary.known_devices?.length ?? 0} device(s)</strong>
              </div>
              <div>
                <span className="base-label">Known Regions:</span>{" "}
                <strong className="text-primary">{customerSummary.known_geos?.length ?? 0} region(s)</strong>
              </div>
            </div>
          </div>
        </AccordionSection>

        {/* Section 2: Behavioral Anomalies */}
        <AccordionSection
          title="Behavioral Anomalies (6 Dimensions)"
          subtitle={`${behavioralAssessment.anomaly_count || 0} anomalous dimension(s)`}
          badge={
            <span
              className={`accordion-status-pill ${
                behavioralAssessment.overall_status === "NOMINAL"
                  ? "nominal"
                  : behavioralAssessment.overall_status === "INSUFFICIENT_HISTORY"
                  ? "neutral"
                  : "warning"
              }`}
            >
              {behavioralAssessment.overall_status || "AVAILABLE"}
            </span>
          }
          isOpen={openSections.behavioral}
          onToggle={() => toggleSection("behavioral")}
        >
          {anomalies.length > 0 ? (
            <div className="anomaly-matrix-grid">
              {anomalies.map((a) => (
                <div
                  key={a.dimension}
                  className={`anomaly-matrix-row ${a.is_anomaly ? "is-anomalous" : "is-nominal"}`}
                >
                  <div className="anomaly-row-header">
                    <div className="anomaly-dimension-title">
                      {DIMENSION_LABELS[a.dimension] || a.dimension}
                    </div>
                    <SeverityBadge severity={a.severity} />
                  </div>
                  <div className="anomaly-description">{a.description}</div>
                  <div className="anomaly-evidence-bar">
                    <div>
                      <span className="evidence-tag-label">Baseline: </span>
                      <span style={{ color: "#F4F7FB" }}>{a.baseline_summary}</span>
                    </div>
                    <div>
                      <span className="evidence-tag-label">Observed: </span>
                      <span className={a.is_anomaly ? "text-danger-strong" : "text-success-strong"}>
                        {a.observed_summary}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-substate">No behavioral dimensions recorded.</div>
          )}
        </AccordionSection>

        {/* Section 3: Network & Related Entities */}
        <AccordionSection
          title="Network & Related Entity Links"
          subtitle={networkAssessment.summary || "Cross-entity graph indicators"}
          badge={
            <span className="accordion-status-pill neutral">
              {networkAssessment.overall_status || "ISOLATED"}
            </span>
          }
          isOpen={openSections.network}
          onToggle={() => toggleSection("network")}
        >
          {networkLinks.length > 0 ? (
            <div className="network-links-grid">
              {networkLinks.map((link, idx) => (
                <div
                  key={idx}
                  className={`network-link-card ${link.severity !== "NORMAL" ? "elevated" : "nominal"}`}
                >
                  <div className="network-link-header">
                    <span className="network-link-title">
                      {NETWORK_LINK_LABELS[link.link_type] || link.link_type}
                    </span>
                    <SeverityBadge severity={link.severity} />
                  </div>
                  <div className="network-link-desc">{link.description}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-substate">No network links identified.</div>
          )}
        </AccordionSection>

        {/* Section 4: SHAP Model Evidence */}
        <AccordionSection
          title="SHAP Model Evidence & Feature Contributions"
          subtitle="TreeSHAP local feature attributions"
          isOpen={openSections.shap}
          onToggle={() => toggleSection("shap")}
        >
          {explanation?.cold_start_context && (
            <div className="cold-start-banner">
              <strong>⚠️ Cold Start Context: </strong>
              <span>{explanation.cold_start_context}</span>
            </div>
          )}

          {explanation?.reasons && explanation.reasons.length > 0 && (
            <div className="shap-reasons-box">
              <div className="shap-box-title">TOP MODEL DECISION DRIVERS</div>
              <ul className="shap-reasons-list">
                {explanation.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {topContributions.length > 0 && (
            <div className="shap-bars-container">
              <div className="shap-bars-title">FEATURE CONTRIBUTION DIRECTION &amp; MAGNITUDE</div>
              {topContributions.map((c) => (
                <ContributionBar key={c.feature} contribution={c} />
              ))}
            </div>
          )}
        </AccordionSection>

        {/* Section 5: Authoritative Policy Decision */}
        <AccordionSection
          title="Authoritative Policy Decision"
          subtitle={`Rule: ${result.policy_rule_id}`}
          isOpen={openSections.policy}
          onToggle={() => toggleSection("policy")}
        >
          <div className="policy-detail-card">
            <div className="policy-detail-row">
              <span className="policy-dt-label">Action:</span>
              <span className="policy-dt-value mono" style={{ fontWeight: "700", color: "#F4F7FB" }}>
                {result.action}
              </span>
            </div>
            <div className="policy-detail-row">
              <span className="policy-dt-label">Rule ID:</span>
              <span className="policy-dt-value mono" style={{ color: "var(--accent)" }}>{result.policy_rule_id}</span>
            </div>
            <div className="policy-detail-row">
              <span className="policy-dt-label">Policy Reason:</span>
              <span className="policy-dt-value">{result.policy_reason}</span>
            </div>
            <div className="policy-detail-row">
              <span className="policy-dt-label">Decision Threshold:</span>
              <span className="policy-dt-value mono">{result.threshold}</span>
            </div>
          </div>

          <div className="policy-table-wrapper">
            <table className="policy-rules-table" aria-label="Policy rules reference table">
              <thead>
                <tr>
                  <th>RULE</th>
                  <th>CONDITION</th>
                  <th>ACTION</th>
                </tr>
              </thead>
              <tbody>
                <tr className={result.policy_rule_id === "CRITICAL_BLOCK" ? "active-rule" : ""}>
                  <td className="mono">CRITICAL_BLOCK</td>
                  <td>p ≥ 0.80</td>
                  <td className="mono">BLOCK</td>
                </tr>
                <tr className={result.policy_rule_id === "HIGH_STEP_UP" ? "active-rule" : ""}>
                  <td className="mono">HIGH_STEP_UP</td>
                  <td>p ≥ 0.40</td>
                  <td className="mono">STEP_UP_VERIFICATION</td>
                </tr>
                <tr className={result.policy_rule_id === "MEDIUM_AMOUNT_ESCALATION" ? "active-rule" : ""}>
                  <td className="mono">MEDIUM_AMOUNT_ESCALATION</td>
                  <td>p ≥ 0.15 and amount ≥ ₹25,000</td>
                  <td className="mono">STEP_UP_VERIFICATION</td>
                </tr>
                <tr className={result.policy_rule_id === "MEDIUM_MONITOR" ? "active-rule" : ""}>
                  <td className="mono">MEDIUM_MONITOR</td>
                  <td>p ≥ 0.15</td>
                  <td className="mono">ALLOW_WITH_MONITORING</td>
                </tr>
                <tr className={result.policy_rule_id === "LOW_ALLOW" ? "active-rule" : ""}>
                  <td className="mono">LOW_ALLOW</td>
                  <td>(catch-all default)</td>
                  <td className="mono">ALLOW</td>
                </tr>
              </tbody>
            </table>
          </div>
        </AccordionSection>
      </div>
    </div>
  );
}
