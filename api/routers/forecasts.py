"""Feature 5: Forecasted risk router — serve at-risk orders from gold layer."""

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter()

GOLD_PATH = os.getenv("GOLD_PATH", "/opt/dagster/storage/gold")


def _read_forecasted_risks() -> list[dict[str, Any]]:
    """Read forecasted_risks parquet from gold layer."""
    parquet_file = Path(GOLD_PATH) / "forecasted_risks" / "data.parquet"
    if not parquet_file.exists():
        return []
    try:
        import pandas as pd
        df = pd.read_parquet(parquet_file)
        # Keep only essential columns for the API
        keep = [c for c in [
            "order_id", "supplier_id", "days_to_delivery", "risk_reason",
            "alt_carrier", "alt_min_cost", "alt_transit_days",
            "product", "quantity", "order_value", "expected_delivery",
        ] if c in df.columns]
        df = df[keep].copy()
        df = df.fillna("")
        # Convert datetime columns to ISO strings for JSON serialisation
        for col in df.select_dtypes(include=["datetime64[ns, UTC]", "datetime64[ns]"]).columns:
            df[col] = df[col].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return df.to_dict(orient="records")
    except Exception as exc:
        logger.warning("Could not read forecasted_risks parquet: %s", exc)
        return []


@router.get("")
async def list_forecasted_risks(
    limit: int = Query(50, ge=1, le=500),
    min_days: float = Query(0.0, description="Filter to orders with days_to_delivery >= N"),
    max_days: float = Query(7.0, description="Filter to orders with days_to_delivery <= N"),
):
    """
    Return orders predicted to be at risk of delay.

    Sourced from the gold/forecasted_risks Parquet produced by the Dagster pipeline.
    """
    rows = _read_forecasted_risks()
    # Filter by days window
    rows = [
        r for r in rows
        if min_days <= float(r.get("days_to_delivery", 0)) <= max_days
    ]
    return rows[:limit]


@router.get("/summary")
async def forecast_summary():
    """Return aggregate summary of at-risk orders."""
    rows = _read_forecasted_risks()
    if not rows:
        return {"at_risk_count": 0, "suppliers_affected": 0, "avg_days_to_delivery": None}
    suppliers = {r.get("supplier_id") for r in rows}
    avg_days = sum(float(r.get("days_to_delivery", 0)) for r in rows) / len(rows)
    return {
        "at_risk_count": len(rows),
        "suppliers_affected": len(suppliers),
        "avg_days_to_delivery": round(avg_days, 1),
    }
