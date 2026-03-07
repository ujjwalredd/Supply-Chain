"""Unit tests for ingestion/pg_writer.py — no live Kafka or Postgres required."""

from datetime import datetime, timezone

import pytest

from ingestion.pg_writer import _detect_deviations
from ingestion.schemas import OrderEvent


def _make_event(**kwargs) -> OrderEvent:
    defaults = {
        "order_id": "ORD-TEST-000001",
        "supplier_id": "SUP-001",
        "product": "WIDGET-A",
        "region": "NA",
        "quantity": 100,
        "unit_price": 50.0,
        "order_value": 5000.0,
        "expected_delivery": "2026-04-01",
        "actual_delivery": None,
        "delay_days": 0,
        "status": "IN_TRANSIT",
        "inventory_level": 50.0,
    }
    defaults.update(kwargs)
    return OrderEvent.model_validate(defaults)


# ── Delay detection ──────────────────────────────────────────────────────────

def test_no_deviation_on_clean_event():
    event = _make_event()
    devs = _detect_deviations(event)
    assert devs == []


def test_medium_delay_detected():
    event = _make_event(delay_days=3, status="DELAYED")
    devs = _detect_deviations(event)
    delay_devs = [d for d in devs if d["type"] == "DELAY"]
    assert len(delay_devs) == 1
    assert delay_devs[0]["severity"] == "MEDIUM"


def test_high_delay_detected():
    event = _make_event(delay_days=10, status="DELAYED")
    devs = _detect_deviations(event)
    delay_devs = [d for d in devs if d["type"] == "DELAY"]
    assert len(delay_devs) == 1
    assert delay_devs[0]["severity"] == "HIGH"


def test_critical_delay_detected():
    event = _make_event(delay_days=15, status="DELAYED")
    devs = _detect_deviations(event)
    delay_devs = [d for d in devs if d["type"] == "DELAY"]
    assert len(delay_devs) == 1
    assert delay_devs[0]["severity"] == "CRITICAL"


# ── Stockout detection ───────────────────────────────────────────────────────

def test_medium_stockout_detected():
    event = _make_event(inventory_level=7.0)
    devs = _detect_deviations(event)
    stockout_devs = [d for d in devs if d["type"] == "STOCKOUT"]
    assert len(stockout_devs) == 1
    assert stockout_devs[0]["severity"] == "MEDIUM"


def test_high_stockout_detected():
    event = _make_event(inventory_level=2.0)
    devs = _detect_deviations(event)
    stockout_devs = [d for d in devs if d["type"] == "STOCKOUT"]
    assert len(stockout_devs) == 1
    assert stockout_devs[0]["severity"] == "HIGH"


def test_no_stockout_above_threshold():
    event = _make_event(inventory_level=15.0)
    devs = _detect_deviations(event)
    assert not any(d["type"] == "STOCKOUT" for d in devs)


# ── Anomaly detection ────────────────────────────────────────────────────────

def test_value_spike_anomaly_detected():
    event = _make_event(order_value=150_000.0)
    devs = _detect_deviations(event)
    anomaly_devs = [d for d in devs if d["type"] == "ANOMALY"]
    assert len(anomaly_devs) == 1
    assert anomaly_devs[0]["severity"] == "MEDIUM"


def test_no_anomaly_below_threshold():
    event = _make_event(order_value=50_000.0)
    devs = _detect_deviations(event)
    assert not any(d["type"] == "ANOMALY" for d in devs)


# ── Compound deviations ──────────────────────────────────────────────────────

def test_compound_delay_and_stockout():
    """A delayed order with low inventory generates two separate deviations."""
    event = _make_event(delay_days=10, inventory_level=3.0, status="DELAYED")
    devs = _detect_deviations(event)
    types = {d["type"] for d in devs}
    assert "DELAY" in types
    assert "STOCKOUT" in types


# ── Deviation schema ─────────────────────────────────────────────────────────

def test_deviation_has_required_fields():
    event = _make_event(delay_days=10, status="DELAYED")
    devs = _detect_deviations(event)
    for d in devs:
        assert "deviation_id" in d
        assert "order_id" in d
        assert "type" in d
        assert "severity" in d
        assert "detected_at" in d
        assert "recommended_action" in d
        assert d["order_id"] == event.order_id


def test_deviation_ids_are_unique():
    """Each detected deviation must have a unique ID."""
    event = _make_event(delay_days=15, inventory_level=2.0, order_value=200_000.0, status="DELAYED")
    devs = _detect_deviations(event)
    ids = [d["deviation_id"] for d in devs]
    assert len(ids) == len(set(ids)), "Duplicate deviation_ids detected"
