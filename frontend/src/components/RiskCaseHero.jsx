import React from "react";
import { formatPercent, formatCurrency } from "../utils/presentation";
import { CaseIcon, RuleIcon, CheckIcon, CrossIcon, AlertIcon } from "./Icons";

function ActionBadge({ action }) {
  const styles = {
    BLOCK: { bg: "rgba(255, 77, 94, 0.15)", text: "#FF4D5E", border: "rgba(255, 77, 94, 0.40)", icon: <CrossIcon size={13} color="#FF4D5E" />, label: "BLOCK" },
    STEP_UP_VERIFICATION: { bg: "rgba(255, 138, 61, 0.15)", text: "#FF8A3D", border: "rgba(255, 138, 61, 0.40)", icon: <AlertIcon size={13} color="#FF8A3D" />, label: "STEP-UP VERIFICATION" },
    ALLOW_WITH_MONITORING: { bg: "rgba(245, 185, 66, 0.15)", text: "#F5B942", border: "rgba(245, 185, 66, 0.40)", icon: <AlertIcon size={13} color="#F5B942" />, label: "ALLOW WITH MONITORING" },
    ALLOW: { bg: "rgba(39, 209, 127, 0.15)", text: "#27D17F", border: "rgba(39, 209, 127, 0.40)", icon: <CheckIcon size={13} color="#27D17F" />, label: "ALLOW" },
  };

  const current = styles[action] || { bg: "rgba(143, 161, 184, 0.12)", text: "#8FA1B8", border: "#26344A", icon: <RuleIcon size={13} />, label: action };

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "6px 14px",
        borderRadius: "6px",
        background: current.bg,
        color: current.text,
        border: `1.5px solid ${current.border}`,
        fontWeight: "700",
        fontSize: "12.5px",
        letterSpacing: "0.03em",
      }}
    >
      <span>{current.icon}</span>
      <span>{current.label}</span>
    </div>
  );
}

function RiskCategoryBadge({ category }) {
  const cat = (category || "LOW").toUpperCase();
  const styles = {
    CRITICAL: { bg: "#FF4D5E", text: "#080D18" },
    HIGH: { bg: "#FF8A3D", text: "#080D18" },
    MEDIUM: { bg: "#F5B942", text: "#080D18" },
    LOW: { bg: "#27D17F", text: "#080D18" },
  };
  const current = styles[cat] || styles.LOW;

  return (
    <span
      style={{
        padding: "2px 7px",
        borderRadius: "3px",
        background: current.bg,
        color: current.text,
        fontSize: "10.5px",
        fontWeight: "700",
        letterSpacing: "0.04em",
      }}
    >
      {cat}
    </span>
  );
}

export default function RiskCaseHero({ result, isLoading }) {
  if (isLoading) {
    return (
      <div className="panel risk-hero-panel" aria-busy="true">
        <div className="panel-header">
          <span className="panel-title">FINAL RISK CASE</span>
        </div>
        <div className="panel-body">
          <div className="skeleton" style={{ height: 28, width: "50%", marginBottom: 12 }} />
          <div className="skeleton" style={{ height: 80, marginBottom: 12 }} />
          <div className="skeleton" style={{ height: 40 }} />
        </div>
      </div>
    );
  }

  if (!result) return null;

  const riskCase = result.risk_case;
  const caseId = riskCase?.case_id || `CASE-${result.request_id?.slice(0, 8).toUpperCase()}`;
  const txnId = result.transaction_id || riskCase?.transaction_facts?.transaction_id;
  const action = result.action;
  const prob = result.fraud_probability;
  const score = result.risk_score;
  const category = result.risk_category;
  const ruleId = result.policy_rule_id;
  const reason = result.policy_reason;
  const modelVersion = result.model_version;
  const amount = riskCase?.transaction_facts?.amount;

  return (
    <div className="panel risk-hero-panel" aria-live="polite">
      <div className="risk-hero-header">
        <div className="risk-hero-title-group">
          <div className="risk-hero-case-badge">
            <CaseIcon size={14} color="#4DA3FF" />
            <span className="mono risk-hero-case-id">{caseId}</span>
          </div>
          <div className="risk-hero-txn-id">
            <span style={{ color: "var(--text-tertiary)" }}>TXN: </span>
            <span className="mono">{txnId}</span>
            {amount !== undefined && (
              <span className="risk-hero-amount"> · {formatCurrency(amount)}</span>
            )}
          </div>
        </div>

        <div>
          <ActionBadge action={action} />
        </div>
      </div>

      <div className="risk-hero-body">
        {/* 4 Metric cards */}
        <div className="risk-metric-grid">
          <div className="risk-metric-card">
            <div className="risk-metric-label">FRAUD PROBABILITY</div>
            <div className="risk-metric-val mono accent">{formatPercent(prob)}</div>
            <div className="risk-metric-sub">Model inference score</div>
          </div>

          <div className="risk-metric-card">
            <div className="risk-metric-label">RISK CATEGORY</div>
            <div className="risk-metric-val" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <RiskCategoryBadge category={category} />
              <span style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-primary)" }}>
                {score}/100
              </span>
            </div>
            <div className="risk-metric-sub">Normalized risk rating</div>
          </div>

          <div className="risk-metric-card">
            <div className="risk-metric-label">AUTHORITATIVE ACTION</div>
            <div className="risk-metric-val mono" style={{ fontSize: "13.5px", color: "var(--text-primary)" }}>
              {action}
            </div>
            <div className="risk-metric-sub mono">{ruleId}</div>
          </div>

          <div className="risk-metric-card">
            <div className="risk-metric-label">MODEL &amp; THRESHOLD</div>
            <div className="risk-metric-val mono" style={{ fontSize: "13px" }}>
              {modelVersion}
            </div>
            <div className="risk-metric-sub mono">Decision Cutoff: {result.threshold}</div>
          </div>
        </div>

        {/* Deterministic policy banner */}
        <div className="risk-policy-banner">
          <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
            <div style={{ marginTop: "2px" }}>
              <RuleIcon size={15} color="#4DA3FF" />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                <span style={{ fontWeight: "700", color: "var(--text-primary)", fontSize: "12px" }}>
                  DETERMINISTIC POLICY:
                </span>
                <span className="mono" style={{ fontSize: "12px", color: "var(--accent)", fontWeight: "600" }}>
                  {ruleId}
                </span>
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px", lineHeight: "1.4" }}>
                {reason}
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "4px" }}>
                <em>Final action is governed by deterministic policy.</em>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
