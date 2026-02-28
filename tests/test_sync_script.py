"""Unit tests for sync_gold_to_postgres helper functions — no DB required."""

import importlib.util
import os

import pandas as pd
import pytest

# Load the script directly since scripts/ has no __init__.py
_script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "sync_gold_to_postgres.py")
_spec = importlib.util.spec_from_file_location("sync_gold_to_postgres", _script_path)
_sync_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sync_mod)
_build_orders_df = _sync_mod._build_orders_df


def _base_df(**overrides) -> pd.DataFrame:
    """Build a minimal raw orders DataFrame."""
    data = {
        "order_id": ["ORD001", "ORD002"],
        "supplier_id": ["PLANT01", "PLANT02"],
        "product": ["PROD_A", "PROD_B"],
        "region": ["US", "EU"],
        "quantity": [100, 200],
        "order_value": [5000.0, 12000.0],
        "delay_days": [2, 0],
        "status": ["IN_TRANSIT", "DELIVERED"],
        "inventory_level": [0.75, 0.5],
        "expected_delivery": ["2016-06-01", "2016-07-15"],
    }
    data.update(overrides)
    return pd.DataFrame(data)


def test_build_orders_df_preserves_order_ids():
    df = _base_df()
    result = _build_orders_df(df)
    assert set(result["order_id"].tolist()) == {"ORD001", "ORD002"}


def test_build_orders_df_computes_unit_price():
    df = _base_df()
    result = _build_orders_df(df)
    row = result[result["order_id"] == "ORD001"].iloc[0]
    # unit_price = order_value / quantity = 5000 / 100 = 50
    assert row["unit_price"] == pytest.approx(50.0, rel=1e-3)


def test_build_orders_df_drops_null_order_id():
    df = _base_df()
    df.loc[0, "order_id"] = None
    result = _build_orders_df(df)
    assert len(result) == 1
    assert result["order_id"].iloc[0] == "ORD002"


def test_build_orders_df_fills_missing_delay_days():
    df = _base_df()
    df.loc[0, "delay_days"] = None
    result = _build_orders_df(df)
    row = result[result["order_id"] == "ORD001"].iloc[0]
    assert row["delay_days"] == 0


def test_build_orders_df_fills_missing_status():
    df = _base_df()
    df = df.drop(columns=["status"])
    result = _build_orders_df(df)
    assert (result["status"] == "UNKNOWN").all()


def test_build_orders_df_expected_delivery_is_tz_aware():
    df = _base_df()
    result = _build_orders_df(df)
    assert result["expected_delivery"].dt.tz is not None


def test_build_orders_df_created_at_is_tz_aware():
    df = _base_df()
    result = _build_orders_df(df)
    assert result["created_at"].dt.tz is not None


def test_build_orders_df_quantity_zero_avoids_div_by_zero():
    """order_value / quantity should not crash when quantity=0."""
    df = _base_df()
    df.loc[0, "quantity"] = 0
    result = _build_orders_df(df)
    # Should not raise; unit_price for that row will be order_value/1 (qty replaced with 1)
    assert result[result["order_id"] == "ORD001"]["unit_price"].iloc[0] == pytest.approx(5000.0, rel=1e-3)
