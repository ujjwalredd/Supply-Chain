"""
Prophet-based demand forecasting for supply chain orders.
Forecasts order_value trend 30 days forward.
"""
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def forecast_demand(df: pd.DataFrame, periods: int = 30) -> pd.DataFrame:
    """
    Given a DataFrame with 'created_at' and 'order_value' columns,
    train a Prophet model and forecast `periods` days forward.

    Returns a DataFrame with columns: ds, yhat, yhat_lower, yhat_upper, trend
    Falls back to linear trend if Prophet not available.
    """
    try:
        from prophet import Prophet

        # Prepare data for Prophet — prefer expected_delivery for date spread,
        # fall back to created_at if delivery dates are too few
        prophet_df = df.copy()
        date_col = "expected_delivery" if "expected_delivery" in prophet_df.columns else "created_at"
        prophet_df["ds"] = pd.to_datetime(prophet_df[date_col], format="mixed", errors="coerce").dt.tz_localize(None)
        prophet_df = prophet_df.dropna(subset=["ds"])
        # Aggregate to daily
        prophet_df = prophet_df.groupby(prophet_df["ds"].dt.date)["order_value"].sum().reset_index()
        prophet_df.columns = ["ds", "y"]
        prophet_df["ds"] = pd.to_datetime(prophet_df["ds"])

        if len(prophet_df) < 10:
            logger.info("Too few unique dates (%d) for Prophet — using linear fallback", len(prophet_df))
            return _linear_forecast(df, periods)

        model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False,
            seasonality_mode="additive",
            changepoint_prior_scale=0.05,
        )
        model.fit(prophet_df)
        future = model.make_future_dataframe(periods=periods, freq="D")
        forecast = model.predict(future)
        return forecast[["ds", "yhat", "yhat_lower", "yhat_upper", "trend"]].tail(periods)

    except ImportError:
        logger.warning("prophet not installed — using linear trend fallback")
        return _linear_forecast(df, periods)


def _linear_forecast(df: pd.DataFrame, periods: int) -> pd.DataFrame:
    """Simple linear trend fallback when Prophet is not available."""
    import numpy as np
    from datetime import timedelta

    base = df["order_value"].mean() if "order_value" in df.columns else 1000.0
    trend_per_day = base * 0.001
    today = datetime.now(timezone.utc).replace(tzinfo=None)

    rows = []
    for i in range(1, periods + 1):
        ds = today + timedelta(days=i)
        yhat = base + trend_per_day * i
        rows.append({
            "ds": ds,
            "yhat": round(yhat, 2),
            "yhat_lower": round(yhat * 0.85, 2),
            "yhat_upper": round(yhat * 1.15, 2),
            "trend": round(trend_per_day * i, 2),
        })
    return pd.DataFrame(rows)
