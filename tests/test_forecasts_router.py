"""Unit tests for the forecasts router — no database or real parquet required."""

import os
from unittest.mock import patch

import pandas as pd
import pytest

# Import the private helper directly (no DB/FastAPI startup needed)
from api.routers.forecasts import _read_forecasted_risks


def test_read_forecasted_risks_returns_empty_when_no_file():
    """Should return [] when the parquet file is missing."""
    with patch.dict(os.environ, {"GOLD_PATH": "/nonexistent/path/that/does/not/exist"}):
        # Re-import to pick up new env var (module-level var already set, patch directly)
        import api.routers.forecasts as fr_module
        original = fr_module.GOLD_PATH
        fr_module.GOLD_PATH = "/nonexistent/path/that/does/not/exist"
        try:
            result = _read_forecasted_risks()
            assert result == []
        finally:
            fr_module.GOLD_PATH = original


def test_read_forecasted_risks_reads_parquet(tmp_path):
    """Should parse a valid parquet and return records."""
    # Build minimal parquet matching the expected schema
    df = pd.DataFrame([{
        "order_id": "ORD001",
        "supplier_id": "PLANT01",
        "days_to_delivery": -100.0,
        "risk_score": 1500.0,
        "delay_probability": 0.25,
        "confidence": 0.85,
        "risk_reason": "Test reason",
        "alt_carrier": "CARRIER_A",
        "alt_min_cost": 250.0,
        "alt_transit_days": 3.0,
        "product": "PROD123",
        "quantity": 100,
        "order_value": 6000.0,
        "expected_delivery": "2016-01-01T00:00:00Z",
    }])
    parquet_dir = tmp_path / "forecasted_risks"
    parquet_dir.mkdir()
    df.to_parquet(parquet_dir / "data.parquet", index=False)

    import api.routers.forecasts as fr_module
    original = fr_module.GOLD_PATH
    fr_module.GOLD_PATH = str(tmp_path)
    try:
        result = _read_forecasted_risks()
        assert len(result) == 1
        assert result[0]["order_id"] == "ORD001"
        assert result[0]["supplier_id"] == "PLANT01"
        assert result[0]["risk_score"] == pytest.approx(1500.0, rel=1e-3)
        assert result[0]["delay_probability"] == pytest.approx(0.25, rel=1e-3)
    finally:
        fr_module.GOLD_PATH = original


def test_read_forecasted_risks_handles_missing_columns(tmp_path):
    """Should tolerate parquet with only a subset of expected columns."""
    df = pd.DataFrame([{
        "order_id": "ORD002",
        "supplier_id": "PLANT02",
        "risk_score": 500.0,
    }])
    parquet_dir = tmp_path / "forecasted_risks"
    parquet_dir.mkdir()
    df.to_parquet(parquet_dir / "data.parquet", index=False)

    import api.routers.forecasts as fr_module
    original = fr_module.GOLD_PATH
    fr_module.GOLD_PATH = str(tmp_path)
    try:
        result = _read_forecasted_risks()
        assert len(result) == 1
        assert result[0]["order_id"] == "ORD002"
    finally:
        fr_module.GOLD_PATH = original


def test_read_forecasted_risks_multiple_rows(tmp_path):
    """Multiple rows should all be returned."""
    rows = [
        {"order_id": f"ORD{i:03d}", "supplier_id": "PLANT03",
         "risk_score": float(1000 - i * 100), "delay_probability": 0.3}
        for i in range(5)
    ]
    df = pd.DataFrame(rows)
    parquet_dir = tmp_path / "forecasted_risks"
    parquet_dir.mkdir()
    df.to_parquet(parquet_dir / "data.parquet", index=False)

    import api.routers.forecasts as fr_module
    original = fr_module.GOLD_PATH
    fr_module.GOLD_PATH = str(tmp_path)
    try:
        result = _read_forecasted_risks()
        assert len(result) == 5
    finally:
        fr_module.GOLD_PATH = original
