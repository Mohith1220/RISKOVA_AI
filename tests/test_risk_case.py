"""
Tests for Phase 5: Final Auditable Risk Case.

Verifies that the unified RiskCase artifact assembles all grounded evidence
from Phases 1–4 without recalculation, maintains exact consistency with
authoritative decision and model outputs, preserves policy isolation,
and is delivered through the API.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime, timezone

from backend.schemas.transaction import TransactionInput, RiskRequest
from backend.services.risk_service import (
    _build_feature_row,
    build_investigation_context,
    evaluate_full,
    build_risk_case,
)


def _txn(
    txn_id="txn_case_01",
    customer_id="cust_case_01",
    amount=500.0,
    device_id="dev_case_known",
    merchant_id="merch_01",
    geo_region="region_01",
    payment_method="card",
    timestamp="2026-05-20T12:00:00Z",
    status="success",
    account_created="2025-01-01T00:00:00Z",
):
    return TransactionInput(
        transaction_id=txn_id,
        customer_id=customer_id,
        merchant_id=merchant_id,
        merchant_category="electronics",
        timestamp=datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
        amount=amount,
        device_id=device_id,
        geo_region=geo_region,
        payment_method=payment_method,
        status=status,
        account_created=datetime.fromisoformat(account_created.replace("Z", "+00:00")),
    )


def _priors(customer_id="cust_case_01", n=5, avg_amt=500.0, device="dev_case_known", geo="region_01"):
    return [
        TransactionInput(
            transaction_id=f"prior_case_{i}",
            customer_id=customer_id,
            merchant_id="merch_01",
            merchant_category="electronics",
            timestamp=datetime.fromisoformat(f"2026-05-1{i}T10:00:00+00:00"),
            amount=avg_amt,
            device_id=device,
            geo_region=geo,
            payment_method="card",
            status="success",
            account_created=datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
        )
        for i in range(n)
    ]


class TestRiskCaseAssemblyAndConsistency:
    """Unit tests for RiskCase structure, assembly, and consistency."""

    def test_risk_case_construction(self, client):
        bundle = client.app.state.model_bundle
        priors = _priors(n=5, avg_amt=500.0)
        curr = _txn(amount=520.0)
        req = RiskRequest(transaction=curr, prior_transactions=priors, source="manual")

        decision, explanation, req_id, prior_count, err, ctx = evaluate_full(bundle, req)
        risk_case = build_risk_case(req, decision, explanation, ctx, req_id, audit_persisted=True)

        assert risk_case.case_id.startswith("CASE-")
        assert risk_case.transaction_facts.transaction_id == curr.transaction_id
        assert risk_case.transaction_facts.amount == curr.amount
        assert risk_case.model_assessment.fraud_probability == decision.fraud_probability
        assert risk_case.policy_decision.action == decision.action
        assert risk_case.audit_metadata.request_id == req_id
        assert risk_case.audit_metadata.audit_persisted is True
        assert risk_case.customer_context.prior_transaction_count == 5
        assert risk_case.behavioral_assessment is not None
        assert risk_case.network_assessment is not None
        assert risk_case.ai_investigation is not None

    def test_risk_case_probability_and_score_consistency(self, client):
        bundle = client.app.state.model_bundle
        priors = _priors(n=5, avg_amt=500.0)
        curr = _txn(amount=45000.0)  # Surge
        req = RiskRequest(transaction=curr, prior_transactions=priors)

        decision, explanation, req_id, prior_count, err, ctx = evaluate_full(bundle, req)
        risk_case = build_risk_case(req, decision, explanation, ctx, req_id)

        assert risk_case.model_assessment.fraud_probability == decision.fraud_probability
        assert risk_case.model_assessment.risk_score == decision.risk_score
        assert risk_case.model_assessment.risk_category == decision.risk_category
        assert risk_case.model_assessment.decision_threshold == decision.threshold

    def test_risk_case_policy_action_and_rule_consistency(self, client):
        bundle = client.app.state.model_bundle
        priors = _priors(n=5, avg_amt=500.0)
        curr = _txn(amount=510.0)
        req = RiskRequest(transaction=curr, prior_transactions=priors)

        decision, explanation, req_id, prior_count, err, ctx = evaluate_full(bundle, req)
        risk_case = build_risk_case(req, decision, explanation, ctx, req_id)

        assert risk_case.policy_decision.action == decision.action
        assert risk_case.policy_decision.policy_rule_id == decision.policy_rule_id
        assert risk_case.policy_decision.policy_reason == decision.policy_reason

    def test_risk_case_shap_reasons_consistency(self, client):
        bundle = client.app.state.model_bundle
        priors = _priors(n=5, avg_amt=500.0)
        curr = _txn(amount=3500.0)
        req = RiskRequest(transaction=curr, prior_transactions=priors)

        decision, explanation, req_id, prior_count, err, ctx = evaluate_full(bundle, req)
        risk_case = build_risk_case(req, decision, explanation, ctx, req_id)

        expected_reasons = explanation.get("reasons", []) if explanation else []
        assert risk_case.model_assessment.top_shap_reasons == expected_reasons

    def test_risk_case_behavioral_and_network_consistency(self, client):
        bundle = client.app.state.model_bundle
        priors = _priors(n=5, avg_amt=500.0)
        curr = _txn(amount=500.0, device_id="dev_novel_01")
        req = RiskRequest(transaction=curr, prior_transactions=priors)

        decision, explanation, req_id, prior_count, err, ctx = evaluate_full(bundle, req)
        risk_case = build_risk_case(req, decision, explanation, ctx, req_id)

        assert risk_case.behavioral_assessment.overall_status == ctx["behavioral_assessment"]["overall_status"]
        assert risk_case.network_assessment.overall_status == ctx["network_assessment"]["overall_status"]
        assert len(risk_case.behavioral_assessment.anomalies) == len(ctx["behavioral_assessment"]["anomalies"])
        assert len(risk_case.network_assessment.links) == len(ctx["network_assessment"]["links"])

    def test_risk_case_ai_report_consistency(self, client):
        bundle = client.app.state.model_bundle
        priors = _priors(n=5, avg_amt=500.0)
        curr = _txn(amount=500.0)
        req = RiskRequest(transaction=curr, prior_transactions=priors)

        decision, explanation, req_id, prior_count, err, ctx = evaluate_full(bundle, req)
        risk_case = build_risk_case(req, decision, explanation, ctx, req_id)

        ai_ctx = ctx["ai_investigation_report"]
        assert risk_case.ai_investigation.executive_summary == ai_ctx.executive_summary
        assert risk_case.ai_investigation.status == ai_ctx.status
        assert risk_case.ai_investigation.grounding_verification_passed is True

    def test_risk_case_cold_start(self, client):
        bundle = client.app.state.model_bundle
        curr = _txn(amount=1000.0)
        req = RiskRequest(transaction=curr, prior_transactions=[], source="manual")

        decision, explanation, req_id, prior_count, err, ctx = evaluate_full(bundle, req)
        risk_case = build_risk_case(req, decision, explanation, ctx, req_id)

        assert risk_case.customer_context.prior_transaction_count == 0
        assert risk_case.behavioral_assessment.overall_status == "INSUFFICIENT_HISTORY"
        assert risk_case.network_assessment.overall_status == "INSUFFICIENT_HISTORY"
        assert "first-time" in risk_case.ai_investigation.executive_summary.lower() or "cold-start" in risk_case.ai_investigation.executive_summary.lower()

    def test_risk_case_audit_metadata_consistency(self, client):
        bundle = client.app.state.model_bundle
        curr = _txn(amount=500.0)
        req = RiskRequest(transaction=curr, prior_transactions=[], source="demo")

        decision, explanation, req_id, prior_count, err, ctx = evaluate_full(bundle, req)
        risk_case = build_risk_case(req, decision, explanation, ctx, req_id, audit_persisted=True, audit_error=None)

        assert risk_case.audit_metadata.request_id == req_id
        assert risk_case.audit_metadata.source == "demo"
        assert risk_case.audit_metadata.audit_persisted is True
        assert risk_case.audit_metadata.audit_error is None

    def test_risk_case_policy_isolation(self, client):
        """Proof that constructing RiskCase does not mutate decision record."""
        bundle = client.app.state.model_bundle
        curr = _txn(amount=500.0)
        req = RiskRequest(transaction=curr, prior_transactions=[])

        decision, explanation, req_id, prior_count, err, ctx = evaluate_full(bundle, req)
        orig_action = decision.action
        orig_prob = decision.fraud_probability

        risk_case = build_risk_case(req, decision, explanation, ctx, req_id)

        assert decision.action == orig_action
        assert decision.fraud_probability == orig_prob
        assert risk_case.policy_decision.action == orig_action


class TestRiskCaseAPIIntegration:
    """API integration tests verifying that /risk/evaluate delivers complete RiskCase."""

    def test_api_risk_evaluate_returns_risk_case(self, client):
        priors = [
            dict(
                transaction_id=f"api_case_{i}", customer_id="cust_case_api", merchant_id="merch_01",
                merchant_category="electronics", timestamp=f"2026-05-1{i}T10:00:00Z", amount=450.0,
                device_id="dev_case_api", geo_region="region_01", payment_method="card", status="success",
                account_created="2025-01-01T00:00:00Z",
            )
            for i in range(3)
        ]
        payload = {
            "transaction": {
                "transaction_id": "api_case_curr",
                "customer_id": "cust_case_api",
                "merchant_id": "merch_01",
                "merchant_category": "electronics",
                "timestamp": "2026-05-20T12:00:00Z",
                "amount": 480.0,
                "device_id": "dev_case_api",
                "geo_region": "region_01",
                "payment_method": "card",
                "status": "success",
                "account_created": "2025-01-01T00:00:00Z",
            },
            "prior_transactions": priors,
            "source": "manual",
        }
        res = client.post("/risk/evaluate", json=payload)
        assert res.status_code == 200
        data = res.json()

        # Verify all existing top-level fields for backwards compatibility
        assert data["request_id"] != ""
        assert data["transaction_id"] == "api_case_curr"
        assert "action" in data
        assert "fraud_probability" in data
        assert "investigation_context" in data

        # Verify RiskCase payload
        assert "risk_case" in data
        rc = data["risk_case"]
        assert rc["case_id"].startswith("CASE-")
        assert rc["model_version"] == data["model_version"]
        assert rc["transaction_facts"]["transaction_id"] == "api_case_curr"
        assert rc["model_assessment"]["fraud_probability"] == data["fraud_probability"]
        assert rc["policy_decision"]["action"] == data["action"]
        assert rc["customer_context"]["prior_transaction_count"] == 3
        assert rc["behavioral_assessment"] is not None
        assert rc["network_assessment"] is not None
        assert rc["ai_investigation"] is not None
        assert rc["audit_metadata"]["request_id"] == data["request_id"]
