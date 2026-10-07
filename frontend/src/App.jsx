import { useEffect, useState, useCallback } from "react";
import { api, ApiError } from "./api/client";
import TransactionForm from "./components/TransactionForm";
import RiskCaseHero from "./components/RiskCaseHero";
import EvidenceChain from "./components/EvidenceChain";
import AiInvestigatorCard from "./components/AiInvestigatorCard";
import DetailedEvidenceAccordion from "./components/DetailedEvidenceAccordion";
import AuditLogTable from "./components/AuditLogTable";
import ModelInfoPanel from "./components/ModelInfoPanel";
import ErrorBanner from "./components/ErrorBanner";
import { ShieldIcon, DocumentIcon } from "./components/Icons";
import "./styles/App.css";

export default function App() {
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState(null);

  const [modelInfo, setModelInfo] = useState(null);
  const [modelInfoError, setModelInfoError] = useState(null);
  const [modelInfoLoading, setModelInfoLoading] = useState(true);

  const [result, setResult] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const [currentPayload, setCurrentPayload] = useState(null);
  const [evaluateLoading, setEvaluateLoading] = useState(false);
  const [evaluateError, setEvaluateError] = useState(null);

  const [auditEntries, setAuditEntries] = useState(null);
  const [auditLoading, setAuditLoading] = useState(true);
  const [auditError, setAuditError] = useState(null);

  const [activeBottomTab, setActiveBottomTab] = useState("audit"); // 'audit' | 'model'

  const loadHealth = useCallback(async () => {
    try {
      const data = await api.getHealth();
      setHealth(data);
      setHealthError(null);
    } catch (err) {
      setHealth(null);
      setHealthError(err instanceof ApiError ? err.message : "Unknown error");
    }
  }, []);

  const loadModelInfo = useCallback(async () => {
    setModelInfoLoading(true);
    try {
      const data = await api.getModelInfo();
      setModelInfo(data);
      setModelInfoError(null);
    } catch (err) {
      setModelInfo(null);
      setModelInfoError(err instanceof ApiError ? err.message : "Unknown error");
    } finally {
      setModelInfoLoading(false);
    }
  }, []);

  const loadAuditLog = useCallback(async () => {
    setAuditLoading(true);
    try {
      const data = await api.getAuditLog(20);
      setAuditEntries(data);
      setAuditError(null);
    } catch (err) {
      setAuditError(err instanceof ApiError ? err.message : "Unknown error");
    } finally {
      setAuditLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHealth();
    loadModelInfo();
    loadAuditLog();
  }, [loadHealth, loadModelInfo, loadAuditLog]);

  async function handleEvaluate(payload) {
    setEvaluateLoading(true);
    setEvaluateError(null);
    setCurrentPayload(payload);
    try {
      const [evaluateResult, explainResult] = await Promise.all([
        api.evaluateTransaction(payload),
        api.explainTransaction(payload),
      ]);
      setResult(evaluateResult);
      setExplanation({
        header: evaluateResult.explanation_header,
        reasons: evaluateResult.reasons,
        contributions: explainResult.contributions,
        cold_start_context: evaluateResult.cold_start_context,
      });
      loadAuditLog();
    } catch (err) {
      setEvaluateError(
        err instanceof ApiError
          ? err.message
          : "Unexpected error while evaluating transaction."
      );
    } finally {
      setEvaluateLoading(false);
    }
  }

  const isModelReady = health?.status === "ok" && health?.model_loaded;
  const modelVersion = health?.model_version || modelInfo?.model_version || "lgbm_v1";
  const threshold = modelInfo?.decision_threshold ?? "0.08";

  // System status indicator
  let statusBadgeClass = "ready";
  let statusText = "READY FOR INVESTIGATION";

  if (evaluateLoading) {
    statusBadgeClass = "evaluating";
    statusText = "EVALUATION IN PROGRESS";
  } else if (healthError || !isModelReady) {
    statusBadgeClass = "offline";
    statusText = "MODEL OFFLINE";
  } else if (result) {
    statusBadgeClass = "operational";
    statusText = "● OPERATIONAL";
  } else {
    statusBadgeClass = "ready";
    statusText = "● OPERATIONAL";
  }

  return (
    <div className="app-shell">
      {/* ── Top Header ────────────────────────────────────────────── */}
      <header className="app-header">
        <div className="header-brand">
          <div className="brand-badge-row">
            <div className="brand-icon-wrapper">
              <ShieldIcon size={20} color="#4DA3FF" />
            </div>
            <h1 className="app-title">RISKOVA AI</h1>
          </div>
          <div className="app-tagline">
            Evidence-Driven Transaction Risk Intelligence
          </div>
          <div className="app-sub-tagline">
            AI-Assisted Transaction Risk Investigation &amp; Auditable Decisioning
          </div>
          <div className="app-event-badge" aria-label="Buildathon metadata">
            Razorpay AI Buildathon 2026 · AI Risk Manager
          </div>
        </div>

        <div className="header-status">
          <div className={`header-status-pill ${statusBadgeClass}`} role="status">
            <span className={`status-dot ${statusBadgeClass}`} aria-hidden="true" />
            <span className="status-label">{statusText}</span>
          </div>

          <div className="header-meta-row" aria-label="Model metrics">
            <span className="header-meta-item">
              Model: <strong className="mono">{modelVersion}</strong>
            </span>
            <span className="header-meta-item">
              Threshold: <strong className="mono">{threshold}</strong>
            </span>
            {modelInfo?.test_metrics_at_frozen_threshold && (
              <>
                <span className="header-meta-item">
                  Precision:{" "}
                  <strong className="mono">
                    {(modelInfo.test_metrics_at_frozen_threshold.precision * 100).toFixed(1)}%
                  </strong>
                </span>
                <span className="header-meta-item">
                  Recall:{" "}
                  <strong className="mono">
                    {(modelInfo.test_metrics_at_frozen_threshold.recall * 100).toFixed(1)}%
                  </strong>
                </span>
              </>
            )}
          </div>
        </div>
      </header>

      {/* ── Main Workspace Grid ───────────────────────────────────── */}
      <main className="main-workspace-grid">
        {/* Left Column: Investigation Launcher */}
        <aside className="workspace-left-col">
          <TransactionForm onSubmit={handleEvaluate} isSubmitting={evaluateLoading} />
        </aside>

        {/* Right Column: Risk Case & Investigation Workspace */}
        <section className="workspace-right-col">
          {evaluateError && (
            <ErrorBanner
              message="Evaluation Error"
              detail={evaluateError}
            />
          )}

          {!result && !evaluateLoading && (
            <div className="panel empty-workspace-panel">
              <div className="empty-workspace-content">
                <div className="empty-workspace-icon">
                  <DocumentIcon size={32} color="#4DA3FF" />
                </div>
                <h2 className="empty-workspace-title">Risk Operations Console Ready</h2>
                <p className="empty-workspace-desc">
                  Select an investigation scenario or enter transaction parameters on the left to synthesize an auditable <strong>Final Risk Case</strong> dossier.
                </p>

                <div className="empty-workspace-steps">
                  <div className="empty-step">
                    <span className="empty-step-num">1</span>
                    <span>ML Risk Assessment &amp; TreeSHAP Local Attributions</span>
                  </div>
                  <div className="empty-step">
                    <span className="empty-step-num">2</span>
                    <span>6-Dimensional Behavioral Anomaly Profiling</span>
                  </div>
                  <div className="empty-step">
                    <span className="empty-step-num">3</span>
                    <span>Cross-Entity Network &amp; Payment Rail Linkages</span>
                  </div>
                  <div className="empty-step">
                    <span className="empty-step-num">4</span>
                    <span>Anti-Hallucination AI Investigator Synthesis</span>
                  </div>
                  <div className="empty-step">
                    <span className="empty-step-num">5</span>
                    <span>Authoritative Deterministic Policy Action</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {(result || evaluateLoading) && (
            <div className="workspace-stack">
              {/* 1. Final Risk Case Hero */}
              <RiskCaseHero result={result} isLoading={evaluateLoading} />

              {/* 2. Visual Evidence Chain */}
              <EvidenceChain result={result} />

              {/* 3. AI Investigator Brief */}
              {result?.investigation_context?.ai_investigation_report && (
                <AiInvestigatorCard
                  report={result.investigation_context.ai_investigation_report}
                />
              )}

              {/* 4. Detailed Supporting Evidence Accordions */}
              <DetailedEvidenceAccordion
                result={result}
                explanation={explanation}
                payload={currentPayload}
              />
            </div>
          )}
        </section>
      </main>

      {/* ── Bottom Governance Panels ──────────────────────────────── */}
      <footer className="bottom-governance-section">
        <div className="governance-tabs-bar">
          <button
            type="button"
            className={`governance-tab-btn ${activeBottomTab === "audit" ? "active" : ""}`}
            onClick={() => setActiveBottomTab("audit")}
          >
            📋 Audit Governance Trail (SQLite)
          </button>
          <button
            type="button"
            className={`governance-tab-btn ${activeBottomTab === "model" ? "active" : ""}`}
            onClick={() => setActiveBottomTab("model")}
          >
            📊 Model &amp; Policy Benchmark
          </button>
        </div>

        <div className="governance-tab-content">
          {activeBottomTab === "audit" && (
            <AuditLogTable
              entries={auditEntries}
              isLoading={auditLoading}
              error={auditError}
              onRefresh={loadAuditLog}
            />
          )}

          {activeBottomTab === "model" && (
            <ModelInfoPanel
              modelInfo={modelInfo}
              isLoading={modelInfoLoading}
              error={modelInfoError}
            />
          )}
        </div>
      </footer>
    </div>
  );
}
