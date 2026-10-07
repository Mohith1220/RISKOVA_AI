import React from "react";
import { formatPercent } from "../utils/presentation";

export default function EvidenceChain({ result }) {
  if (!result) return null;

  const invCtx = result.investigation_context;
  const behStatus = invCtx?.behavioral_assessment?.overall_status || "NOMINAL";
  const netStatus = invCtx?.network_assessment?.overall_status || "ISOLATED_TRANSACTION";
  const action = result.action;

  const statusFormat = {
    CRITICAL_ANOMALIES: { label: "CRITICAL ANOMALIES", color: "#FF4D5E", bg: "rgba(255, 77, 94, 0.12)" },
    ELEVATED_ANOMALIES: { label: "ELEVATED ANOMALIES", color: "#FF8A3D", bg: "rgba(255, 138, 61, 0.12)" },
    MODERATE_ANOMALIES: { label: "MODERATE DEVIATIONS", color: "#F5B942", bg: "rgba(245, 185, 66, 0.12)" },
    NOMINAL: { label: "NOMINAL BASELINE", color: "#27D17F", bg: "rgba(39, 209, 127, 0.12)" },
    INSUFFICIENT_HISTORY: { label: "COLD START (0 PRIORS)", color: "#8FA1B8", bg: "rgba(143, 161, 184, 0.12)" },
    CRITICAL_NETWORK_RISK: { label: "CRITICAL SHARING", color: "#FF4D5E", bg: "rgba(255, 77, 94, 0.12)" },
    ELEVATED_NETWORK_RISK: { label: "ELEVATED LINKS", color: "#FF8A3D", bg: "rgba(255, 138, 61, 0.12)" },
    MODERATE_NETWORK_RISK: { label: "MODERATE DIVERGENCE", color: "#F5B942", bg: "rgba(245, 185, 66, 0.12)" },
    ISOLATED_TRANSACTION: { label: "ISOLATED ENTITY", color: "#27D17F", bg: "rgba(39, 209, 127, 0.12)" },
  };

  const behMeta = statusFormat[behStatus] || statusFormat.NOMINAL;
  const netMeta = statusFormat[netStatus] || statusFormat.ISOLATED_TRANSACTION;

  return (
    <div className="panel evidence-chain-panel">
      <div className="panel-header">
        <span className="panel-title">INVESTIGATION EVIDENCE PIPELINE</span>
        <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>
          End-to-End Decisioning Chain
        </span>
      </div>

      <div className="panel-body">
        <div className="evidence-chain-grid">
          {/* Step 1: Model & SHAP */}
          <div className="chain-step-card">
            <div className="chain-step-header">
              <span className="chain-step-num">1</span>
              <span className="chain-step-title">MODEL &amp; SHAP</span>
            </div>
            <div className="chain-step-value mono">
              {formatPercent(result.fraud_probability)}
            </div>
            <div className="chain-step-desc">
              LightGBM inference with TreeSHAP attributions
            </div>
          </div>

          <div className="chain-arrow" aria-hidden="true">→</div>

          {/* Step 2: Behavioral Assessment */}
          <div className="chain-step-card">
            <div className="chain-step-header">
              <span className="chain-step-num">2</span>
              <span className="chain-step-title">BEHAVIORAL</span>
            </div>
            <div
              className="chain-step-badge"
              style={{ color: behMeta.color, background: behMeta.bg, border: `1px solid ${behMeta.color}40` }}
            >
              {behMeta.label}
            </div>
            <div className="chain-step-desc">
              6-dimensional baseline &amp; anomaly matrix
            </div>
          </div>

          <div className="chain-arrow" aria-hidden="true">→</div>

          {/* Step 3: Network Assessment */}
          <div className="chain-step-card">
            <div className="chain-step-header">
              <span className="chain-step-num">3</span>
              <span className="chain-step-title">NETWORK RISK</span>
            </div>
            <div
              className="chain-step-badge"
              style={{ color: netMeta.color, background: netMeta.bg, border: `1px solid ${netMeta.color}40` }}
            >
              {netMeta.label}
            </div>
            <div className="chain-step-desc">
              Cross-entity sharing &amp; rail profiling
            </div>
          </div>

          <div className="chain-arrow" aria-hidden="true">→</div>

          {/* Step 4: AI Investigator */}
          <div className="chain-step-card">
            <div className="chain-step-header">
              <span className="chain-step-num">4</span>
              <span className="chain-step-title">AI INVESTIGATOR</span>
            </div>
            <div
              className="chain-step-badge"
              style={{ color: "#27D17F", background: "rgba(39, 209, 127, 0.12)", border: "1px solid rgba(39, 209, 127, 0.35)" }}
            >
              ✓ GROUNDED BRIEF
            </div>
            <div className="chain-step-desc">
              Anti-hallucination grounded synthesis
            </div>
          </div>

          <div className="chain-arrow" aria-hidden="true">→</div>

          {/* Step 5: Policy Decision */}
          <div className="chain-step-card policy-highlight">
            <div className="chain-step-header">
              <span className="chain-step-num">5</span>
              <span className="chain-step-title">POLICY ACTION</span>
            </div>
            <div className="chain-step-action mono">
              {action}
            </div>
            <div className="chain-step-desc mono">
              {result.policy_rule_id}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
