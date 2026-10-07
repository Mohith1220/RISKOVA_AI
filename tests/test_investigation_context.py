"""
Tests for Phase 1: Transaction Investigation Context.

Verifies that the investigation context accurately and strictly reflects
customer historical baseline and behavioral anomalies using grounded evidence.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime, timezone
import pandas as pd

from backend.schemas.transaction import TransactionInput, RiskRequest
from backend.services.risk_service import build_investigation_context, _build_feature_row


def _create_txn(
    txn_id="txn_current",
    customer_id="cust_inv_01",
    amount=5000.0,
    device_id="dev_current",
    geo_region="region_01",
    timestamp="2026-05-20T12:00:00Z",
    status="success",
    account_created="2025-01-01T00:00:00Z",
):
    return TransactionInput(
        transaction_id=txn_id,
        customer_id=customer_id,
        merchant_id="merch_01",
        merchant_category="electronics",
        timestamp=datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
        amount=amount,
        device_id=device_id,
        geo_region=geo_region,
        payment_method="card",
        status=status,
        account_created=datetime.fromisoformat(account_created.replace("Z", "+00:00")),
    )


def _create_prior_txns(customer_id="cust_inv_01", n=5, avg_amt=1000.0, device="dev_known", geo="region_known"):
    return [
        TransactionInput(
            transaction_id=f"prior_txn_{i}",
            customer_id=customer_id,
            merchant_id="merch_01",
            merchant_category="electronics",
            timestamp=datetime.fromisoformat(f"2026-05-1{i}T10:00:00+00:00"),
            amount=avg_amt + i * 10,
            device_id=device,
            geo_region=geo,
            payment_method="card",
            status="success",
            account_created=datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
        )
        for i in range(n)
    ]


class TestInvestigationContextUnit:
    """Unit tests for build_investigation_context function."""

    def test_cold_start_reports_insufficient_history(self):
        txn = _create_txn(amount=2500.0)
        req = RiskRequest(transaction=txn, prior_transactions=[], source="manual")
        row = _build_feature_row(req)

        ctx = build_investigation_context(req, row)

        assert ctx["status"] == "INSUFFICIENT_HISTORY"
        assert ctx["customer_id"] == "cust_inv_01"
        assert ctx["current_transaction_id"] == "txn_current"
        assert ctx["customer_summary"]["prior_transaction_count"] == 0
        assert ctx["customer_summary"]["historical_avg_amount"] is None
        assert ctx["customer_summary"]["known_devices"] == []
        assert ctx["customer_summary"]["known_geos"] == []
        assert ctx["behavioral_signals"]["status"] == "INSUFFICIENT_HISTORY"
        assert ctx["behavioral_signals"]["amount_deviation"] is None

        # Check baseline key finding
        assert len(ctx["key_findings"]) == 1
        assert ctx["key_findings"][0]["signal_type"] == "BASELINE"
        assert ctx["key_findings"][0]["severity"] == "INFO"
        assert "no prior history" in ctx["key_findings"][0]["description"].lower()

    def test_established_history_summary_metrics(self):
        priors = _create_prior_txns(n=4, avg_amt=500.0, device="dev_trusted", geo="region_west")
        # amounts: 500, 510, 520, 530 => mean = 515.0, min = 500, max = 530
        txn = _create_txn(amount=515.0, device_id="dev_trusted", geo_region="region_west")
        req = RiskRequest(transaction=txn, prior_transactions=priors, source="demo")
        row = _build_feature_row(req)

        ctx = build_investigation_context(req, row)

        assert ctx["status"] == "AVAILABLE"
        summary = ctx["customer_summary"]
        assert summary["prior_transaction_count"] == 4
        assert summary["historical_avg_amount"] == 515.0
        assert summary["historical_min_amount"] == 500.0
        assert summary["historical_max_amount"] == 530.0
        assert summary["known_devices"] == ["dev_trusted"]
        assert summary["known_geos"] == ["region_west"]
        assert summary["first_seen_timestamp"] is not None
        assert summary["last_seen_timestamp"] is not None

    def test_amount_deviation_grounded_finding(self):
        priors = _create_prior_txns(n=5, avg_amt=1000.0, device="dev_known", geo="region_known")
        # Massive amount surge: 50,000 vs 1000 avg (50x)
        txn = _create_txn(amount=50000.0, device_id="dev_known", geo_region="region_known")
        req = RiskRequest(transaction=txn, prior_transactions=priors, source="demo")
        row = _build_feature_row(req)

        ctx = build_investigation_context(req, row)

        amt_dev = ctx["behavioral_signals"]["amount_deviation"]
        assert amt_dev is not None
        assert amt_dev["current_amount"] == 50000.0
        assert amt_dev["ratio"] > 40.0

        # Check finding
        amt_findings = [f for f in ctx["key_findings"] if f["signal_type"] == "AMOUNT_DEVIATION"]
        assert len(amt_findings) == 1
        assert amt_findings[0]["severity"] == "HIGH"
        assert "50,000" in amt_findings[0]["description"]

    def test_device_and_geo_novelty_grounded_findings(self):
        priors = _create_prior_txns(n=3, avg_amt=1000.0, device="dev_primary", geo="region_01")
        # Current txn uses new device and new geo
        txn = _create_txn(amount=1000.0, device_id="dev_new_brand", geo_region="region_99")
        req = RiskRequest(transaction=txn, prior_transactions=priors, source="demo")
        row = _build_feature_row(req)

        ctx = build_investigation_context(req, row)

        dev_sig = ctx["behavioral_signals"]["device_novelty"]
        assert dev_sig["is_new_device"] is True
        assert dev_sig["current_device"] == "dev_new_brand"
        assert dev_sig["known_devices_count"] == 1

        geo_sig = ctx["behavioral_signals"]["geo_novelty"]
        assert geo_sig["is_new_geo"] is True
        assert geo_sig["current_geo"] == "region_99"
        assert geo_sig["known_geos_count"] == 1

        # Check findings
        dev_findings = [f for f in ctx["key_findings"] if f["signal_type"] == "DEVICE_NOVELTY"]
        assert len(dev_findings) == 1
        assert dev_findings[0]["severity"] == "HIGH"
        assert "dev_new_brand" in dev_findings[0]["description"]

        geo_findings = [f for f in ctx["key_findings"] if f["signal_type"] == "GEO_NOVELTY"]
        assert len(geo_findings) == 1
        assert geo_findings[0]["severity"] == "HIGH"
        assert "region_99" in geo_findings[0]["description"]

    def test_velocity_spike_grounded_finding(self):
        # 3 prior transactions in past 10 minutes
        base_ts = datetime(2026, 5, 20, 10, 0, 0, tzinfo=timezone.utc)
        priors = [
            TransactionInput(
                transaction_id=f"vel_prior_{i}",
                customer_id="cust_inv_vel",
                merchant_id="merch_01",
                merchant_category="electronics",
                timestamp=datetime(2026, 5, 20, 10, 1 + i * 2, 0, tzinfo=timezone.utc),
                amount=500.0,
                device_id="dev_known",
                geo_region="region_01",
                payment_method="card",
                status="success",
                account_created=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            )
            for i in range(3)
        ]
        txn = TransactionInput(
            transaction_id="vel_current",
            customer_id="cust_inv_vel",
            merchant_id="merch_01",
            merchant_category="electronics",
            timestamp=datetime(2026, 5, 20, 10, 8, 0, tzinfo=timezone.utc),
            amount=500.0,
            device_id="dev_known",
            geo_region="region_01",
            payment_method="card",
            status="success",
            account_created=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        req = RiskRequest(transaction=txn, prior_transactions=priors, source="manual")
        row = _build_feature_row(req)

        ctx = build_investigation_context(req, row)

        vel_sig = ctx["behavioral_signals"]["velocity"]
        assert vel_sig["velocity_30min"] >= 3

        vel_findings = [f for f in ctx["key_findings"] if f["signal_type"] == "VELOCITY_SPIKE"]
        assert len(vel_findings) >= 1
        assert vel_findings[0]["severity"] in ("HIGH", "MEDIUM")


class TestInvestigationContextAPI:
    """API integration tests verifying /risk/evaluate response contract with investigation context."""

    def test_api_evaluate_returns_investigation_context_with_priors(self, client):
        priors = [
            dict(
                transaction_id=f"api_ctx_{i}", customer_id="cust_api_inv", merchant_id="merch_001",
                merchant_category="electronics", timestamp=f"2026-05-1{i}T10:00:00Z", amount=600.0,
                device_id="dev_known", geo_region="region_03", payment_method="card", status="success",
                account_created="2025-01-01T00:00:00Z",
            )
            for i in range(5)
        ]
        txn = dict(
            transaction_id="api_txn_target", customer_id="cust_api_inv", merchant_id="merch_001",
            merchant_category="electronics", timestamp="2026-05-20T10:05:00Z", amount=25000.0,
            device_id="dev_novel", geo_region="region_novel", payment_method="card", status="success",
            account_created="2025-01-01T00:00:00Z",
        )

        r = client.post("/risk/evaluate", json={"transaction": txn, "prior_transactions": priors, "source": "demo"})
        assert r.status_code == 200
        body = r.json()

        assert "investigation_context" in body
        ctx = body["investigation_context"]
        assert ctx["status"] == "AVAILABLE"
        assert ctx["customer_id"] == "cust_api_inv"
        assert ctx["current_transaction_id"] == "api_txn_target"
        assert ctx["customer_summary"]["prior_transaction_count"] == 5
        assert ctx["customer_summary"]["historical_avg_amount"] == 600.0
        assert ctx["behavioral_signals"]["device_novelty"]["is_new_device"] is True
        assert ctx["behavioral_signals"]["geo_novelty"]["is_new_geo"] is True
        assert len(ctx["key_findings"]) >= 1

    def test_api_evaluate_returns_investigation_context_cold_start(self, client):
        txn = dict(
            transaction_id="api_txn_cold", customer_id="cust_api_cold", merchant_id="merch_001",
            merchant_category="electronics", timestamp="2026-05-20T10:05:00Z", amount=1200.0,
            device_id="dev_first", geo_region="region_01", payment_method="card", status="success",
            account_created="2025-01-01T00:00:00Z",
        )

        r = client.post("/risk/evaluate", json={"transaction": txn, "prior_transactions": [], "source": "manual"})
        assert r.status_code == 200
        body = r.json()

        assert "investigation_context" in body
        ctx = body["investigation_context"]
        assert ctx["status"] == "INSUFFICIENT_HISTORY"
        assert ctx["customer_summary"]["prior_transaction_count"] == 0
        assert ctx["customer_summary"]["historical_avg_amount"] is None
        assert ctx["key_findings"][0]["signal_type"] == "BASELINE"
