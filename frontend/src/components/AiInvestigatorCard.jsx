import React from "react";
import { BotIcon, CheckIcon, AlertIcon, InfoIcon, DocumentIcon } from "./Icons";

export default function AiInvestigatorCard({ report }) {
  if (!report) return null;

  const isGroundingPassed = report.grounding_verification_passed !== false;

  return (
    <div className="panel ai-brief-panel">
      <div className="ai-brief-header">
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div className="ai-brief-icon-wrapper">
            <BotIcon size={16} color="#4DA3FF" />
          </div>
          <div>
            <span className="ai-brief-title">AI INVESTIGATOR BRIEF</span>
            <span className="ai-brief-subtitle">AI-Assisted Evidence Synthesis</span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span className={`ai-grounding-badge ${isGroundingPassed ? "passed" : "fallback"}`}>
            {isGroundingPassed ? (
              <>
                <CheckIcon size={12} color="#27D17F" />
                <span>GROUNDING VERIFIED</span>
              </>
            ) : (
              <span>DETERMINISTIC FALLBACK</span>
            )}
          </span>
        </div>
      </div>

      <div className="panel-body">
        {/* Anti-hallucination / policy authority notice */}
        <div className="ai-disclaimer-banner">
          <InfoIcon size={14} color="#4DA3FF" />
          <span>
            <strong>AI-Assisted Investigation:</strong> AI synthesis is strictly grounded in evaluated evidence. Final action is governed by deterministic policy.
          </span>
        </div>

        {/* Executive Summary */}
        <div className="ai-executive-summary">
          <div className="ai-summary-label">EXECUTIVE SUMMARY</div>
          <div className="ai-summary-text">{report.executive_summary}</div>
        </div>

        {/* 2-Column Risk Drivers and Mitigating Factors */}
        <div className="ai-columns-grid">
          {/* Risk Drivers */}
          <div className="ai-drivers-card">
            <div className="ai-column-title drivers">
              <AlertIcon size={13} color="#FF8A3D" />
              <span>Primary Risk Drivers ({report.risk_drivers?.length || 0})</span>
            </div>

            {report.risk_drivers && report.risk_drivers.length > 0 ? (
              <div className="ai-drivers-list">
                {report.risk_drivers.map((d, i) => (
                  <div key={i} className="ai-driver-item">
                    <div className="ai-driver-item-header">
                      <span className="ai-driver-finding">{d.finding}</span>
                      <span className={`ai-severity-pill ${d.severity?.toLowerCase()}`}>
                        {d.severity}
                      </span>
                    </div>
                    <div className="ai-driver-evidence">
                      Evidence: {d.supporting_evidence}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="ai-empty-drivers">
                No anomalous risk drivers detected for this transaction.
              </div>
            )}
          </div>

          {/* Mitigating Factors */}
          <div className="ai-mitigating-card">
            <div className="ai-column-title mitigating">
              <CheckIcon size={13} color="#27D17F" />
              <span>Mitigating Factors &amp; Context</span>
            </div>

            {report.mitigating_factors && report.mitigating_factors.length > 0 ? (
              <ul className="ai-mitigating-list">
                {report.mitigating_factors.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            ) : (
              <div className="ai-empty-mitigating">
                No mitigating baseline factors available (e.g. cold start).
              </div>
            )}
          </div>
        </div>

        {/* Analyst Action Guidance */}
        {report.analyst_action_guidance && (
          <div className="ai-guidance-card">
            <DocumentIcon size={14} color="#8FA1B8" />
            <div>
              <strong style={{ color: "#F4F7FB" }}>Analyst Evidence Guidance: </strong>
              <span>{report.analyst_action_guidance}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
