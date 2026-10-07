"""
Tests for Phase 3: Related-Transaction / Network Risk Investigation.

Verifies that the deterministic network risk engine accurately, defensively,
and leakage-safely assesses entity-level linkages across:
- Device sharing linkages (cross-customer multi-account clustering)
- Device usage depth (customer/device historical relationship)
- Merchant concentration (trailing velocity to specific merchants)
- Payment rail divergence (novel payment method introduction)
- Policy separation (ensuring network evidence does not change deterministic policy action)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError

from backend.schemas.transaction import TransactionInput, RiskRequest
from backend.services.risk_service import _build_feature_row, build_investigation_context, evaluate_full
from backend.services.network_engine import evaluate_network_risk


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


class TestNetworkRiskEngine:
    """Unit tests for each network risk dimension."""

    def test_cold_start_network_assessment(self):
        txn = _txn(amount=1000.0)
        req = RiskRequest(transaction=txn, prior_transactions=[], related_transactions=[], source="manual")
        row = _build_feature_row(req)
        ctx = build_investigation_context(req, row)

        net = ctx["network_assessment"]
        assert net["overall_status"] == "INSUFFICIENT_HISTORY"
        assert net["total_links_identified"] == 0
        assert len(net["links"]) == 4
        for link in net["links"]:
            assert link["severity"] == "NORMAL"

    def test_device_sharing_single_account(self):
        priors = [
            _txn(txn_id=f"p_{i}", customer_id="cust_alice", device_id="dev_shared", timestamp=f"2026-05-1{i}T10:00:00Z")
            for i in range(3)
        ]
        curr = _txn(txn_id="curr", customer_id="cust_alice", device_id="dev_shared", timestamp="2026-05-20T12:00:00Z")
        req = RiskRequest(transaction=curr, prior_transactions=priors)
        assessment = evaluate_network_risk(req)

        dev_share = next(l for l in assessment["links"] if l["link_type"] == "DEVICE_SHARING_LINK")
        assert dev_share["severity"] == "NORMAL"
        assert dev_share["related_entity_count"] == 1
        assert "Single-account" in dev_share["description"] or "exclusively" in dev_share["description"]

    def test_device_sharing_multi_account_high(self):
        # 2 distinct customers previously used dev_shared
        priors = [
            _txn(txn_id="p_alice", customer_id="cust_alice", device_id="dev_shared", timestamp="2026-05-18T10:00:00Z")
        ]
        related = [
            _txn(txn_id="p_bob", customer_id="cust_bob", device_id="dev_shared", timestamp="2026-05-19T10:00:00Z")
        ]
        curr = _txn(txn_id="curr", customer_id="cust_alice", device_id="dev_shared", timestamp="2026-05-20T12:00:00Z")
        req = RiskRequest(transaction=curr, prior_transactions=priors, related_transactions=related)
        assessment = evaluate_network_risk(req)

        dev_share = next(l for l in assessment["links"] if l["link_type"] == "DEVICE_SHARING_LINK")
        assert dev_share["severity"] == "HIGH"
        assert dev_share["related_entity_count"] == 2
        assert "Multi-account" in dev_share["description"]
        assert assessment["overall_status"] == "ELEVATED_NETWORK_RISK"

    def test_device_sharing_multi_account_critical(self):
        # 4 distinct customers previously used dev_syndicate
        related = [
            _txn(txn_id=f"p_synd_{i}", customer_id=f"cust_mule_{i}", device_id="dev_syndicate", timestamp=f"2026-05-1{i}T10:00:00Z")
            for i in range(4)
        ]
        curr = _txn(txn_id="curr", customer_id="cust_target", device_id="dev_syndicate", timestamp="2026-05-20T12:00:00Z")
        req = RiskRequest(transaction=curr, prior_transactions=[], related_transactions=related)
        assessment = evaluate_network_risk(req)

        dev_share = next(l for l in assessment["links"] if l["link_type"] == "DEVICE_SHARING_LINK")
        assert dev_share["severity"] == "CRITICAL"
        assert dev_share["related_entity_count"] == 4
        assert "High-density" in dev_share["description"]
        assert assessment["overall_status"] == "CRITICAL_NETWORK_RISK"

    def test_future_related_transaction_rejection_in_schema(self):
        curr = _txn(txn_id="curr", timestamp="2026-05-20T12:00:00Z")
        future_rel = _txn(txn_id="future_rel", customer_id="cust_other", timestamp="2026-05-20T13:00:00Z")

        with pytest.raises(ValidationError) as excinfo:
            RiskRequest(transaction=curr, prior_transactions=[], related_transactions=[future_rel])
        assert "strictly before" in str(excinfo.value).lower()

    def test_future_transaction_exclusion_in_engine(self):
        curr_ts = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
        curr = _txn(txn_id="curr", timestamp="2026-05-20T12:00:00Z")

        # Manually construct request bypassing schema validation to verify engine-level defense
        req = RiskRequest.model_construct(
            transaction=curr,
            prior_transactions=[
                _txn(txn_id="p_valid", timestamp="2026-05-20T11:00:00Z"),
                _txn(txn_id="p_future", timestamp="2026-05-20T13:00:00Z"),
            ],
            related_transactions=[
                _txn(txn_id="rel_valid", customer_id="cust_other", timestamp="2026-05-20T11:30:00Z"),
                _txn(txn_id="rel_future", customer_id="cust_other2", timestamp="2026-05-20T14:00:00Z"),
            ],
            source="manual",
        )
        assessment = evaluate_network_risk(req)
        dev_share = next(l for l in assessment["links"] if l["link_type"] == "DEVICE_SHARING_LINK")
        # Only 2 customers prior to curr_ts: cust_test and cust_other
        assert dev_share["related_entity_count"] == 2
        assert "cust_other2" not in dev_share["evidence"]["customer_ids"]

    def test_device_history_depth_novel(self):
        priors = [
            _txn(txn_id=f"p_{i}", device_id="dev_old", status="success", timestamp=f"2026-05-1{i}T10:00:00Z")
            for i in range(3)
        ]
        curr = _txn(txn_id="curr", device_id="dev_brand_new", timestamp="2026-05-20T12:00:00Z")
        req = RiskRequest(transaction=curr, prior_transactions=priors)
        assessment = evaluate_network_risk(req)

        depth_link = next(l for l in assessment["links"] if l["link_type"] == "DEVICE_HISTORY_DEPTH")
        assert depth_link["severity"] == "MEDIUM"
        assert depth_link["related_entity_count"] == 0
        assert "0 prior successful" in depth_link["description"]

    def test_device_history_depth_established(self):
        priors = [
            _txn(txn_id=f"p_{i}", device_id="dev_trusted", status="success", timestamp=f"2026-05-1{i}T10:00:00Z")
            for i in range(5)
        ]
        curr = _txn(txn_id="curr", device_id="dev_trusted", timestamp="2026-05-20T12:00:00Z")
        req = RiskRequest(transaction=curr, prior_transactions=priors)
        assessment = evaluate_network_risk(req)

        depth_link = next(l for l in assessment["links"] if l["link_type"] == "DEVICE_HISTORY_DEPTH")
        assert depth_link["severity"] == "NORMAL"
        assert depth_link["related_entity_count"] == 5
        assert "5 prior successful" in depth_link["description"]

    def test_merchant_concentration_burst(self):
        # 4 transactions to merch_01 in trailing 1h
        priors = [
            _txn(txn_id=f"p_m_{i}", merchant_id="merch_target", timestamp=f"2026-05-20T11:{10+i*10}:00Z")
            for i in range(4)
        ]
        curr = _txn(txn_id="curr", merchant_id="merch_target", timestamp="2026-05-20T11:55:00Z")
        req = RiskRequest(transaction=curr, prior_transactions=priors)
        assessment = evaluate_network_risk(req)

        merch_link = next(l for l in assessment["links"] if l["link_type"] == "MERCHANT_CONCENTRATION")
        assert merch_link["severity"] == "HIGH"
        assert merch_link["related_entity_count"] == 4
        assert "Rapid merchant velocity" in merch_link["description"]

    def test_merchant_concentration_moderate(self):
        # 2 transactions to merch_01 in trailing 1h
        priors = [
            _txn(txn_id="p_m_0", merchant_id="merch_target", timestamp="2026-05-20T11:20:00Z"),
            _txn(txn_id="p_m_1", merchant_id="merch_target", timestamp="2026-05-20T11:40:00Z"),
        ]
        curr = _txn(txn_id="curr", merchant_id="merch_target", timestamp="2026-05-20T11:55:00Z")
        req = RiskRequest(transaction=curr, prior_transactions=priors)
        assessment = evaluate_network_risk(req)

        merch_link = next(l for l in assessment["links"] if l["link_type"] == "MERCHANT_CONCENTRATION")
        assert merch_link["severity"] == "MEDIUM"
        assert merch_link["related_entity_count"] == 2

    def test_payment_method_divergence(self):
        priors = [
            _txn(txn_id=f"p_pay_{i}", payment_method="upi", timestamp=f"2026-05-1{i}T10:00:00Z")
            for i in range(3)
        ]
        curr = _txn(txn_id="curr", payment_method="card", timestamp="2026-05-20T12:00:00Z")
        req = RiskRequest(transaction=curr, prior_transactions=priors)
        assessment = evaluate_network_risk(req)

        pay_link = next(l for l in assessment["links"] if l["link_type"] == "PAYMENT_METHOD_DIVERGENCE")
        assert pay_link["severity"] == "MEDIUM"
        assert "Payment rail divergence" in pay_link["description"]
        assert "card" in pay_link["description"]

    def test_payment_method_consistency(self):
        priors = [
            _txn(txn_id=f"p_pay_{i}", payment_method="card", timestamp=f"2026-05-1{i}T10:00:00Z")
            for i in range(3)
        ]
        curr = _txn(txn_id="curr", payment_method="card", timestamp="2026-05-20T12:00:00Z")
        req = RiskRequest(transaction=curr, prior_transactions=priors)
        assessment = evaluate_network_risk(req)

        pay_link = next(l for l in assessment["links"] if l["link_type"] == "PAYMENT_METHOD_DIVERGENCE")
        assert pay_link["severity"] == "NORMAL"
        assert "matches customer's established" in pay_link["description"]

    def test_network_evidence_does_not_alter_policy_action(self, client):
        """
        Critical invariant: network risk evidence is strictly an investigation artifact
        and must not modify model probability, SHAP explanations, or deterministic policy action.
        """
        bundle = client.app.state.model_bundle


        # Moderate transaction that falls into ALLOW / LOW category
        priors = [
            _txn(txn_id=f"p_{i}", amount=500.0, device_id="dev_syndicate", timestamp=f"2026-05-1{i}T10:00:00Z")
            for i in range(5)
        ]
        curr = _txn(txn_id="curr", amount=510.0, device_id="dev_syndicate", timestamp="2026-05-20T12:00:00Z")

        # Scenario A: without related transactions
        req_a = RiskRequest(transaction=curr, prior_transactions=priors, related_transactions=[])
        dec_a, _, _, _, _, ctx_a = evaluate_full(bundle, req_a)

        # Scenario B: with heavy multi-customer syndicate related transactions
        related = [
            _txn(txn_id=f"rel_{i}", customer_id=f"cust_mule_{i}", device_id="dev_syndicate", timestamp=f"2026-05-1{i}T08:00:00Z")
            for i in range(5)
        ]
        req_b = RiskRequest(transaction=curr, prior_transactions=priors, related_transactions=related)
        dec_b, _, _, _, _, ctx_b = evaluate_full(bundle, req_b)

        # Policy and probability MUST be identical
        assert dec_a.action == dec_b.action
        assert dec_a.fraud_probability == dec_b.fraud_probability
        assert dec_a.policy_rule_id == dec_b.policy_rule_id
        assert dec_a.risk_score == dec_b.risk_score

        # Network assessment in investigation context captures the difference
        assert ctx_a["network_assessment"]["overall_status"] == "ISOLATED_TRANSACTION"
        assert ctx_b["network_assessment"]["overall_status"] == "CRITICAL_NETWORK_RISK"


class TestNetworkRiskAPI:
    """API integration tests for network assessment payload."""

    def test_api_risk_evaluate_returns_network_assessment(self, client):
        priors = [
            dict(
                transaction_id=f"api_net_{i}", customer_id="cust_net_api", merchant_id="merch_01",
                merchant_category="electronics", timestamp=f"2026-05-1{i}T10:00:00Z", amount=450.0,
                device_id="dev_net_known", geo_region="region_01", payment_method="card", status="success",
                account_created="2025-01-01T00:00:00Z",
            )
            for i in range(3)
        ]
        payload = {
            "transaction": {
                "transaction_id": "api_net_curr",
                "customer_id": "cust_net_api",
                "merchant_id": "merch_01",
                "merchant_category": "electronics",
                "timestamp": "2026-05-20T12:00:00Z",
                "amount": 480.0,
                "device_id": "dev_net_known",
                "geo_region": "region_01",
                "payment_method": "card",
                "status": "success",
                "account_created": "2025-01-01T00:00:00Z",
            },
            "prior_transactions": priors,
            "related_transactions": [],
            "source": "manual",
        }
        res = client.post("/risk/evaluate", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert "investigation_context" in data
        ctx = data["investigation_context"]
        assert "network_assessment" in ctx
        net = ctx["network_assessment"]
        assert net["overall_status"] == "ISOLATED_TRANSACTION"
        assert len(net["links"]) == 4
        assert net["summary"] != ""
