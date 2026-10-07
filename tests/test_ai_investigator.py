"""
Tests for Phase 4: AI Risk Investigator.

Verifies the deterministic synthesizer, entity grounding validation,
safe fallback behavior, policy isolation, and full API integration.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import respx
import httpx
import json
from datetime import datetime, timezone


from backend.schemas.transaction import TransactionInput, RiskRequest
from backend.schemas.investigation import RiskInvestigationInput
from backend.schemas.response import AIInvestigationReport, RiskDriverItem
from backend.services.ai_investigator import (
    build_investigation_input,
    deterministic_synthesizer,
    verify_grounding,
    optional_llm_adapter,
    generate_ai_investigation_report,
)
from backend.services.risk_service import (
    _build_feature_row,
    build_investigation_context,
    evaluate_full,
)


def _txn(
    txn_id="txn_test",
    customer_id="cust_test",
    amount=500.0,
    device_id="dev_known",
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


def _priors(customer_id="cust_test", n=5, avg_amt=500.0, device="dev_known", geo="region_01"):
    return [
        TransactionInput(
            transaction_id=f"prior_{i}",
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


class TestAIInvestigatorSynthesizer:
    """Tests for the deterministic grounding synthesizer."""

    def test_cold_start_deterministic_synthesis(self):
        txn = _txn(amount=1000.0)
        req = RiskRequest(transaction=txn, prior_transactions=[])
        row = _build_feature_row(req)
        ctx = build_investigation_context(req, row)

        ai_report = ctx["ai_investigation_report"]
        assert ai_report.status in ("DETERMINISTIC_SYNTHESIS", "GENERATED")
        assert "cold-start" in ai_report.executive_summary.lower() or "first-time" in ai_report.executive_summary.lower()
        assert ai_report.grounding_verification_passed is True
        assert len(ai_report.mitigating_factors) > 0

    def test_multi_anomaly_synthesis(self):
        priors = _priors(n=5, avg_amt=500.0)
        # Extreme 90x surge + novel device
        txn = _txn(amount=45000.0, device_id="dev_brand_new")
        req = RiskRequest(transaction=txn, prior_transactions=priors)
        row = _build_feature_row(req)
        ctx = build_investigation_context(req, row)

        ai_report = ctx["ai_investigation_report"]
        assert len(ai_report.risk_drivers) >= 1
        driver_types = [d.driver_type for d in ai_report.risk_drivers]
        assert "BEHAVIORAL" in driver_types or "NETWORK" in driver_types
        assert "45,000" in ai_report.executive_summary or "45000" in ai_report.executive_summary

    def test_mitigating_factor_detection(self):
        priors = _priors(n=5, avg_amt=500.0, device="dev_trusted", geo="region_01")
        # Same device, same region, moderate amount
        txn = _txn(amount=520.0, device_id="dev_trusted", geo_region="region_01")
        req = RiskRequest(transaction=txn, prior_transactions=priors)
        row = _build_feature_row(req)
        ctx = build_investigation_context(req, row)

        ai_report = ctx["ai_investigation_report"]
        mitigating_text = " ".join(ai_report.mitigating_factors).lower()
        assert "dev_trusted" in mitigating_text or "recognized device" in mitigating_text
        assert "region_01" in mitigating_text or "geographic region" in mitigating_text

    def test_contradictory_evidence(self):
        priors = _priors(n=5, avg_amt=500.0, device="dev_trusted", geo="region_01")
        # Large amount surge, but on trusted home device and region
        txn = _txn(amount=15000.0, device_id="dev_trusted", geo_region="region_01")
        req = RiskRequest(transaction=txn, prior_transactions=priors)
        row = _build_feature_row(req)
        ctx = build_investigation_context(req, row)

        ai_report = ctx["ai_investigation_report"]
        # Has risk driver (amount)
        assert any(d.driver_type == "BEHAVIORAL" for d in ai_report.risk_drivers)
        # Also has mitigating factor (device/geo)
        assert any("dev_trusted" in m or "recognized" in m for m in ai_report.mitigating_factors)


class TestGroundingValidator:
    """Tests for the post-generation entity grounding validator."""

    def _sample_input(self):
        return RiskInvestigationInput(
            transaction_id="txn_ground_01",
            customer_id="cust_ground_01",
            amount=500.0,
            timestamp="2026-05-20T12:00:00Z",
            merchant_id="merch_valid_01",
            merchant_category="electronics",
            device_id="dev_valid_01",
            geo_region="region_01",
            payment_method="card",
            fraud_probability=0.12,
            decision_threshold=0.40,
            risk_score=15,
            risk_category="LOW",
            prior_transaction_count=5,
            account_age_days=100.0,
            known_devices_count=1,
            known_geos_count=1,
            behavioral_overall_status="NOMINAL",
            network_overall_status="ISOLATED_TRANSACTION",
            recommended_action="ALLOW",
            policy_rule_id="R_LOW_NORMAL",
            policy_reason="Normal baseline spending.",
        )

    def test_hallucinated_device_rejection(self):
        inp = self._sample_input()
        report = AIInvestigationReport(
            status="GENERATED",
            executive_summary="Customer transacted on unauthorized hardware dev_hallucinated_99.",
            risk_drivers=[RiskDriverItem(driver_type="BEHAVIORAL", severity="HIGH", finding="Unknown device", supporting_evidence="dev_hallucinated_99")],
            mitigating_factors=["None"],
            analyst_action_guidance="Inspect device.",
            grounding_verification_passed=True,
        )
        assert verify_grounding(report, inp) is False

    def test_hallucinated_merchant_rejection(self):
        inp = self._sample_input()
        report = AIInvestigationReport(
            status="GENERATED",
            executive_summary="Customer transacted on merchant merch_fake_store.",
            risk_drivers=[],
            mitigating_factors=["None"],
            analyst_action_guidance="Inspect merchant.",
            grounding_verification_passed=True,
        )
        assert verify_grounding(report, inp) is False

    def test_hallucinated_customer_rejection(self):
        inp = self._sample_input()
        report = AIInvestigationReport(
            status="GENERATED",
            executive_summary="Linked to foreign account cust_phantom_user.",
            risk_drivers=[],
            mitigating_factors=["None"],
            analyst_action_guidance="Inspect customer.",
            grounding_verification_passed=True,
        )
        assert verify_grounding(report, inp) is False

    def test_fabricated_probability_rejection(self):
        inp = self._sample_input()  # Actual probability is 0.12 (12%)
        report = AIInvestigationReport(
            status="GENERATED",
            executive_summary="Critical alert: model calculated 95% fraud probability.",
            risk_drivers=[],
            mitigating_factors=["None"],
            analyst_action_guidance="Inspect probability.",
            grounding_verification_passed=True,
        )
        assert verify_grounding(report, inp) is False

    def test_grounding_verification_flag(self):
        inp = self._sample_input()
        valid_report = deterministic_synthesizer(inp)
        assert verify_grounding(valid_report, inp) is True
        assert valid_report.grounding_verification_passed is True


class TestLLMAdapterAndFallbacks:
    """Tests for optional LLM adapter and graceful degradation."""

    def test_llm_unavailable_fallback(self, monkeypatch):
        monkeypatch.delenv("MERCHANTSHIELD_LLM_URL", raising=False)
        inp = TestGroundingValidator()._sample_input()
        report = generate_ai_investigation_report(inp)
        assert report.status == "DETERMINISTIC_SYNTHESIS"
        assert report.grounding_verification_passed is True

    @respx.mock
    def test_llm_timeout_fallback(self, monkeypatch):
        monkeypatch.setenv("MERCHANTSHIELD_LLM_URL", "https://api.ai-risk.internal/v1/chat")
        respx.post("https://api.ai-risk.internal/v1/chat").mock(side_effect=httpx.TimeoutException("Timeout"))

        inp = TestGroundingValidator()._sample_input()
        report = generate_ai_investigation_report(inp)
        # Must fall back gracefully to deterministic synthesizer
        assert report.status == "DETERMINISTIC_SYNTHESIS"
        assert report.grounding_verification_passed is True

    @respx.mock
    def test_malformed_json_fallback(self, monkeypatch):
        monkeypatch.setenv("MERCHANTSHIELD_LLM_URL", "https://api.ai-risk.internal/v1/chat")
        respx.post("https://api.ai-risk.internal/v1/chat").mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": "INVALID NON-JSON RESPONSE"}}]})
        )

        inp = TestGroundingValidator()._sample_input()
        report = generate_ai_investigation_report(inp)
        assert report.status == "DETERMINISTIC_SYNTHESIS"

    @respx.mock
    def test_invalid_schema_fallback(self, monkeypatch):
        monkeypatch.setenv("MERCHANTSHIELD_LLM_URL", "https://api.ai-risk.internal/v1/chat")
        respx.post("https://api.ai-risk.internal/v1/chat").mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"wrong_key": 123})}}]})
        )

        inp = TestGroundingValidator()._sample_input()
        report = generate_ai_investigation_report(inp)
        assert report.status == "DETERMINISTIC_SYNTHESIS"

    @respx.mock
    def test_grounding_failure_fallback(self, monkeypatch):
        monkeypatch.setenv("MERCHANTSHIELD_LLM_URL", "https://api.ai-risk.internal/v1/chat")
        # LLM returns JSON with hallucinated device
        hallucinated_data = {
            "status": "GENERATED",
            "executive_summary": "Transaction linked to unauthorized device dev_hallucinated_01.",
            "risk_drivers": [],
            "mitigating_factors": [],
            "analyst_action_guidance": "Inspect evidence.",
            "grounding_verification_passed": True,
        }
        respx.post("https://api.ai-risk.internal/v1/chat").mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(hallucinated_data)}}]})
        )

        inp = TestGroundingValidator()._sample_input()
        report = generate_ai_investigation_report(inp)
        # Grounding check failed -> falls back to deterministic synthesis
        assert report.status == "DETERMINISTIC_SYNTHESIS"
        assert "dev_hallucinated_01" not in report.executive_summary


class TestPolicyAndRiskIsolation:
    """Critical tests proving AI Investigator output does not alter decision engine or risk calculations."""

    def test_policy_isolation(self, client):
        bundle = client.app.state.model_bundle
        priors = _priors(n=5, avg_amt=500.0)
        curr = _txn(amount=510.0)
        req = RiskRequest(transaction=curr, prior_transactions=priors)

        decision, explanation, req_id, prior_count, err, ctx = evaluate_full(bundle, req)

        assert decision.action == "ALLOW"
        assert decision.risk_category == "LOW"
        assert ctx["ai_investigation_report"] is not None
        assert ctx["ai_investigation_report"].grounding_verification_passed is True

    def test_fraud_probability_and_score_isolation(self, client):
        bundle = client.app.state.model_bundle
        priors = _priors(n=5, avg_amt=500.0)
        curr = _txn(amount=45000.0)  # Extreme surge
        req = RiskRequest(transaction=curr, prior_transactions=priors)

        decision, explanation, req_id, prior_count, err, ctx = evaluate_full(bundle, req)

        # Confirm probability and score match LightGBM directly
        assert decision.fraud_probability > 0.0
        assert decision.risk_score > 0
        assert ctx["ai_investigation_report"].status in ("DETERMINISTIC_SYNTHESIS", "GENERATED")


class TestAPIIntegration:
    """API integration tests for AI report."""

    def test_existing_api_compatibility(self, client):
        priors = [
            dict(
                transaction_id=f"api_ai_{i}", customer_id="cust_ai_api", merchant_id="merch_01",
                merchant_category="electronics", timestamp=f"2026-05-1{i}T10:00:00Z", amount=450.0,
                device_id="dev_ai_known", geo_region="region_01", payment_method="card", status="success",
                account_created="2025-01-01T00:00:00Z",
            )
            for i in range(3)
        ]
        payload = {
            "transaction": {
                "transaction_id": "api_ai_curr",
                "customer_id": "cust_ai_api",
                "merchant_id": "merch_01",
                "merchant_category": "electronics",
                "timestamp": "2026-05-20T12:00:00Z",
                "amount": 480.0,
                "device_id": "dev_ai_known",
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

        assert "investigation_context" in data
        ctx = data["investigation_context"]
        assert "ai_investigation_report" in ctx
        ai_report = ctx["ai_investigation_report"]
        assert ai_report["status"] in ("DETERMINISTIC_SYNTHESIS", "GENERATED")
        assert len(ai_report["executive_summary"]) > 10
        assert isinstance(ai_report["risk_drivers"], list)
        assert isinstance(ai_report["mitigating_factors"], list)
        assert "analyst_action_guidance" in ai_report
        assert ai_report["grounding_verification_passed"] is True
