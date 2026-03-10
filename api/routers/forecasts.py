"""Feature 5: Forecasted risk router — serve at-risk orders from gold layer."""

import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter()

GOLD_PATH = os.getenv("GOLD_PATH", "data/gold")

# Module-level cache: avoid re-reading parquet on every request (TTL = 5 min)
_FORECAST_CACHE: list[dict[str, Any]] = []
_FORECAST_CACHE_AT: float = 0.0
_FORECAST_CACHE_TTL: float = 300.0


def _read_forecasted_risks() -> list[dict[str, Any]]:
    """Read forecasted_risks parquet from gold layer, cached for 5 minutes."""
    global _FORECAST_CACHE, _FORECAST_CACHE_AT
    if _FORECAST_CACHE and (time.monotonic() - _FORECAST_CACHE_AT) < _FORECAST_CACHE_TTL:
        return _FORECAST_CACHE

    parquet_file = Path(GOLD_PATH) / "forecasted_risks" / "data.parquet"
    if not parquet_file.exists():
        logger.warning("forecasted_risks parquet not found at %s", parquet_file)
        return []
    try:
        import pandas as pd
        df = pd.read_parquet(parquet_file)
        keep = [c for c in [
            "order_id", "supplier_id", "days_to_delivery", "risk_score",
            "delay_probability", "confidence", "risk_reason",
            "alt_carrier", "alt_min_cost", "alt_transit_days",
            "product", "quantity", "order_value", "expected_delivery",
        ] if c in df.columns]
        df = df[keep].copy()
        df = df.fillna("")
        import pandas as pd
        dt_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
        for col in dt_cols:
            df[col] = df[col].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        _FORECAST_CACHE = df.to_dict(orient="records")
        _FORECAST_CACHE_AT = time.monotonic()
        return _FORECAST_CACHE
    except Exception as exc:
        logger.warning("Could not read forecasted_risks parquet: %s", exc)
        return []


@router.get("")
async def list_forecasted_risks(
    limit: int = Query(50, ge=1, le=500),
    min_risk_score: float = Query(0.0, ge=0.0, description="Filter to orders with risk_score >= N"),
):
    """
    Return orders predicted to be at risk of delay, ranked by risk_score.

    Sourced from gold/forecasted_risks Parquet (Dagster pipeline).
    risk_score = order_value × delay_probability (time-decay weighted).
    """
    rows = _read_forecasted_risks()
    if min_risk_score > 0:
        rows = [r for r in rows if float(r.get("risk_score", 0)) >= min_risk_score]
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


@router.get("/demand")
async def get_demand_forecast():
    """
    Feature 6 (Prophet): 30-day demand forecast for order_value.

    Reads GOLD_PATH/demand_forecast/forecast.parquet if available (produced by
    the gold_demand_forecast Dagster asset).  If the file does not yet exist,
    generates an on-the-fly forecast from synthetic data so the endpoint always
    returns a usable response.

    Returns: {forecast: [{ds, yhat, yhat_lower, yhat_upper}], periods: int, generated_at: str}
    """
    from datetime import datetime, timezone as tz

    parquet_file = Path(GOLD_PATH) / "demand_forecast" / "forecast.parquet"
    generated_at = datetime.now(tz.utc).isoformat()

    if parquet_file.exists():
        try:
            import pandas as pd
            df = pd.read_parquet(parquet_file)
            records = []
            for _, row in df.iterrows():
                records.append({
                    "ds": str(row["ds"]) if "ds" in df.columns else "",
                    "yhat": float(row["yhat"]) if "yhat" in df.columns else 0.0,
                    "yhat_lower": float(row["yhat_lower"]) if "yhat_lower" in df.columns else 0.0,
                    "yhat_upper": float(row["yhat_upper"]) if "yhat_upper" in df.columns else 0.0,
                })
            return {
                "forecast": records,
                "periods": len(records),
                "generated_at": generated_at,
                "source": "parquet",
            }
        except Exception as exc:
            logger.warning("Could not read demand_forecast parquet: %s", exc)

    # On-the-fly fallback using synthetic data
    try:
        import numpy as np
        import pandas as pd
        from datetime import timedelta, timezone
        from pipeline.demand_forecast import forecast_demand

        dates = [datetime.now(timezone.utc) - timedelta(days=i) for i in range(60, 0, -1)]
        synthetic_df = pd.DataFrame({
            "created_at": [d.isoformat() for d in dates],
            "order_value": np.random.uniform(500, 5000, 60).tolist(),
        })
        forecast_df = forecast_demand(synthetic_df, periods=30)
        records = []
        for _, row in forecast_df.iterrows():
            records.append({
                "ds": str(row["ds"]),
                "yhat": float(row["yhat"]),
                "yhat_lower": float(row["yhat_lower"]),
                "yhat_upper": float(row["yhat_upper"]),
            })
        return {
            "forecast": records,
            "periods": len(records),
            "generated_at": generated_at,
            "source": "synthetic_fallback",
        }
    except Exception as exc:
        logger.error("Demand forecast generation failed: %s", exc)
        return {"forecast": [], "periods": 0, "generated_at": generated_at, "error": str(exc)}
