import React from "react";

function formatCurrency(amount) {
  if (amount === null || amount === undefined || isNaN(amount)) return "—";
  return `₹${Number(amount).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function SeverityBadge({ severity }) {
  const sev = (severity || "INFO").toUpperCase();
  const styles = {
    CRITICAL: { background: "#fee2e2", color: "#991b1b", border: "1px solid #f87171" },
    HIGH: { background: "#fee2e2", color: "#991b1b", border: "1px solid #fca5a5" },
    MEDIUM: { background: "#fef3c7", color: "#92400e", border: "1px solid #fcd34d" },
    LOW: { background: "#e0f2fe", color: "#075985", border: "1px solid #7dd3fc" },
    INFO: { background: "#f3f4f6", color: "#374151", border: "1px solid #d1d5db" },
    NORMAL: { background: "#f0fdf4", color: "#166534", border: "1px solid #bbf7d0" },
  };

  const current = styles[sev] || styles.INFO;

  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "4px",
        fontSize: "11px",
        fontWeight: "600",
        letterSpacing: "0.02em",
        ...current,
      }}
    >
      {sev}
    </span>
  );
}

function OverallStatusBadge({ status }) {
  const statusStyles = {
    CRITICAL_ANOMALIES: { background: "#fef2f2", color: "#991b1b", border: "1px solid #f87171", label: "🚨 CRITICAL BEHAVIORAL ANOMALIES" },
    ELEVATED_ANOMALIES: { background: "#fffbeb", color: "#b45309", border: "1px solid #fcd34d", label: "⚠️ ELEVATED BEHAVIORAL ANOMALIES" },
    MODERATE_ANOMALIES: { background: "#fefce8", color: "#854d0e", border: "1px solid #fef08a", label: "⚡ MODERATE BEHAVIORAL DEVIATION" },
    NOMINAL: { background: "#f0fdf4", color: "#15803d", border: "1px solid #86efac", label: "✓ NOMINAL BEHAVIORAL PATTERNS" },
    INSUFFICIENT_HISTORY: { background: "#f8fafc", color: "#475569", border: "1px solid #cbd5e1", label: "⚠️ INSUFFICIENT HISTORY (COLD START)" },
  };

  const item = statusStyles[status] || statusStyles.INSUFFICIENT_HISTORY;

  return (
    <span
      style={{
        fontSize: "11.5px",
        fontWeight: "700",
        padding: "4px 10px",
        borderRadius: "4px",
        letterSpacing: "0.02em",
        ...item,
      }}
    >
      {item.label}
    </span>
  );
}

function NetworkStatusBadge({ status }) {
  const statusStyles = {
    CRITICAL_NETWORK_RISK: { background: "#fef2f2", color: "#991b1b", border: "1px solid #f87171", label: "🚨 CRITICAL NETWORK RISK" },
    ELEVATED_NETWORK_RISK: { background: "#fffbeb", color: "#b45309", border: "1px solid #fcd34d", label: "⚠️ ELEVATED NETWORK RISK" },
    MODERATE_NETWORK_RISK: { background: "#fefce8", color: "#854d0e", border: "1px solid #fef08a", label: "⚡ MODERATE ENTITY DIVERGENCE" },
    ISOLATED_TRANSACTION: { background: "#f0fdf4", color: "#15803d", border: "1px solid #86efac", label: "✓ ISOLATED TRANSACTION" },
    INSUFFICIENT_HISTORY: { background: "#f8fafc", color: "#475569", border: "1px solid #cbd5e1", label: "⚠️ INSUFFICIENT HISTORY" },
  };

  const item = statusStyles[status] || statusStyles.ISOLATED_TRANSACTION;

  return (
    <span
      style={{
        fontSize: "11px",
        fontWeight: "700",
        padding: "3px 8px",
        borderRadius: "4px",
        letterSpacing: "0.02em",
        ...item,
      }}
    >
      {item.label}
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


export default function InvestigationPanel({ investigationContext, riskCase, isLoading }) {
  if (isLoading) {
    return (
      <div className="panel" aria-busy="true" aria-label="Investigation context loading">
        <div className="panel-header">
          <span className="panel-title">Transaction Investigation Context</span>
        </div>
        <div className="panel-body">
          <div className="skeleton" style={{ height: 20, width: "50%", marginBottom: 12 }} />
          <div className="skeleton" style={{ height: 60, marginBottom: 12 }} />
          <div className="skeleton" style={{ height: 80 }} />
        </div>
      </div>
    );
  }

  if (!investigationContext) {
    return (
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Transaction Investigation Context</span>
        </div>
        <div className="empty-state">
          Investigation context and behavioral anomaly assessment will appear here after evaluation.
        </div>
      </div>
    );
  }

  const { status, customer_summary, behavioral_signals, key_findings, behavioral_assessment, customer_id } =
    investigationContext;

  const isColdStart = status === "INSUFFICIENT_HISTORY";
  const anomalies = behavioral_assessment?.anomalies || [];
  const overallStatus = behavioral_assessment?.overall_status || status;

  return (
    <div className="panel" aria-live="polite">
      <div className="panel-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
        <div>
          <span className="panel-title">Transaction Investigation Context & Risk Case</span>
        </div>
        <OverallStatusBadge status={overallStatus} />
      </div>

      <div className="panel-body">
        {/* Phase 5: Final Risk Case Dossier Header */}
        {riskCase && (
          <div
            style={{
              marginBottom: "16px",
              background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
              color: "#ffffff",
              borderRadius: "8px",
              padding: "12px 16px",
              boxShadow: "0 2px 4px rgba(0,0,0,0.12)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px", marginBottom: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "14px" }}>📁</span>
                <span style={{ fontSize: "13px", fontWeight: "700", letterSpacing: "0.03em" }}>
                  FINAL RISK CASE DOSSIER · {riskCase.case_id}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "11px", color: "#94a3b8" }}>Rule: {riskCase.policy_decision.policy_rule_id}</span>
                <span
                  style={{
                    fontSize: "11.5px",
                    fontWeight: "700",
                    padding: "3px 8px",
                    borderRadius: "4px",
                    background: riskCase.policy_decision.action === "BLOCK"
                      ? "#ef4444"
                      : riskCase.policy_decision.action === "STEP_UP"
                      ? "#f97316"
                      : riskCase.policy_decision.action === "MONITOR"
                      ? "#eab308"
                      : "#22c55e",
                    color: "#ffffff",
                  }}
                >
                  {riskCase.policy_decision.action}
                </span>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "8px", fontSize: "11px", color: "#cbd5e1" }}>
              <div>
                <span style={{ color: "#94a3b8" }}>Txn ID: </span>
                <span className="mono" style={{ color: "#ffffff", fontWeight: "600" }}>{riskCase.transaction_facts.transaction_id}</span>
              </div>
              <div>
                <span style={{ color: "#94a3b8" }}>Amount: </span>
                <span style={{ color: "#ffffff", fontWeight: "600" }}>{formatCurrency(riskCase.transaction_facts.amount)}</span>
              </div>
              <div>
                <span style={{ color: "#94a3b8" }}>Model Prob: </span>
                <span style={{ color: "#ffffff", fontWeight: "600" }}>{(riskCase.model_assessment.fraud_probability * 100).toFixed(1)}%</span>
              </div>
              <div>
                <span style={{ color: "#94a3b8" }}>Score: </span>
                <span style={{ color: "#ffffff", fontWeight: "600" }}>{riskCase.model_assessment.risk_score}/100 ({riskCase.model_assessment.risk_category})</span>
              </div>
            </div>
          </div>
        )}

        {/* Phase 4: AI Risk Investigator Report */}
        {investigationContext.ai_investigation_report && (
          <div
            style={{
              marginBottom: "18px",
              background: "#ffffff",
              border: "1px solid #cbd5e1",
              borderRadius: "8px",
              boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "10px 14px",
                background: "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)",
                borderBottom: "1px solid #e2e8f0",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "14px" }}>🤖</span>
                <span style={{ fontSize: "12.5px", fontWeight: "700", color: "#0f172a", letterSpacing: "0.02em", textTransform: "uppercase" }}>
                  AI Risk Investigator Brief
                </span>
              </div>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: "600",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  background: investigationContext.ai_investigation_report.status === "GENERATED" ? "#dcfce7" : "#e2e8f0",
                  color: investigationContext.ai_investigation_report.status === "GENERATED" ? "#166534" : "#334155",
                  border: "1px solid #cbd5e1",
                }}
              >
                {investigationContext.ai_investigation_report.status === "GENERATED" ? "✨ AI Synthesized" : "⚡ Grounded Synthesis"}
              </span>
            </div>

            <div style={{ padding: "12px 14px" }}>
              {/* Executive Summary */}
              <div style={{ fontSize: "13px", color: "#1e293b", lineHeight: "1.5", marginBottom: "12px", fontWeight: "500" }}>
                {investigationContext.ai_investigation_report.executive_summary}
              </div>

              {/* Drivers & Mitigating Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px", marginBottom: "12px" }}>
                {/* Risk Drivers */}
                <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "6px", padding: "10px" }}>
                  <div style={{ fontSize: "11.5px", fontWeight: "700", color: "#991b1b", textTransform: "uppercase", marginBottom: "6px", display: "flex", alignItems: "center", gap: "4px" }}>
                    <span>🚨</span> Key Risk Drivers ({investigationContext.ai_investigation_report.risk_drivers.length})
                  </div>
                  {investigationContext.ai_investigation_report.risk_drivers.length > 0 ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                      {investigationContext.ai_investigation_report.risk_drivers.map((d, idx) => (
                        <div key={idx} style={{ fontSize: "12px", color: "#450a0a", background: "#ffffff", padding: "6px 8px", borderRadius: "4px", border: "1px solid #fee2e2" }}>
                          <div style={{ fontWeight: "600", marginBottom: "2px", display: "flex", justifyContent: "space-between" }}>
                            <span>{d.finding}</span>
                            <span style={{ fontSize: "10px", padding: "1px 4px", borderRadius: "3px", background: "#fef2f2", color: "#b91c1c", border: "1px solid #fca5a5" }}>{d.severity}</span>
                          </div>
                          <div style={{ fontSize: "11px", color: "#7f1d1d" }}>Evidence: {d.supporting_evidence}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: "12px", color: "#7f1d1d", fontStyle: "italic" }}>
                      No active anomalous risk drivers detected.
                    </div>
                  )}
                </div>

                {/* Mitigating Factors */}
                <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "6px", padding: "10px" }}>
                  <div style={{ fontSize: "11.5px", fontWeight: "700", color: "#166534", textTransform: "uppercase", marginBottom: "6px", display: "flex", alignItems: "center", gap: "4px" }}>
                    <span>✓</span> Mitigating Factors & Context
                  </div>
                  <ul style={{ margin: "0", paddingLeft: "16px", fontSize: "12px", color: "#14532d", lineHeight: "1.4" }}>
                    {investigationContext.ai_investigation_report.mitigating_factors.map((m, idx) => (
                      <li key={idx} style={{ marginBottom: "4px" }}>{m}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Analyst Action Guidance */}
              <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "6px", padding: "8px 12px", display: "flex", alignItems: "flex-start", gap: "8px" }}>
                <span style={{ fontSize: "13px" }}>📋</span>
                <div style={{ fontSize: "12px", color: "#334155", lineHeight: "1.4" }}>
                  <span style={{ fontWeight: "700", color: "#0f172a" }}>Analyst Evidence Guidance: </span>
                  {investigationContext.ai_investigation_report.analyst_action_guidance}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Customer Baseline Summary */}
        <div style={{ marginBottom: "16px" }}>
          <div style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Customer Profile & Baseline ({customer_id})
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: "8px",
              background: "var(--bg-subtle, #f8fafc)",
              border: "1px solid var(--border-color, #e2e8f0)",
              borderRadius: "6px",
              padding: "10px 12px",
            }}
          >

            <div>
              <div style={{ fontSize: "11px", color: "#64748b" }}>Prior Txn Count</div>
              <div style={{ fontSize: "13px", fontWeight: "600", color: "#0f172a" }}>
                {customer_summary.prior_transaction_count}
              </div>
            </div>
            <div>
              <div style={{ fontSize: "11px", color: "#64748b" }}>Historical Avg Amount</div>
              <div style={{ fontSize: "13px", fontWeight: "600", color: "#0f172a" }}>
                {formatCurrency(customer_summary.historical_avg_amount)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: "11px", color: "#64748b" }}>Amount Range</div>
              <div style={{ fontSize: "12px", fontWeight: "500", color: "#0f172a" }}>
                {customer_summary.historical_min_amount !== null
                  ? `${formatCurrency(customer_summary.historical_min_amount)} – ${formatCurrency(customer_summary.historical_max_amount)}`
                  : "—"}
              </div>
            </div>
            <div>
              <div style={{ fontSize: "11px", color: "#64748b" }}>Account Age</div>
              <div style={{ fontSize: "13px", fontWeight: "600", color: "#0f172a" }}>
                {customer_summary.account_age_days} days
              </div>
            </div>
            <div>
              <div style={{ fontSize: "11px", color: "#64748b" }}>Known Devices / Regions</div>
              <div style={{ fontSize: "12px", fontWeight: "500", color: "#0f172a" }}>
                {customer_summary.known_devices.length} device(s) · {customer_summary.known_geos.length} region(s)
              </div>
            </div>
          </div>
        </div>

        {/* Phase 2: Behavioral Anomaly Assessment Matrix */}
        <div style={{ marginBottom: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <div style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
              Behavioral Anomaly Assessment (Phase 2)
            </div>
            {behavioral_assessment && (
              <span style={{ fontSize: "11px", color: "#64748b", fontWeight: "500" }}>
                {behavioral_assessment.anomaly_count} of {anomalies.length} dimension(s) anomalous
              </span>
            )}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "8px" }}>
            {anomalies.map((a) => (
              <div
                key={a.dimension}
                style={{
                  background: a.is_anomaly ? "#ffffff" : "#fcfcfd",
                  border: a.is_anomaly ? (a.severity === "CRITICAL" ? "1px solid #fca5a5" : "1px solid #fed7aa") : "1px solid #e2e8f0",
                  borderLeft: a.is_anomaly ? (a.severity === "CRITICAL" ? "4px solid #ef4444" : "4px solid #f97316") : "4px solid #cbd5e1",
                  borderRadius: "6px",
                  padding: "10px 12px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <div style={{ fontSize: "12.5px", fontWeight: "600", color: "#0f172a" }}>
                    {DIMENSION_LABELS[a.dimension] || a.dimension}
                  </div>
                  <SeverityBadge severity={a.severity} />
                </div>

                <div style={{ fontSize: "12px", color: "#334155", marginBottom: "6px", lineHeight: "1.4" }}>
                  {a.description}
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                    gap: "6px",
                    background: "#f8fafc",
                    border: "1px solid #f1f5f9",
                    borderRadius: "4px",
                    padding: "6px 8px",
                    fontSize: "11px",
                  }}
                >
                  <div>
                    <span style={{ color: "#64748b", fontWeight: "600" }}>Baseline: </span>
                    <span style={{ color: "#1e293b" }}>{a.baseline_summary}</span>
                  </div>
                  <div>
                    <span style={{ color: "#64748b", fontWeight: "600" }}>Observed: </span>
                    <span style={{ color: a.is_anomaly ? "#b91c1c" : "#166534", fontWeight: a.is_anomaly ? "600" : "500" }}>
                      {a.observed_summary}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Phase 3: Network & Related Entity Links */}
        {investigationContext.network_assessment && (
          <div style={{ marginBottom: "16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <div style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Network & Related Entity Links (Phase 3)
              </div>
              <NetworkStatusBadge status={investigationContext.network_assessment.overall_status} />
            </div>

            <div style={{ fontSize: "12px", color: "#475569", marginBottom: "8px" }}>
              {investigationContext.network_assessment.summary}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "8px" }}>
              {investigationContext.network_assessment.links.map((link, idx) => (
                <div
                  key={idx}
                  style={{
                    background: link.severity !== "NORMAL" ? "#ffffff" : "#fcfcfd",
                    border: link.severity === "CRITICAL"
                      ? "1px solid #fca5a5"
                      : link.severity === "HIGH"
                      ? "1px solid #fed7aa"
                      : link.severity === "MEDIUM"
                      ? "1px solid #fef08a"
                      : "1px solid #e2e8f0",
                    borderLeft: link.severity === "CRITICAL"
                      ? "4px solid #ef4444"
                      : link.severity === "HIGH"
                      ? "4px solid #f97316"
                      : link.severity === "MEDIUM"
                      ? "4px solid #eab308"
                      : "4px solid #cbd5e1",
                    borderRadius: "6px",
                    padding: "10px 12px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                    <div style={{ fontSize: "12.5px", fontWeight: "600", color: "#0f172a" }}>
                      {NETWORK_LINK_LABELS[link.link_type] || link.link_type}
                    </div>
                    <SeverityBadge severity={link.severity} />
                  </div>

                  <div style={{ fontSize: "12px", color: "#334155", lineHeight: "1.4" }}>
                    {link.description}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Key Investigation Findings */}
        <div>
          <div style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Summary of Evidence Findings
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {key_findings.map((f, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "10px",
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: "6px",
                  padding: "8px 12px",
                }}
              >
                <div style={{ marginTop: "2px" }}>
                  <SeverityBadge severity={f.severity} />
                </div>
                <div style={{ flex: 1, fontSize: "12.5px", color: "#1e293b", lineHeight: "1.45" }}>
                  {f.description}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

