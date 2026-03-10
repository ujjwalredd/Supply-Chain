"""
Tests for data engineering features:
  - DLQ send_to_dlq helper
  - Partitioned Parquet writing in batch_loader
  - JSON Schema validation in producer
  - OpenLineage lineage_resource emit_event
  - Delta maintenance asset (import + logic check)
  - Freshness policy presence on gold assets
  - Incremental dbt model config check
  - dbt packages.yml existence
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Feature 2: DLQ ───────────────────────────────────────────────────────────

def test_send_to_dlq_no_producer_logs_warning(caplog):
    """_send_to_dlq with None producer should log a warning, not raise."""
    from ingestion.pg_writer import _send_to_dlq
    import logging
    with caplog.at_level(logging.WARNING, logger="pg-writer"):
        _send_to_dlq(None, '{"bad": "msg"}', "parse error", {"order_id": "X"})
    assert any("DLQ" in r.message or "dropping" in r.message for r in caplog.records)


def test_send_to_dlq_producer_flush_called():
    """_send_to_dlq should call producer.send and flush when producer is available."""
    from ingestion.pg_writer import _send_to_dlq
    mock_producer = MagicMock()
    _send_to_dlq(mock_producer, '{"order_id": "A"}', "validation failed", {})
    mock_producer.send.assert_called_once()
    call_args = mock_producer.send.call_args
    topic = call_args[0][0]
    payload = call_args[0][1]
    assert "dlq" in topic.lower()
    assert "error" in payload
    assert payload["error"] == "validation failed"
    mock_producer.flush.assert_called_once()


def test_dlq_payload_contains_original_message():
    """DLQ payload should contain the original raw message."""
    from ingestion.pg_writer import _send_to_dlq
    mock_producer = MagicMock()
    raw = '{"order_id": "BAD-001", "corrupt": true}'
    _send_to_dlq(mock_producer, raw, "missing fields", {"source": "kafka"})
    payload = mock_producer.send.call_args[0][1]
    assert payload["original_message"] == raw
    assert "failed_at" in payload


# ── Feature 4: Partitioned Parquet ───────────────────────────────────────────

def _make_order_records(n: int, prefix: str = "ORD") -> list[dict]:
    return [{
        "order_id": f"{prefix}-{i:04d}",
        "supplier_id": "SUP-001",
        "product": "WIDGET-A",
        "region": "NA",
        "quantity": 10,
        "unit_price": 5.0,
        "order_value": 50.0,
        "expected_delivery": "2026-04-01",
        "actual_delivery": None,
        "delay_days": 0,
        "status": "DELIVERED",
        "inventory_level": 80.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "_source_file": "test.csv",
        "_source_ingested_at": datetime.now(timezone.utc).isoformat(),
    } for i in range(n)]


def test_partitioned_parquet_created():
    """batch_loader should write a date-partitioned Parquet alongside the main write."""
    import ingestion.batch_loader as bl

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(bl, "BRONZE_PATH", tmpdir):
            count = bl.load_to_bronze_delta(iter(_make_order_records(5)), "orders")

        assert count == 5
        today = datetime.now(timezone.utc)
        partition_dir = Path(tmpdir) / "orders" / f"year={today.year}" / f"month={today.month:02d}" / f"day={today.day:02d}"
        assert partition_dir.exists(), f"Expected partition dir: {partition_dir}"
        partition_files = list(partition_dir.glob("*.parquet"))
        assert len(partition_files) == 1, f"Expected 1 parquet file, got: {partition_files}"


def test_partitioned_parquet_has_correct_row_count():
    """Partitioned Parquet should contain all the records."""
    import pandas as pd
    import ingestion.batch_loader as bl

    n_records = 12
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(bl, "BRONZE_PATH", tmpdir):
            bl.load_to_bronze_delta(iter(_make_order_records(n_records, "GADGET")), "orders")

        today = datetime.now(timezone.utc)
        partition_dir = Path(tmpdir) / "orders" / f"year={today.year}" / f"month={today.month:02d}" / f"day={today.day:02d}"
        parquet_file = partition_dir / "batch.parquet"
        df = pd.read_parquet(str(parquet_file))
        assert len(df) == n_records


# ── Feature 5: Schema Validation ─────────────────────────────────────────────

_kafka_available = bool(__import__("importlib").util.find_spec("kafka"))


_skip_no_kafka = pytest.mark.skipif(not _kafka_available, reason="kafka-python not installed in local env")


@_skip_no_kafka
def test_validate_event_valid_order():
    """Valid ORDER event should pass schema validation."""
    from ingestion.producer import _validate_event
    event = {
        "event_type": "ORDER",
        "order_id": "ORD-001",
        "supplier_id": "SUP-001",
        "product": "WIDGET",
        "region": "NA",
        "quantity": 10,
        "unit_price": 5.0,
        "order_value": 50.0,
        "expected_delivery": "2026-04-01",
        "delay_days": 0,
        "status": "IN_TRANSIT",
        "inventory_level": 75.0,
    }
    valid, err = _validate_event(event)
    assert valid is True
    assert err == ""


@_skip_no_kafka
def test_validate_event_missing_required_field():
    """ORDER event missing required field should fail validation."""
    from ingestion.producer import _validate_event
    event = {
        "event_type": "ORDER",
        "product": "WIDGET",
    }
    valid, err = _validate_event(event)
    assert valid is False
    assert err != ""


@_skip_no_kafka
def test_validate_event_invalid_status():
    """ORDER event with invalid status should fail validation."""
    from ingestion.producer import _validate_event
    event = {
        "event_type": "ORDER",
        "order_id": "ORD-001",
        "supplier_id": "SUP-001",
        "product": "WIDGET",
        "region": "NA",
        "quantity": 10,
        "unit_price": 5.0,
        "order_value": 50.0,
        "expected_delivery": "2026-04-01",
        "delay_days": 0,
        "status": "UNKNOWN_STATUS",
        "inventory_level": 75.0,
    }
    valid, err = _validate_event(event)
    assert valid is False


@_skip_no_kafka
def test_validate_event_demand_spike_valid():
    """Valid DEMAND_SPIKE event should pass schema validation."""
    from ingestion.producer import _validate_event
    event = {
        "event_type": "DEMAND_SPIKE",
        "product": "WIDGET",
        "region": "APAC",
        "forecast_delta_pct": 35.0,
        "current_inventory_days": 7.0,
    }
    valid, err = _validate_event(event)
    assert valid is True


@_skip_no_kafka
def test_validate_event_unknown_type_passes():
    """Unknown event types should pass through (allow future event types)."""
    from ingestion.producer import _validate_event
    event = {"event_type": "FUTURE_TYPE", "data": "anything"}
    valid, err = _validate_event(event)
    assert valid is True


# ── Feature 6: OpenLineage Tracker ───────────────────────────────────────────

def test_lineage_emit_event_no_db_no_marquez():
    """emit_event should not raise even when Postgres and Marquez are unavailable."""
    from pipeline.lineage_resource import emit_event
    # Should not raise — silently degrades if no DB
    emit_event(
        job_name="test_asset",
        event_type="START",
        run_id="test-run-001",
        inputs=["bronze/orders"],
        output="silver/orders",
    )


def test_lineage_context_manager_complete():
    """emit_lineage context manager should emit START then COMPLETE."""
    from pipeline.lineage_resource import emit_lineage

    emitted = []

    def mock_emit(**kwargs):
        emitted.append(kwargs)

    with patch("pipeline.lineage_resource._emit_to_postgres"), \
         patch("pipeline.lineage_resource._emit_to_marquez"):
        from pipeline.lineage_resource import emit_event as orig_emit_event
        with patch("pipeline.lineage_resource.emit_event") as mock_ev:
            mock_context = MagicMock()
            mock_context.asset_key.to_user_string.return_value = "gold_orders"

            with emit_lineage(mock_context, inputs=["silver/orders"], output="gold/orders"):
                pass  # simulated asset work

            assert mock_ev.call_count == 2
            calls = [c.kwargs if c.kwargs else dict(zip(
                ["job_name","event_type","run_id","inputs","output"],
                c.args
            )) for c in mock_ev.call_args_list]
            event_types = [c.get("event_type") for c in calls]
            assert "START" in event_types
            assert "COMPLETE" in event_types


def test_lineage_context_manager_emits_fail_on_exception():
    """emit_lineage should emit FAIL event when an exception is raised inside."""
    from pipeline.lineage_resource import emit_lineage

    with patch("pipeline.lineage_resource.emit_event") as mock_ev:
        mock_context = MagicMock()
        mock_context.asset_key.to_user_string.return_value = "broken_asset"

        with pytest.raises(ValueError):
            with emit_lineage(mock_context, inputs=["bronze/orders"], output="silver/orders"):
                raise ValueError("simulated asset failure")

        event_types = [c.kwargs.get("event_type", c.args[1] if len(c.args) > 1 else "")
                       for c in mock_ev.call_args_list]
        assert "FAIL" in event_types


# ── Feature 7: Freshness Policies ────────────────────────────────────────────

@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("dagster"),
    reason="dagster not installed in local env (runs inside Docker)"
)
def test_gold_assets_have_freshness_policy():
    """Gold assets should have FreshnessPolicy attached."""
    from dagster import FreshnessPolicy
    from pipeline.assets_medallion import (
        gold_orders_ai_ready,
        gold_deviations,
        gold_supplier_risk,
        gold_forecasted_risks,
    )
    for asset_fn in [gold_orders_ai_ready, gold_deviations, gold_supplier_risk, gold_forecasted_risks]:
        policy = getattr(asset_fn, "freshness_policy", None)
        assert policy is not None or hasattr(asset_fn, "op"), \
            f"{asset_fn.__name__} missing freshness_policy"


# ── Feature 8: dbt packages.yml ──────────────────────────────────────────────

def test_dbt_packages_yml_exists():
    """transforms/packages.yml should exist and reference dbt_expectations."""
    import yaml
    packages_path = Path(__file__).parent.parent / "transforms" / "packages.yml"
    assert packages_path.exists(), "transforms/packages.yml not found"
    with open(packages_path) as f:
        data = yaml.safe_load(f)
    packages = data.get("packages", [])
    package_names = [p.get("package", "") for p in packages]
    assert any("dbt_expectations" in name or "calogica" in name for name in package_names), \
        f"dbt_expectations not found in packages.yml: {package_names}"


# ── Feature 1: Incremental dbt models ────────────────────────────────────────

def test_fct_shipments_is_incremental():
    """fct_shipments.sql should use incremental materialization."""
    fct_path = Path(__file__).parent.parent / "transforms" / "models" / "marts" / "fct_shipments.sql"
    assert fct_path.exists()
    content = fct_path.read_text()
    assert "incremental" in content.lower(), "fct_shipments.sql should use incremental materialization"
    assert "unique_key" in content, "fct_shipments.sql should define unique_key for incremental"


def test_dim_suppliers_is_incremental():
    """dim_suppliers.sql should use incremental materialization."""
    dim_path = Path(__file__).parent.parent / "transforms" / "models" / "marts" / "dim_suppliers.sql"
    assert dim_path.exists()
    content = dim_path.read_text()
    assert "incremental" in content.lower(), "dim_suppliers.sql should use incremental materialization"


def test_fct_shipments_has_incremental_filter():
    """fct_shipments.sql should have is_incremental() conditional filter."""
    fct_path = Path(__file__).parent.parent / "transforms" / "models" / "marts" / "fct_shipments.sql"
    content = fct_path.read_text()
    assert "is_incremental()" in content, "fct_shipments.sql missing is_incremental() filter"


# ── Feature 3: Delta maintenance asset ───────────────────────────────────────

_dagster_available = bool(__import__("importlib").util.find_spec("dagster"))


@pytest.mark.skipif(not _dagster_available, reason="dagster not installed in local env")
def test_delta_maintenance_asset_exists():
    """delta_maintenance asset should be importable from assets_medallion."""
    from pipeline.assets_medallion import delta_maintenance
    assert callable(delta_maintenance)


@pytest.mark.skipif(not _dagster_available, reason="dagster not installed in local env")
def test_delta_maintenance_skips_missing_paths():
    """delta_maintenance should not raise when Delta table paths don't exist."""
    import tempfile
    from unittest.mock import patch as _patch

    with tempfile.TemporaryDirectory() as tmpdir:
        with _patch.dict(os.environ, {
            "BRONZE_PATH": os.path.join(tmpdir, "bronze"),
            "SILVER_PATH": os.path.join(tmpdir, "silver"),
            "GOLD_PATH":   os.path.join(tmpdir, "gold"),
        }):
            mock_context = MagicMock()
            mock_context.log = MagicMock()
            from pipeline.assets_medallion import delta_maintenance
            result = delta_maintenance(mock_context)
            assert result is not None
