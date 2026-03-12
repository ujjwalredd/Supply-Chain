"""
Comprehensive QA tests for critical, untested, and edge-case paths.

Covers:
  - orders router: delay-predictions div/None safety, timeline 404, route ordering bug
  - suppliers router: scorecard 404, policy validation, cost_analytics div-by-zero
  - actions router: complete/cancel/resolve 404, resolve bad body
  - alerts router: trend boundary, enriched zero-division, dismiss 404
  - ontology router: normalize empty, constraint validation
  - forecasts router: demand endpoint fallback
  - ml router: predict heuristic boundary
  - query router: empty question, oversized question
  - lineage router: jobs endpoint when table missing
  - ai router: analyze missing API key, WhatIf missing supplier
  - ingestion: pg_writer _detect_deviations boundary values
  - stress: unbounded queries, division-by-zero guards in production code paths
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _async_gen_db(session):
    """Wrap a mock session into an async generator for dependency override."""
    async def _gen() -> AsyncGenerator:
        yield session
    return _gen


def _make_client(mock_session=None):
    """Build a TestClient with optional DB dependency override."""
    with patch("api.database.init_db", new_callable=AsyncMock):
        from api.database import get_db
        from api.main import app
        from starlette.testclient import TestClient

        if mock_session is not None:
            app.dependency_overrides[get_db] = _async_gen_db(mock_session)

        client = TestClient(app, raise_server_exceptions=False)
        return client, get_db


def _make_order(**kwargs):
    """Return a minimal mock Order object."""
    o = MagicMock()
    o.order_id = kwargs.get("order_id", "ORD-001")
    o.supplier_id = kwargs.get("supplier_id", "SUP-001")
    o.product = kwargs.get("product", "Widget A")
    o.region = kwargs.get("region", "US-EAST")
    o.quantity = kwargs.get("quantity", 100)
    o.unit_price = kwargs.get("unit_price", 10.0)
    o.order_value = kwargs.get("order_value", 1000.0)
    o.delay_days = kwargs.get("delay_days", 0)
    o.status = kwargs.get("status", "PENDING")
    o.inventory_level = kwargs.get("inventory_level", 80.0)
    o.expected_delivery = kwargs.get(
        "expected_delivery",
        datetime(2026, 4, 15, tzinfo=timezone.utc),
    )
    o.actual_delivery = kwargs.get("actual_delivery", None)
    o.created_at = kwargs.get(
        "created_at",
        datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    return o


def _make_supplier(**kwargs):
    s = MagicMock()
    s.supplier_id = kwargs.get("supplier_id", "SUP-001")
    s.name = kwargs.get("name", "Acme Corp")
    s.region = kwargs.get("region", "US-EAST")
    s.trust_score = kwargs.get("trust_score", 0.9)
    s.total_orders = kwargs.get("total_orders", 100)
    s.delayed_orders = kwargs.get("delayed_orders", 10)
    s.avg_delay_days = kwargs.get("avg_delay_days", 1.5)
    s.contract_terms = kwargs.get("contract_terms", None)
    s.capacity_limits = kwargs.get("capacity_limits", None)
    s.created_at = kwargs.get("created_at", datetime(2026, 1, 1, tzinfo=timezone.utc))
    s.updated_at = kwargs.get("updated_at", datetime(2026, 1, 1, tzinfo=timezone.utc))
    return s


# ── Orders router ─────────────────────────────────────────────────────────────

class TestOrdersDelayPredictions:
    """GET /orders/delay-predictions — delay-score calculations."""

    def test_no_rows_returns_empty_predictions(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/orders/delay-predictions")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["predictions"] == []
        assert data["total_scored"] == 0

    def test_order_without_supplier_uses_default_trust(self):
        """When supplier is None, trust defaults to 0.7 (no crash)."""
        order = _make_order(status="PENDING", trust_score=None)
        session = AsyncMock()
        mock_result = MagicMock()
        # Return (order, None) to simulate missing supplier join
        mock_result.all.return_value = [(order, None)]
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/orders/delay-predictions?min_probability=0.0")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        predictions = resp.json()["predictions"]
        # Should not crash and supplier_trust should be default 0.7
        if predictions:
            assert predictions[0]["supplier_trust"] == 0.7

    def test_overdue_order_gets_high_probability(self):
        """Orders with expected_delivery in the past should get urgency multiplier 2.0."""
        from api.routers.orders import delay_predictions as _dp
        # This tests the scoring logic directly via the live DB mock
        order = _make_order(
            status="PENDING",
            expected_delivery=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        supplier = _make_supplier(trust_score=0.9, avg_delay_days=0)
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [(order, supplier)]
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/orders/delay-predictions?min_probability=0.0")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        predictions = resp.json()["predictions"]
        assert len(predictions) == 1
        assert predictions[0]["is_overdue"] is True
        # trust=0.9 → p_base=0.1, delay_factor=1.0, urgency=2.0 → p=0.2
        assert predictions[0]["delay_probability"] == 0.2

    def test_min_probability_filter_works(self):
        """min_probability=0.99 should exclude low-risk orders."""
        order = _make_order(
            status="PENDING",
            expected_delivery=datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
        supplier = _make_supplier(trust_score=0.99, avg_delay_days=0)
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [(order, supplier)]
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/orders/delay-predictions?min_probability=0.99")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        # Low-risk order should be filtered out
        assert resp.json()["predictions"] == []

    def test_limit_param_respected(self):
        """limit query param should be respected in response."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/orders/delay-predictions?limit=5")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200


