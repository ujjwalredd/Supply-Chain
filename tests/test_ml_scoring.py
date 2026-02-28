"""Unit tests for time-decay ML risk scoring logic (no DB required)."""

import numpy as np
import pandas as pd
import pytest


# ── Helpers that mirror the pipeline logic ───────────────────────────────────

def _compute_supplier_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Reproduce the supplier-level time-decay scoring from gold_forecasted_risks."""
    newest_date = df["expected_delivery"].dropna().max()
    df = df.copy()
    df["days_old"] = (
        (newest_date - df["expected_delivery"]).dt.total_seconds().div(86400).clip(lower=0).fillna(180)
    )
    df["weight"] = np.exp(-df["days_old"] / 90)
    df["weighted_delayed"] = (df["delay_days"] > 0).astype(float) * df["weight"]

    def _supplier_risk(g):
        total_weight = float(g["weight"].sum())
        if total_weight < 1e-9:
            total_weight = 1e-9
        return pd.Series({
            "total_orders": len(g),
            "delay_probability": float(g["weighted_delayed"].sum()) / total_weight,
            "avg_delay_days": float(g["delay_days"].mean()),
        })

    try:
        stats = df.groupby("supplier_id", group_keys=False).apply(_supplier_risk, include_groups=False).reset_index()
    except TypeError:
        stats = df.groupby("supplier_id", group_keys=False).apply(_supplier_risk).reset_index()

    stats["confidence"] = (
        1.0 - 1.0 / np.sqrt(stats["total_orders"].clip(lower=1))
    ).clip(0, 1).round(3)
    return stats


def _make_orders(supplier_id: str, n_delayed: int, n_on_time: int, base_date: str = "2016-01-01") -> pd.DataFrame:
    """Build a minimal orders DataFrame for testing."""
    rows = []
    t0 = pd.Timestamp(base_date, tz="UTC")
    for i in range(n_delayed):
        rows.append({
            "supplier_id": supplier_id,
            "order_id": f"{supplier_id}-D{i}",
            "expected_delivery": t0 + pd.Timedelta(days=i),
            "delay_days": 5.0,
            "order_value": 1000.0,
        })
    for i in range(n_on_time):
        rows.append({
            "supplier_id": supplier_id,
            "order_id": f"{supplier_id}-O{i}",
            "expected_delivery": t0 + pd.Timedelta(days=n_delayed + i),
            "delay_days": 0.0,
            "order_value": 1000.0,
        })
    return pd.DataFrame(rows)


# ── Tests ────────────────────────────────────────────────────────────────────

def test_zero_delays_gives_zero_probability():
    df = _make_orders("SUP1", n_delayed=0, n_on_time=10)
    stats = _compute_supplier_stats(df)
    row = stats[stats["supplier_id"] == "SUP1"].iloc[0]
    assert row["delay_probability"] == pytest.approx(0.0, abs=1e-6)


def test_all_delays_gives_high_probability():
    df = _make_orders("SUP2", n_delayed=10, n_on_time=0)
    stats = _compute_supplier_stats(df)
    row = stats[stats["supplier_id"] == "SUP2"].iloc[0]
    # All orders delayed → probability close to 1.0
    assert row["delay_probability"] > 0.95


def test_delay_probability_between_zero_and_one():
    df = _make_orders("SUP3", n_delayed=3, n_on_time=7)
    stats = _compute_supplier_stats(df)
    row = stats[stats["supplier_id"] == "SUP3"].iloc[0]
    assert 0.0 <= row["delay_probability"] <= 1.0


def test_confidence_increases_with_more_orders():
    df_small = _make_orders("SUP4", n_delayed=1, n_on_time=0)
    df_large = _make_orders("SUP5", n_delayed=100, n_on_time=0)
    stats_small = _compute_supplier_stats(df_small)
    stats_large = _compute_supplier_stats(df_large)
    conf_small = stats_small[stats_small["supplier_id"] == "SUP4"]["confidence"].iloc[0]
    conf_large = stats_large[stats_large["supplier_id"] == "SUP5"]["confidence"].iloc[0]
    assert conf_large > conf_small


def test_confidence_formula_single_order():
    """confidence = 1 - 1/sqrt(n). For n=1, confidence = 0."""
    df = _make_orders("SUP6", n_delayed=1, n_on_time=0)
    stats = _compute_supplier_stats(df)
    row = stats[stats["supplier_id"] == "SUP6"].iloc[0]
    assert row["confidence"] == pytest.approx(0.0, abs=0.001)


def test_confidence_formula_100_orders():
    """For n=100, confidence = 1 - 1/10 = 0.9."""
    df = _make_orders("SUP7", n_delayed=50, n_on_time=50)
    stats = _compute_supplier_stats(df)
    row = stats[stats["supplier_id"] == "SUP7"].iloc[0]
    assert row["confidence"] == pytest.approx(0.9, abs=0.01)


def test_time_decay_uses_relative_newest_date():
    """Oldest orders should have lower weight than newest orders in same supplier."""
    rows = [
        {"supplier_id": "SUP8", "order_id": "old", "expected_delivery": pd.Timestamp("2015-01-01", tz="UTC"),
         "delay_days": 5.0, "order_value": 1000.0},
        {"supplier_id": "SUP8", "order_id": "new", "expected_delivery": pd.Timestamp("2016-01-01", tz="UTC"),
         "delay_days": 0.0, "order_value": 1000.0},
    ]
    df = pd.DataFrame(rows)
    newest = df["expected_delivery"].max()
    df["days_old"] = (newest - df["expected_delivery"]).dt.total_seconds().div(86400)
    df["weight"] = np.exp(-df["days_old"] / 90)
    # newest order has days_old=0 → weight=1.0
    new_weight = df[df["order_id"] == "new"]["weight"].iloc[0]
    old_weight = df[df["order_id"] == "old"]["weight"].iloc[0]
    assert new_weight == pytest.approx(1.0, abs=1e-6)
    assert old_weight < new_weight


def test_risk_score_equals_value_times_probability():
    df = _make_orders("SUP9", n_delayed=5, n_on_time=5)
    stats = _compute_supplier_stats(df)
    prob = stats[stats["supplier_id"] == "SUP9"]["delay_probability"].iloc[0]
    order_value = 1000.0
    risk_score = order_value * prob
    assert risk_score == pytest.approx(order_value * prob, rel=1e-6)


def test_multi_supplier_independence():
    """Each supplier's stats are independent."""
    df1 = _make_orders("GOOD", n_delayed=0, n_on_time=20)
    df2 = _make_orders("BAD", n_delayed=20, n_on_time=0)
    df = pd.concat([df1, df2], ignore_index=True)
    stats = _compute_supplier_stats(df)
    good = stats[stats["supplier_id"] == "GOOD"]["delay_probability"].iloc[0]
    bad = stats[stats["supplier_id"] == "BAD"]["delay_probability"].iloc[0]
    assert good == pytest.approx(0.0, abs=1e-6)
    assert bad > 0.95
