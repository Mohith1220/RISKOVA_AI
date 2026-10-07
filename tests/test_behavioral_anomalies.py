"""
Tests for Phase 2: Behavioral Anomaly Investigation.

Verifies that the deterministic behavioral anomaly engine accurately, safely,
and defensively detects and explains anomalies across 6 behavioral dimensions.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime, timezone

from backend.schemas.transaction import TransactionInput, RiskRequest
from backend.services.risk_service import _build_feature_row, build_investigation_context
from backend.services.behavioral_engine import evaluate_behavioral_anomalies


def _txn(
    txn_id="txn_test",
    customer_id="cust_test",
    amount=500.0,
    device_id="dev_known",
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


class TestBehavioralAnomalyDimensions:
    """Unit tests for each of the 6 behavioral dimensions."""

    def test_cold_start_reports_insufficient_history(self):
        txn = _txn(amount=1000.0)
        req = RiskRequest(transaction=txn, prior_transactions=[], source="manual")
        row = _build_feature_row(req)
        ctx = build_investigation_context(req, row)

        assessment = ctx["behavioral_assessment"]
        assert assessment["overall_status"] == "INSUFFICIENT_HISTORY"
        assert assessment["anomaly_count"] == 0
        assert len(assessment["anomalies"]) == 6
        for anomaly in assessment["anomalies"]:
            assert anomaly["is_anomaly"] is False
            assert anomaly["severity"] == "NORMAL"
            assert "No prior" in anomaly["baseline_summary"]

    def test_amount_anomaly_normal_spending(self):
        priors = _priors(n=5, avg_amt=500.0)
        txn = _txn(amount=510.0)
        req = RiskRequest(transaction=txn, prior_transactions=priors, source="demo")
        row = _build_feature_row(req)
        ctx = build_investigation_context(req, row)

        assessment = ctx["behavioral_assessment"]
        amt_dim = next(a for a in assessment["anomalies"] if a["dimension"] == "AMOUNT")
        assert amt_dim["is_anomaly"] is False
        assert amt_dim["severity"] == "NORMAL"
        assert "consistent" in amt_dim["description"].lower()

    def test_amount_anomaly_extreme_surge(self):
        priors = _priors(n=5, avg_amt=500.0)
        txn = _txn(amount=45000.0)  # 90x surge
        req = RiskRequest(transaction=txn, prior_transactions=priors, source="demo")
        row = _build_feature_row(req)
        ctx = build_investigation_context(req, row)

        assessment = ctx["behavioral_assessment"]
        amt_dim = next(a for a in assessment["anomalies"] if a["dimension"] == "AMOUNT")
        assert amt_dim["is_anomaly"] is True
        assert amt_dim["severity"] == "CRITICAL"
        assert "45,000" in amt_dim["description"]
        assert "90.0x" in amt_dim["observed_summary"] or "90" in amt_dim["observed_summary"]

    def test_velocity_anomaly_burst_detection(self):
        # 3 prior transactions in the past 15 minutes
        priors = [
            TransactionInput(
                transaction_id=f"vel_p_{i}",
                customer_id="cust_vel",
                merchant_id="merch_01",
                merchant_category="electronics",
                timestamp=datetime(2026, 5, 20, 10, 1 + i * 3, 0, tzinfo=timezone.utc),
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
            transaction_id="vel_curr",
            customer_id="cust_vel",
            merchant_id="merch_01",
            merchant_category="electronics",
            timestamp=datetime(2026, 5, 20, 10, 11, 0, tzinfo=timezone.utc),
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

        assessment = ctx["behavioral_assessment"]
        vel_dim = next(a for a in assessment["anomalies"] if a["dimension"] == "VELOCITY")
        assert vel_dim["is_anomaly"] is True
        assert vel_dim["severity"] in ("HIGH", "CRITICAL")
        assert vel_dim["evidence"]["velocity_30min"] >= 3

    def test_interval_anomaly_rapid_followup(self):
        priors = [
            TransactionInput(
                transaction_id="int_p_0",
                customer_id="cust_int",
                merchant_id="merch_01",
                merchant_category="electronics",
                timestamp=datetime(2026, 5, 20, 10, 0, 0, tzinfo=timezone.utc),
                amount=500.0,
                device_id="dev_known",
                geo_region="region_01",
                payment_method="card",
                status="success",
                account_created=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            )
        ]
        # Current transaction occurs 30 seconds after previous
        txn = TransactionInput(
            transaction_id="int_curr",
            customer_id="cust_int",
            merchant_id="merch_01",
            merchant_category="electronics",
            timestamp=datetime(2026, 5, 20, 10, 0, 30, tzinfo=timezone.utc),
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

        assessment = ctx["behavioral_assessment"]
        int_dim = next(a for a in assessment["anomalies"] if a["dimension"] == "INTERVAL")
        assert int_dim["is_anomaly"] is True
        assert int_dim["severity"] == "HIGH"
        assert "seconds" in int_dim["description"].lower() or "0.5" in int_dim["description"]

    def test_device_and_location_novelty(self):
        priors = _priors(n=3, device="dev_home", geo="region_north")
        txn = _txn(device_id="dev_unknown", geo_region="region_south")
        req = RiskRequest(transaction=txn, prior_transactions=priors, source="demo")
        row = _build_feature_row(req)
        ctx = build_investigation_context(req, row)

        assessment = ctx["behavioral_assessment"]
        dev_dim = next(a for a in assessment["anomalies"] if a["dimension"] == "DEVICE")
        assert dev_dim["is_anomaly"] is True
        assert dev_dim["severity"] == "HIGH"
        assert "dev_unknown" in dev_dim["description"]

        loc_dim = next(a for a in assessment["anomalies"] if a["dimension"] == "LOCATION")
        assert loc_dim["is_anomaly"] is True
        assert loc_dim["severity"] == "HIGH"
        assert "region_south" in loc_dim["description"]

    def test_failure_burst_anomaly(self):
        # 3 out of 5 prior transactions failed (60% failure rate)
        priors = []
        for i in range(5):
            st = "failed" if i in (1, 2, 4) else "success"
            priors.append(
                TransactionInput(
                    transaction_id=f"fail_p_{i}",
                    customer_id="cust_fail",
                    merchant_id="merch_01",
                    merchant_category="electronics",
                    timestamp=datetime.fromisoformat(f"2026-05-1{i}T10:00:00+00:00"),
                    amount=500.0,
                    device_id="dev_known",
                    geo_region="region_01",
                    payment_method="card",
                    status=st,
                    account_created=datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
                )
            )
        txn = _txn(customer_id="cust_fail", amount=500.0)
        req = RiskRequest(transaction=txn, prior_transactions=priors, source="demo")
        row = _build_feature_row(req)
        ctx = build_investigation_context(req, row)

        assessment = ctx["behavioral_assessment"]
        fail_dim = next(a for a in assessment["anomalies"] if a["dimension"] == "FAILURE_BURST")
        assert fail_dim["is_anomaly"] is True
        assert fail_dim["severity"] == "CRITICAL"
        assert "60%" in fail_dim["description"]


class TestBehavioralAnomalyAPI:
    """API integration tests verifying that /risk/evaluate returns complete behavioral assessment."""

    def test_api_returns_behavioral_assessment(self, client):
        priors = [
            dict(
                transaction_id=f"api_b_{i}", customer_id="cust_b_api", merchant_id="merch_01",
                merchant_category="electronics", timestamp=f"2026-05-1{i}T10:00:00Z", amount=450.0,
                device_id="dev_known", geo_region="region_01", payment_method="card", status="success",
                account_created="2025-01-01T00:00:00Z",
            )
            for i in range(4)
        ]
        txn = dict(
            transaction_id="api_b_curr", customer_id="cust_b_api", merchant_id="merch_01",
            merchant_category="electronics", timestamp="2026-05-20T10:05:00Z", amount=25000.0,
            device_id="dev_brand_new", geo_region="region_brand_new", payment_method="card", status="success",
            account_created="2025-01-01T00:00:00Z",
        )

        r = client.post("/risk/evaluate", json={"transaction": txn, "prior_transactions": priors, "source": "demo"})
        assert r.status_code == 200
        body = r.json()

        assert "investigation_context" in body
        ctx = body["investigation_context"]
        assert "behavioral_assessment" in ctx
        assessment = ctx["behavioral_assessment"]
        assert assessment["overall_status"] in ("CRITICAL_ANOMALIES", "ELEVATED_ANOMALIES")
        assert assessment["anomaly_count"] >= 3  # Amount surge + novel device + novel geo
        assert len(assessment["anomalies"]) == 6