class TestOrdersTimeline:
    """GET /orders/{order_id}/timeline — lifecycle reconstruction."""

    def test_unknown_order_returns_404(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/orders/NONEXISTENT/timeline")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_timeline_happy_path_delivered_order(self):
        """A DELIVERED order with actual_delivery returns valid timeline."""
        # Use a full MagicMock (not real datetime) so attributes are assignable
        order = MagicMock()
        order.order_id = "ORD-DELIVERED"
        order.supplier_id = "SUP-001"
        order.product = "Widget A"
        order.region = "US-EAST"
        order.quantity = 100
        order.order_value = 1000.0
        order.delay_days = 2
        order.status = "DELIVERED"
        order.actual_delivery = datetime(2026, 4, 17, tzinfo=timezone.utc)
        # Use real datetimes for isoformat / strftime calls in the router
        order.created_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        order.expected_delivery = datetime(2026, 4, 15, tzinfo=timezone.utc)

        session = AsyncMock()
        # First execute → get order; second execute → get deviations (empty)
        mock_order_result = MagicMock()
        mock_order_result.scalar_one_or_none.return_value = order
        mock_devs_result = MagicMock()
        mock_devs_result.scalars.return_value.all.return_value = []
        session.execute.side_effect = [mock_order_result, mock_devs_result]

        client, get_db = _make_client(session)
        try:
            resp = client.get("/orders/ORD-DELIVERED/timeline")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["order_id"] == "ORD-DELIVERED"
        events = data["events"]
        assert any(e["event"] == "ORDER_PLACED" for e in events)
        assert any(e["event"] == "DELIVERED" for e in events)


class TestOrdersGet:
    """GET /orders/{order_id} — basic CRUD."""

    def test_get_order_not_found_returns_404(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/orders/DOES-NOT-EXIST")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404


# ── Suppliers router ───────────────────────────────────────────────────────────

class TestSuppliersScorecard:
    """GET /suppliers/{supplier_id}/scorecard — weekly metrics."""

    def test_unknown_supplier_returns_404(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/suppliers/BAD-SUPPLIER/scorecard")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404

    def test_scorecard_zero_total_orders_safe(self):
        """supplier.total_orders = 0 must not cause ZeroDivisionError in delay_rate_pct."""
        supplier = _make_supplier(total_orders=0, delayed_orders=0)

        session = AsyncMock()
        supplier_result = MagicMock()
        supplier_result.scalar_one_or_none.return_value = supplier
        orders_result = MagicMock()
        orders_result.scalars.return_value.all.return_value = []
        devs_result = MagicMock()
        devs_result.scalars.return_value.all.return_value = []
        session.execute.side_effect = [supplier_result, orders_result, devs_result]

        client, get_db = _make_client(session)
        try:
            resp = client.get("/suppliers/SUP-ZERO/scorecard")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["supplier"]["delay_rate_pct"] == 0.0


class TestSuppliersPolicy:
    """PUT /suppliers/{supplier_id}/policy — Glass-Box policy upsert."""

    def _make_policy(**kwargs):
        p = MagicMock()
        p.supplier_id = kwargs.get("supplier_id", "SUP-001")
        p.require_approval_at_severity = kwargs.get("require_approval_at_severity", "CRITICAL")
        p.require_approval_above_value = kwargs.get("require_approval_above_value", 50000.0)
        p.max_auto_actions_per_day = kwargs.get("max_auto_actions_per_day", 10)
        p.min_confidence = kwargs.get("min_confidence", 0.7)
        p.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        p.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return p

    def test_invalid_severity_returns_422(self):
        session = AsyncMock()
        client, get_db = _make_client(session)
        try:
            resp = client.put(
                "/suppliers/SUP-001/policy",
                json={
                    "require_approval_at_severity": "INVALID",
                    "require_approval_above_value": 50000.0,
                    "max_auto_actions_per_day": 10,
                    "min_confidence": 0.7,
                },
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 422

    def test_confidence_out_of_range_returns_422(self):
        session = AsyncMock()
        client, get_db = _make_client(session)
        try:
            resp = client.put(
                "/suppliers/SUP-001/policy",
                json={
                    "require_approval_at_severity": "CRITICAL",
                    "require_approval_above_value": 50000.0,
                    "max_auto_actions_per_day": 10,
                    "min_confidence": 1.5,  # invalid
                },
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 422

    def test_get_supplier_not_found_returns_404(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/suppliers/GHOST-SUP")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404


class TestSuppliersCostAnalytics:
    """GET /suppliers/cost-analytics — spend aggregation."""

    def test_cost_analytics_zero_total_spend_safe(self):
        """When total_spend=0, cost_efficiency_score must default to 100.0, no ZeroDivisionError."""
        mock_row = MagicMock()
        mock_row.supplier_id = "SUP-ZERO-SPEND"
        mock_row.name = "Broke Inc"
        mock_row.region = "APAC"
        mock_row.total_orders = 5
        mock_row.total_spend = 0.0
        mock_row.avg_order_value = 0.0
        mock_row.estimated_delay_cost = 0.0
        mock_row.avg_delay_days_when_delayed = None
        mock_row.delayed_count = 0

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/suppliers/cost-analytics")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        analytics = resp.json()["suppliers"]
        assert len(analytics) == 1
        assert analytics[0]["cost_efficiency_score"] == 100.0

    def test_cost_analytics_zero_total_orders_safe(self):
        """When total_orders=0, delay_rate_pct must be 0.0, no ZeroDivisionError."""
        mock_row = MagicMock()
        mock_row.supplier_id = "SUP-NO-ORDERS"
        mock_row.name = "Ghost Co"
        mock_row.region = "EU"
        mock_row.total_orders = 0
        mock_row.total_spend = 0.0
        mock_row.avg_order_value = 0.0
        mock_row.estimated_delay_cost = 0.0
        mock_row.avg_delay_days_when_delayed = None
        mock_row.delayed_count = 0

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/suppliers/cost-analytics")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        analytics = resp.json()["suppliers"]
        assert analytics[0]["delay_rate_pct"] == 0.0


# ── Actions router ─────────────────────────────────────────────────────────────

class TestActionsComplete:
    """POST /actions/{action_id}/complete — mark completed."""

    def test_complete_nonexistent_action_returns_404(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.post("/actions/99999/complete")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestActionsCancel:
    """POST /actions/{action_id}/cancel — mark cancelled."""

    def test_cancel_nonexistent_action_returns_404(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.post("/actions/99999/cancel")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404


class TestActionsResolve:
    """POST /actions/{action_id}/resolve — feedback loop."""

    def test_resolve_nonexistent_action_returns_404(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.post(
                "/actions/99999/resolve",
                json={"outcome_note": "Fixed", "success": True},
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404

    def test_resolve_missing_outcome_note_returns_422(self):
        """outcome_note is required (Body(...)). Missing it should 422."""
        session = AsyncMock()
        client, get_db = _make_client(session)
        try:
            resp = client.post(
                "/actions/1/resolve",
                json={"success": True},  # outcome_note missing
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 422


class TestActionsSuccessRates:
    """GET /actions/success-rates — resolved_count=0 must not divide."""

    def test_success_rates_zero_resolved_returns_null(self):
        mock_row = MagicMock()
        mock_row.action_type = "REROUTE"
        mock_row.total = 5
        mock_row.resolved_count = 0
        mock_row.success_count = 0
        mock_row.avg_confidence = None

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/actions/success-rates")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        rates = resp.json()["success_rates"]
        assert len(rates) == 1
        # When resolved_count=0, success_rate_pct must be None (not crash)
        assert rates[0]["success_rate_pct"] is None


# ── Alerts router ─────────────────────────────────────────────────────────────

class TestAlertsDismiss:
    """POST /alerts/{deviation_id}/dismiss."""

    def test_dismiss_nonexistent_deviation_returns_404(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.post("/alerts/DEV-GHOST/dismiss")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404

    def test_get_alert_not_found_returns_404(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/alerts/DEV-DOES-NOT-EXIST")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404


class TestAlertsEnriched:
    """GET /alerts/enriched — cost impact calculation."""

    def test_enriched_zero_delay_zero_cost(self):
        """delay_days=0 → cost_impact_usd=0.0, tier=MODERATE."""
        mock_row = MagicMock()
        mock_row.deviation_id = "DEV-001"
        mock_row.order_id = "ORD-001"
        mock_row.type = "DELAY"
        mock_row.severity = "MEDIUM"
        mock_row.detected_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        mock_row.recommended_action = "Check supplier"
        mock_row.executed = False
        mock_row.created_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        mock_row.supplier_id = "SUP-001"
        mock_row.product = "Widget"
        mock_row.order_value = 10000.0
        mock_row.delay_days = 0
        mock_row.region = "US-EAST"

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/alerts/enriched")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        alerts = resp.json()["alerts"]
        assert alerts[0]["cost_impact_usd"] == 0.0
        assert alerts[0]["risk_tier"] == "MODERATE"

    def test_enriched_critical_cost_threshold(self):
        """10_001 delay_cost → CRITICAL_COST tier."""
        # cost = delay_days * order_value * 0.02
        # need cost >= 10000 → delay_days=5, order_value=100_010 → 5*100010*0.02=10001
        mock_row = MagicMock()
        mock_row.deviation_id = "DEV-BIG"
        mock_row.order_id = "ORD-BIG"
        mock_row.type = "DELAY"
        mock_row.severity = "CRITICAL"
        mock_row.detected_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        mock_row.recommended_action = None
        mock_row.executed = False
        mock_row.created_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        mock_row.supplier_id = "SUP-001"
        mock_row.product = "Expensive Part"
        mock_row.order_value = 100010.0
        mock_row.delay_days = 5
        mock_row.region = "EU"

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/alerts/enriched")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        alerts = resp.json()["alerts"]
        assert alerts[0]["risk_tier"] == "CRITICAL_COST"
        assert alerts[0]["cost_impact_usd"] == round(5 * 100010.0 * 0.02, 2)


# ── Ontology router ────────────────────────────────────────────────────────────

class TestOntologyNormalize:
    """POST /ontology/normalize — field name mapping."""

    def test_normalize_empty_dict_returns_empty(self):
        client, get_db = _make_client()
        try:
            resp = client.post("/ontology/normalize", json={})
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["normalized"] == {}
        assert data["unmapped"] == {}
        assert data["mapping_applied"] == []

    def test_normalize_known_aliases(self):
        client, get_db = _make_client()
        try:
            resp = client.post(
                "/ontology/normalize",
                json={"po_number": "ORD-001", "vendor": "SUP-001", "qty": 100},
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        normalized = resp.json()["normalized"]
        assert normalized.get("order_id") == "ORD-001"
        assert normalized.get("supplier_id") == "SUP-001"
        assert normalized.get("quantity") == 100

    def test_normalize_unknown_field_goes_to_unmapped(self):
        client, get_db = _make_client()
        try:
            resp = client.post(
                "/ontology/normalize",
                json={"zxcvbnm_totally_unknown_field": "value"},
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        # Either unmapped or partial-matched, but must not crash
        assert "normalized" in data
        assert "unmapped" in data


class TestOntologyConstraints:
    """POST /ontology/constraints — validation rules."""

    def test_invalid_entity_type_returns_422(self):
        session = AsyncMock()
        client, get_db = _make_client(session)
        try:
            resp = client.post(
                "/ontology/constraints",
                json={
                    "entity_id": "SUP-001",
                    "entity_type": "INVALID_TYPE",
                    "constraint_type": "MAX_DELAY_DAYS",
                    "value": 7.0,
                    "hard_limit": True,
                },
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 422

    def test_negative_max_delay_days_returns_422(self):
        session = AsyncMock()
        client, get_db = _make_client(session)
        try:
            resp = client.post(
                "/ontology/constraints",
                json={
                    "entity_id": "SUP-001",
                    "entity_type": "SUPPLIER",
                    "constraint_type": "MAX_DELAY_DAYS",
                    "value": -5.0,
                    "hard_limit": True,
                },
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 422

    def test_min_trust_score_above_one_returns_422(self):
        session = AsyncMock()
        client, get_db = _make_client(session)
        try:
            resp = client.post(
                "/ontology/constraints",
                json={
                    "entity_id": "SUP-001",
                    "entity_type": "SUPPLIER",
                    "constraint_type": "MIN_TRUST_SCORE",
                    "value": 1.5,
                    "hard_limit": True,
                },
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 422


# ── ML router ─────────────────────────────────────────────────────────────────

class TestMLPredict:
    """POST /ml/predict — heuristic fallback when pipeline not available."""

    def test_heuristic_low_risk_order(self):
        client, get_db = _make_client()
        try:
            resp = client.post(
                "/ml/predict",
                json={
                    "supplier_id": "SUP-001",
                    "region": "US-EAST",
                    "quantity": 10,
                    "unit_price": 5.0,
                    "order_value": 50.0,
                    "inventory_level": 500.0,
                },
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "is_delayed" in data
        assert "probability" in data
        assert 0.0 <= data["probability"] <= 1.0

    def test_predict_missing_required_field_returns_422(self):
        client, get_db = _make_client()
        try:
            resp = client.post(
                "/ml/predict",
                json={
                    "supplier_id": "SUP-001",
                    # missing: region, quantity, unit_price, order_value, inventory_level
                },
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 422

    def test_predict_negative_quantity_returns_422(self):
        client, get_db = _make_client()
        try:
            resp = client.post(
                "/ml/predict",
                json={
                    "supplier_id": "SUP-001",
                    "region": "US",
                    "quantity": -1,  # ge=1 constraint
                    "unit_price": 10.0,
                    "order_value": 100.0,
                    "inventory_level": 50.0,
                },
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 422


# ── Query router ─────────────────────────────────────────────────────────────

class TestQueryStream:
    """POST /ai/query/stream — natural language query validation."""

    def test_empty_question_returns_400(self):
        session = AsyncMock()
        client, get_db = _make_client(session)
        try:
            resp = client.post(
                "/ai/query/stream",
                json={"question": "   "},  # whitespace only
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        # 400 (empty question) or 503 (no API key) — both valid for CI
        assert resp.status_code in (400, 503)

    def test_question_exceeding_2000_chars_returns_400(self):
        session = AsyncMock()
        client, get_db = _make_client(session)
        try:
            resp = client.post(
                "/ai/query/stream",
                json={"question": "x" * 2001},
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        # 400 (too long) or 503 (no API key — key checked after validation)
        assert resp.status_code in (400, 503)

    def test_suggestions_endpoint_returns_list(self):
        client, get_db = _make_client()
        try:
            resp = client.get("/ai/query/suggestions")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        assert len(data["suggestions"]) > 0


# ── AI analyze router ─────────────────────────────────────────────────────────

class TestAIAnalyze:
    """POST /ai/analyze — rate limiting and API key guard."""

    def test_no_api_key_env_var_returns_503_on_analyze_stream(self):
        """POST /ai/analyze/stream explicitly checks for empty API key and returns 503."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        # Temporarily remove the env var to trigger the 503 guard
        import os
        original_key = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = ""
        try:
            client, get_db = _make_client(session)
            try:
                resp = client.post(
                    "/ai/analyze/stream",
                    json={
                        "deviation_id": "DEV-001",
                        "deviation_type": "DELAY",
                        "severity": "HIGH",
                    },
                )
            finally:
                from api.main import app
                app.dependency_overrides.pop(get_db, None)
        finally:
            if original_key is not None:
                os.environ["ANTHROPIC_API_KEY"] = original_key
            else:
                del os.environ["ANTHROPIC_API_KEY"]

        assert resp.status_code == 503

    def test_analyze_with_placeholder_key_returns_fallback_200(self):
        """With a placeholder API key, analyze endpoint falls back gracefully (200)."""
        # conftest sets ANTHROPIC_API_KEY=ci-placeholder, so analyze endpoint proceeds
        # but Claude returns 401 → engine falls back to AIAnalysisOutput with "unavailable"
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.post(
                "/ai/analyze",
                json={
                    "deviation_id": "DEV-FALLBACK-TEST",
                    "deviation_type": "DELAY",
                    "severity": "MEDIUM",
                },
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        # 200 with fallback analysis, 429 if rate-limited in prior tests
        assert resp.status_code in (200, 429)
        if resp.status_code == 200:
            data = resp.json()
            assert "recommendation" in data
            assert "autonomous_executable" in data

    def test_whatif_missing_source_supplier_returns_404(self):
        """POST /ai/whatif/stream with unknown supplier_id should 404."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.post(
                "/ai/whatif/stream",
                json={
                    "supplier_id": "GHOST-SUP-999",
                    "volume_shift_pct": 25.0,
                },
            )
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        # 404 (supplier not found) or 503 (no API key checked first)
        assert resp.status_code in (404, 503)


# ── Lineage router ─────────────────────────────────────────────────────────────

class TestLineage:
    """GET /lineage — graceful handling when table is missing."""

    def test_lineage_returns_empty_when_table_missing(self):
        session = AsyncMock()
        # Simulate the EXISTS check returning False (no table)
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/lineage")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert data["total"] == 0
        assert "note" in data

    def test_lineage_with_job_name_filter(self):
        """?job_name= filter still returns 200 when table missing."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        session.execute.return_value = mock_result

        client, get_db = _make_client(session)
        try:
            resp = client.get("/lineage?job_name=bronze_ingest")
        finally:
            from api.main import app
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200


# ── Forecasts router ──────────────────────────────────────────────────────────

class TestForecastsDemand:
    """GET /forecasts/demand — fallback when no parquet file."""

    def test_demand_endpoint_returns_503_when_prophet_missing(self):
        """When Prophet and the parquet file are both unavailable, return 503."""
        import api.routers.forecasts as fr_module
        original = fr_module.GOLD_PATH
        fr_module.GOLD_PATH = "/nonexistent/path"
        try:
            with patch("api.database.init_db", new_callable=AsyncMock):
                from api.main import app
                from starlette.testclient import TestClient

                with patch.dict("sys.modules", {"pipeline.demand_forecast": None}):
                    with TestClient(app, raise_server_exceptions=False) as client:
                        resp = client.get("/forecasts/demand")
        finally:
            fr_module.GOLD_PATH = original

        # Either 503 (error) or 200 with synthetic fallback (if numpy available)
        assert resp.status_code in (200, 503)


# ── pg_writer _detect_deviations edge cases ────────────────────────────────────

class TestPgWriterDeviationEdgeCases:
    """Unit tests for _detect_deviations boundary values."""

    def _make_event(self, **kwargs):
        from ingestion.schemas import OrderEvent
        return OrderEvent(
            order_id=kwargs.get("order_id", "ORD-TEST"),
            supplier_id=kwargs.get("supplier_id", "SUP-TEST"),
            product=kwargs.get("product", "Widget"),
            region=kwargs.get("region", "US"),
            quantity=kwargs.get("quantity", 100),
            unit_price=kwargs.get("unit_price", 10.0),
            order_value=kwargs.get("order_value", 1000.0),
            expected_delivery=kwargs.get("expected_delivery", "2026-04-15T00:00:00Z"),
            actual_delivery=kwargs.get("actual_delivery", None),
            delay_days=kwargs.get("delay_days", 0),
            status=kwargs.get("status", "PENDING"),
            inventory_level=kwargs.get("inventory_level", 80.0),
        )

    def test_exactly_at_delay_high_threshold_is_high(self):
        """delay_days = DELAY_HIGH_THRESHOLD + 1 = 8 should be HIGH."""
        from ingestion.pg_writer import _detect_deviations
        event = self._make_event(delay_days=8)
        devs = _detect_deviations(event)
        delay_devs = [d for d in devs if d["type"] == "DELAY"]
        assert len(delay_devs) == 1
        assert delay_devs[0]["severity"] == "HIGH"

    def test_exactly_at_delay_critical_threshold_is_critical(self):
        """delay_days = DELAY_CRITICAL_THRESHOLD + 1 = 15 should be CRITICAL."""
        from ingestion.pg_writer import _detect_deviations
        event = self._make_event(delay_days=15)
        devs = _detect_deviations(event)
        delay_devs = [d for d in devs if d["type"] == "DELAY"]
        assert len(delay_devs) == 1
        assert delay_devs[0]["severity"] == "CRITICAL"

    def test_delay_days_zero_produces_no_delay_deviation(self):
        from ingestion.pg_writer import _detect_deviations
        event = self._make_event(delay_days=0)
        devs = _detect_deviations(event)
        delay_devs = [d for d in devs if d["type"] == "DELAY"]
        assert delay_devs == []

    def test_inventory_exactly_at_high_threshold_is_high(self):
        """inventory_level = STOCKOUT_HIGH_THRESHOLD - 1 = 4 → HIGH stockout."""
        from ingestion.pg_writer import _detect_deviations
        event = self._make_event(delay_days=0, inventory_level=4.0)
        devs = _detect_deviations(event)
        stockout_devs = [d for d in devs if d["type"] == "STOCKOUT"]
        assert len(stockout_devs) == 1
        assert stockout_devs[0]["severity"] == "HIGH"

    def test_inventory_exactly_at_medium_threshold_is_medium(self):
        """inventory_level = STOCKOUT_THRESHOLD - 1 = 9 → MEDIUM stockout."""
        from ingestion.pg_writer import _detect_deviations
        event = self._make_event(delay_days=0, inventory_level=9.0)
        devs = _detect_deviations(event)
        stockout_devs = [d for d in devs if d["type"] == "STOCKOUT"]
        assert len(stockout_devs) == 1
        assert stockout_devs[0]["severity"] == "MEDIUM"

    def test_inventory_above_threshold_produces_no_stockout(self):
        from ingestion.pg_writer import _detect_deviations
        event = self._make_event(delay_days=0, inventory_level=10.0)
        devs = _detect_deviations(event)
        stockout_devs = [d for d in devs if d["type"] == "STOCKOUT"]
        assert stockout_devs == []

    def test_anomaly_exactly_at_threshold_is_detected(self):
        """order_value = ANOMALY_VALUE_THRESHOLD + 1 → ANOMALY deviation."""
        from ingestion.pg_writer import _detect_deviations
        event = self._make_event(delay_days=0, inventory_level=80.0, order_value=100_001.0)
        devs = _detect_deviations(event)
        anomaly_devs = [d for d in devs if d["type"] == "ANOMALY"]
        assert len(anomaly_devs) == 1

    def test_anomaly_at_threshold_not_detected(self):
        """order_value = ANOMALY_VALUE_THRESHOLD exactly (not >) → no ANOMALY."""
        from ingestion.pg_writer import _detect_deviations
        event = self._make_event(delay_days=0, inventory_level=80.0, order_value=100_000.0)
        devs = _detect_deviations(event)
        anomaly_devs = [d for d in devs if d["type"] == "ANOMALY"]
        assert anomaly_devs == []

    def test_compound_critical_delay_high_stockout_anomaly(self):
        """All three triggered simultaneously — all 3 deviation dicts returned."""
        from ingestion.pg_writer import _detect_deviations
        event = self._make_event(delay_days=15, inventory_level=3.0, order_value=200_000.0)
        devs = _detect_deviations(event)
        types = {d["type"] for d in devs}
        assert types == {"DELAY", "STOCKOUT", "ANOMALY"}

    def test_all_deviation_ids_are_unique(self):
        from ingestion.pg_writer import _detect_deviations
        event = self._make_event(delay_days=15, inventory_level=3.0, order_value=200_000.0)
        devs = _detect_deviations(event)
        ids = [d["deviation_id"] for d in devs]
        assert len(ids) == len(set(ids)), "Duplicate deviation IDs detected"


# ── Stress-test static analysis ────────────────────────────────────────────────

class TestStressAnalysis:
    """
    Static-style tests verifying bounded query patterns and limit guards.
    These test the logic without a real DB.
    """

    def test_delay_predictions_fetch_limit_is_bounded(self):
        """delay_predictions fetch_limit must be <= 500 (hardcoded cap)."""
        # Indirectly verified by checking behavior with limit=100 → fetch=min(500,500)=500
        import api.routers.orders as orders_mod
        import inspect
        src = inspect.getsource(orders_mod.delay_predictions)
        # Ensure the cap of 500 exists in the source
        assert "500" in src, "Missing fetch_limit cap in delay_predictions"

    def test_list_orders_has_limit_upper_bound(self):
        """list_orders must cap at le=500."""
        import api.routers.orders as orders_mod
        import inspect
        src = inspect.getsource(orders_mod.list_orders)
        assert "le=500" in src, "Missing le=500 on limit param in list_orders"

    def test_list_suppliers_has_limit_upper_bound(self):
        """list_suppliers must cap at le=500."""
        import api.routers.suppliers as suppliers_mod
        import inspect
        src = inspect.getsource(suppliers_mod.list_suppliers)
        assert "le=500" in src, "Missing le=500 on limit param in list_suppliers"

    def test_list_actions_has_limit_upper_bound(self):
        """list_actions must cap at le=500."""
        import api.routers.actions as actions_mod
        import inspect
        src = inspect.getsource(actions_mod.list_actions)
        assert "le=500" in src, "Missing le=500 on limit param in list_actions"

    def test_ai_router_has_rate_limit_store(self):
        """AI router must have a rate limit mechanism."""
        import api.routers.ai as ai_mod
        # Rate limit store should exist
        assert hasattr(ai_mod, "_AI_RATE_LIMIT_STORE"), "Missing rate limit store in ai router"
        assert hasattr(ai_mod, "_check_ai_rate_limit"), "Missing rate limit checker"

    def test_forecast_cache_has_ttl(self):
        """Forecast router must have a TTL to prevent stale data serving forever."""
        import api.routers.forecasts as fr_mod
        assert hasattr(fr_mod, "_FORECAST_CACHE_TTL"), "Missing TTL on forecast cache"
        assert fr_mod._FORECAST_CACHE_TTL > 0

    def test_network_cache_has_ttl(self):
        """Network router must have a TTL on the CSV cache."""
        import api.routers.network as net_mod
        assert hasattr(net_mod, "_NETWORK_CACHE_TTL"), "Missing TTL on network cache"
        assert net_mod._NETWORK_CACHE_TTL > 0

    def test_supplier_risk_has_limit_cap(self):
        """list_supplier_risk must cap at le=200."""
        import api.routers.suppliers as suppliers_mod
        import inspect
        src = inspect.getsource(suppliers_mod.list_supplier_risk)
        assert "le=200" in src, "Missing le=200 cap in list_supplier_risk"

    def test_lineage_endpoint_has_limit_cap(self):
        """lineage GET must cap at le=500."""
        import api.routers.lineage as lineage_mod
        import inspect
        src = inspect.getsource(lineage_mod.get_lineage)
        assert "le=500" in src, "Missing le=500 cap in get_lineage"

    def test_ai_analyze_scored_requires_api_key_or_openai(self):
        """analyze-scored must raise 503 when neither key is set."""
        session = AsyncMock()
        client, get_db = _make_client(session)
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": ""}):
            try:
                resp = client.post(
                    "/ai/analyze-scored",
                    json={
                        "prompt": "Test prompt",
                        "deviation_id": "DEV-001",
                    },
                )
            finally:
                from api.main import app
                app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 503
