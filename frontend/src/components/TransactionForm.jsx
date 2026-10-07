import { useState } from "react";
import { DEMO_SCENARIOS, emptyTransactionDraft } from "../data/sampleScenarios";
import { formatCurrency } from "../utils/presentation";
import { BoltIcon } from "./Icons";

const STATUS_OPTIONS  = ["success", "failed"];
const PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"];

export default function TransactionForm({ onSubmit, isSubmitting }) {
  const [mode, setMode] = useState("scenario");
  const [selectedId, setSelectedId] = useState("critical");
  const [draft, setDraft] = useState(emptyTransactionDraft());
  const [formError, setFormError] = useState(null);

  function updateDraft(field, value) {
    setDraft((d) => ({ ...d, [field]: value }));
  }

  const activeScenario = DEMO_SCENARIOS.find((s) => s.id === selectedId) || DEMO_SCENARIOS[0];

  function handleScenarioSelect(scenario) {
    setSelectedId(scenario.id);
  }

  function handleEvaluateClick() {
    if (mode === "scenario") {
      if (!activeScenario) return;
      onSubmit({
        transaction: activeScenario.transaction,
        prior_transactions: activeScenario.prior_transactions,
        source: "demo",
      });
    }
  }

  function handleManualSubmit(e) {
    e.preventDefault();
    setFormError(null);

    if (
      !draft.transaction_id.trim() ||
      !draft.customer_id.trim() ||
      !draft.merchant_id.trim() ||
      !draft.device_id.trim() ||
      !draft.geo_region.trim()
    ) {
      setFormError("Please fill in all required fields.");
      return;
    }
    const amount = Number(draft.amount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setFormError("Amount must be a positive number.");
      return;
    }
    if (!draft.timestamp || !draft.account_created) {
      setFormError("Please provide both the transaction time and the account creation date.");
      return;
    }

    const transaction = {
      ...draft,
      amount,
      timestamp: new Date(draft.timestamp).toISOString(),
      account_created: new Date(draft.account_created).toISOString(),
    };

    onSubmit({ transaction, prior_transactions: [], source: "manual" });
  }

  return (
    <div className="panel launcher-panel">
      <div className="panel-header">
        <span className="panel-title">NEW INVESTIGATION</span>
        <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>
          Launcher
        </span>
      </div>

      <div className="panel-body">
        {/* Mode toggle */}
        <div className="launcher-mode-toggle" role="group" aria-label="Investigation mode">
          <button
            type="button"
            className={`launcher-tab ${mode === "scenario" ? "active" : ""}`}
            onClick={() => setMode("scenario")}
            aria-pressed={mode === "scenario"}
          >
            Demo Scenarios
          </button>
          <button
            type="button"
            className={`launcher-tab ${mode === "manual" ? "active" : ""}`}
            onClick={() => setMode("manual")}
            aria-pressed={mode === "manual"}
          >
            Manual Entry
          </button>
        </div>

        {/* Demo scenarios mode */}
        {mode === "scenario" && (
          <div className="scenarios-container">
            <div className="scenarios-list" role="radiogroup" aria-label="Select test scenario">
              {DEMO_SCENARIOS.map((s) => {
                const isSelected = selectedId === s.id;
                const tier = s.id.toUpperCase();
                return (
                  <div
                    key={s.id}
                    role="radio"
                    aria-checked={isSelected}
                    tabIndex={0}
                    className={`scenario-item-card ${isSelected ? "selected" : ""} tier-${s.id}`}
                    onClick={() => handleScenarioSelect(s)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleScenarioSelect(s);
                      }
                    }}
                  >
                    <div className="scenario-item-top">
                      <span className={`scenario-tier-badge ${s.id}`}>{tier}</span>
                      <span className="scenario-amount">{formatCurrency(s.transaction.amount)}</span>
                    </div>

                    <div className="scenario-item-label">{s.label}</div>
                    <div className="scenario-item-desc">{s.description}</div>
                  </div>
                );
              })}
            </div>

            <button
              type="button"
              className="btn btn-primary btn-block evaluate-btn"
              onClick={handleEvaluateClick}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <span className="btn-spinner" aria-hidden="true" />
                  <span>Evaluating Investigation...</span>
                </>
              ) : (
                <>
                  <BoltIcon size={14} color="#080D18" />
                  <span>EVALUATE TRANSACTION</span>
                </>
              )}
            </button>
          </div>
        )}

        {/* Manual entry mode */}
        {mode === "manual" && (
          <form onSubmit={handleManualSubmit} aria-label="Manual transaction entry" className="manual-form">
            <p className="field-hint">
              Evaluated as a first-time transaction for this customer (0 prior transactions).
            </p>

            {formError && (
              <div className="form-error-banner" role="alert">
                <span>⚠️</span> {formError}
              </div>
            )}

            <div className="field-group">
              <label className="field-label" htmlFor="txn-transaction-id">Transaction ID</label>
              <input
                id="txn-transaction-id"
                className="field-input mono"
                placeholder="txn_test_001"
                value={draft.transaction_id}
                onChange={(e) => updateDraft("transaction_id", e.target.value)}
              />
            </div>

            <div className="field-row">
              <div className="field-group">
                <label className="field-label" htmlFor="txn-amount">Amount (INR)</label>
                <input
                  id="txn-amount"
                  className="field-input"
                  type="number"
                  min="0.01"
                  step="0.01"
                  placeholder="e.g. 5000"
                  value={draft.amount}
                  onChange={(e) => updateDraft("amount", e.target.value)}
                />
              </div>
              <div className="field-group">
                <label className="field-label" htmlFor="txn-payment-method">Payment Rail</label>
                <select
                  id="txn-payment-method"
                  className="field-select"
                  value={draft.payment_method}
                  onChange={(e) => updateDraft("payment_method", e.target.value)}
                >
                  {PAYMENT_METHODS.map((m) => (
                    <option key={m} value={m}>{m.toUpperCase()}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="field-row">
              <div className="field-group">
                <label className="field-label" htmlFor="txn-merchant-category">Category</label>
                <input
                  id="txn-merchant-category"
                  className="field-input"
                  placeholder="electronics"
                  value={draft.merchant_category}
                  onChange={(e) => updateDraft("merchant_category", e.target.value)}
                />
              </div>
              <div className="field-group">
                <label className="field-label" htmlFor="txn-status">Status</label>
                <select
                  id="txn-status"
                  className="field-select"
                  value={draft.status}
                  onChange={(e) => updateDraft("status", e.target.value)}
                >
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="field-row">
              <div className="field-group">
                <label className="field-label" htmlFor="txn-customer-id">Customer ID</label>
                <input
                  id="txn-customer-id"
                  className="field-input mono"
                  placeholder="cust_manual_01"
                  value={draft.customer_id}
                  onChange={(e) => updateDraft("customer_id", e.target.value)}
                />
              </div>
              <div className="field-group">
                <label className="field-label" htmlFor="txn-merchant-id">Merchant ID</label>
                <input
                  id="txn-merchant-id"
                  className="field-input mono"
                  placeholder="merch_01"
                  value={draft.merchant_id}
                  onChange={(e) => updateDraft("merchant_id", e.target.value)}
                />
              </div>
            </div>

            <div className="field-row">
              <div className="field-group">
                <label className="field-label" htmlFor="txn-device-id">Device ID</label>
                <input
                  id="txn-device-id"
                  className="field-input mono"
                  placeholder="dev_new_phone"
                  value={draft.device_id}
                  onChange={(e) => updateDraft("device_id", e.target.value)}
                />
              </div>
              <div className="field-group">
                <label className="field-label" htmlFor="txn-geo-region">Geo Region</label>
                <input
                  id="txn-geo-region"
                  className="field-input mono"
                  placeholder="region_15"
                  value={draft.geo_region}
                  onChange={(e) => updateDraft("geo_region", e.target.value)}
                />
              </div>
            </div>

            <div className="field-row">
              <div className="field-group">
                <label className="field-label" htmlFor="txn-timestamp">Txn Time</label>
                <input
                  id="txn-timestamp"
                  className="field-input"
                  type="datetime-local"
                  value={draft.timestamp}
                  onChange={(e) => updateDraft("timestamp", e.target.value)}
                />
              </div>
              <div className="field-group">
                <label className="field-label" htmlFor="txn-account-created">Account Created</label>
                <input
                  id="txn-account-created"
                  className="field-input"
                  type="date"
                  value={draft.account_created}
                  onChange={(e) => updateDraft("account_created", e.target.value)}
                />
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-block evaluate-btn"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <span className="btn-spinner" aria-hidden="true" />
                  <span>Evaluating Investigation...</span>
                </>
              ) : (
                <>
                  <BoltIcon size={14} color="#080D18" />
                  <span>EVALUATE TRANSACTION</span>
                </>
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
