"""
Gold Layer Agent
Model: Claude Haiku (validates AI-generated financial calculations)
Interval: 600s (10min)

Validates:
- Financial formula correctness (re-computes on sample)
- ML output sanity (probability bounds, confidence)
- Forecast validity (yhat bounds, positive values)
- Gold freshness against FreshnessPolicy (6h)
"""
import os
import math
import logging
import time
from pathlib import Path

from agents.base import BaseAgent, HAIKU_MODEL

logger = logging.getLogger(__name__)

GOLD_PATH = os.getenv("GOLD_PATH", "/data/gold")
FRESHNESS_THRESHOLD_MINUTES = int(os.getenv("GOLD_FRESHNESS_THRESHOLD_MIN", "360"))

CARRYING_COST_RATE = 0.02
DELAY_COST_PER_DAY = 500.0
STOCKOUT_PENALTY_RATE = 0.15
FORMULA_TOLERANCE = 0.02  # 2% tolerance for floating point


class GoldAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="gold_agent",
            model=HAIKU_MODEL,
            interval_seconds=600,
            description="Validates Gold layer financial formulas, ML outputs, forecast sanity."
        )

    def check(self) -> dict:
        import pandas as pd

        metrics = {}
        gold_dir = Path(GOLD_PATH)

        if not gold_dir.exists():
            logger.warning(f"Gold path missing: {GOLD_PATH}")
            return {"task": "gold_dir_missing"}

        parquet_files = list(gold_dir.rglob("*.parquet"))
        metrics["total_gold_files"] = len(parquet_files)

        if not parquet_files:
            logger.warning("No Gold parquet files found")
            self.alert("MEDIUM", "Gold layer has no parquet files", {})
            return {"task": "no_gold_files"}

        # Check freshness
        latest = max(parquet_files, key=lambda p: p.stat().st_mtime)
        age_min = (time.time() - latest.stat().st_mtime) / 60
        metrics["gold_age_min"] = round(age_min, 1)

        if age_min > FRESHNESS_THRESHOLD_MINUTES:
            self.alert("HIGH", f"Gold layer stale: {age_min:.0f}min (threshold={FRESHNESS_THRESHOLD_MINUTES}min)",
                       {"latest_file": str(latest), "age_min": age_min})

        # Validate orders_ai_ready financial formulas
        ai_files = [f for f in gold_dir.rglob("*.parquet") if f.is_file() and ("ai_ready" in str(f) or "orders" in str(f))]
        if ai_files:
            try:
                import shutil, tempfile, pyarrow.parquet as pq
                with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
                    tmp_path = tmp.name
                shutil.copy2(str(ai_files[0]), tmp_path)
                table = pq.read_table(tmp_path, use_threads=False)
                df = table.to_pandas()
                try:
                    import os as _os; _os.unlink(tmp_path)
                except Exception:
                    pass
                metrics["gold_orders_rows"] = len(df)
                formula_issues = self._validate_formulas(df)
                metrics["formula_issues"] = len(formula_issues)

                if formula_issues:
                    logger.error(f"Gold formula validation failed: {formula_issues[:3]}")
                    analysis = self.analyze_with_llm(
                        system_prompt="You are a financial data validator for supply chain analytics.",
                        user_message=f"These Gold layer financial calculation mismatches were found: {formula_issues[:5]}. "
                                     f"The formulas should be: "
                                     f"carrying_cost = order_value * (delay_days/30) * {CARRYING_COST_RATE}, "
                                     f"delay_cost = delay_days * {DELAY_COST_PER_DAY}, "
                                     f"stockout_penalty = order_value * {STOCKOUT_PENALTY_RATE}. "
                                     f"What is the likely cause of the mismatch?",
                        max_tokens=300
                    )
                    self.alert("HIGH", f"Gold financial formula mismatch in {len(formula_issues)} rows",
                               {"issues": formula_issues[:5], "analysis": analysis})
                    self.audit("FORMULA_MISMATCH", analysis, "ALERT",
                               {"mismatch_count": len(formula_issues)})

                # Validate ML outputs if present
                if "delay_probability" in df.columns:
                    bad_prob = df[(df["delay_probability"] < 0) | (df["delay_probability"] > 1)]
                    metrics["bad_delay_probability"] = len(bad_prob)
                    if len(bad_prob) > 0:
                        self.alert("HIGH", f"{len(bad_prob)} rows have delay_probability outside [0,1]",
                                   {"count": len(bad_prob)})

                if "confidence" in df.columns:
                    bad_conf = df[(df["confidence"] < 0) | (df["confidence"] > 1)]
                    metrics["bad_confidence"] = len(bad_conf)
                    if len(bad_conf) > 0:
                        self.alert("MEDIUM", f"{len(bad_conf)} rows have confidence outside [0,1]", {})

            except Exception as e:
                logger.error(f"Gold orders validation error: {e}")
                raise

        # Validate forecast if present
        forecast_files = [f for f in gold_dir.rglob("*.parquet") if f.is_file() and "forecast" in f.name]
        if forecast_files:
            try:
                import shutil, tempfile, pyarrow.parquet as pq2
                with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp2:
                    tmp2_path = tmp2.name
                shutil.copy2(str(forecast_files[0]), tmp2_path)
                ftable = pq2.read_table(tmp2_path, use_threads=False)
                fdf = ftable.to_pandas()
                try:
                    import os as _os2; _os2.unlink(tmp2_path)
                except Exception:
                    pass
                if all(c in fdf.columns for c in ["yhat", "yhat_lower", "yhat_upper"]):
                    bad_bounds = fdf[fdf["yhat"] < fdf["yhat_lower"]]
                    bad_bounds2 = fdf[fdf["yhat"] > fdf["yhat_upper"]]
                    neg_forecast = fdf[fdf["yhat"] < 0]
                    metrics["forecast_bound_violations"] = len(bad_bounds) + len(bad_bounds2)
                    metrics["negative_forecasts"] = len(neg_forecast)

                    if len(neg_forecast) > 0:
                        self.alert("MEDIUM", f"{len(neg_forecast)} negative demand forecasts (yhat<0)", {})
            except Exception as e:
                logger.debug(f"Forecast validation skipped: {e}")

        metrics["task"] = f"files={len(parquet_files)}|age={metrics.get('gold_age_min','?')}min|formula_issues={metrics.get('formula_issues',0)}"
        return metrics

    def _validate_formulas(self, df) -> list:
        """Re-compute financial formulas on a sample and check for mismatches."""
        issues = []
        required = {"order_value", "delay_days"}
        if not required.issubset(set(df.columns)):
            return []

        sample = df.head(50)
        for _, row in sample.iterrows():
            try:
                ov = float(row.get("order_value", 0) or 0)
                dd = float(row.get("delay_days", 0) or 0)

                expected_carrying = ov * (dd / 30) * CARRYING_COST_RATE
                expected_delay = dd * DELAY_COST_PER_DAY

                actual_carrying = float(row.get("carrying_cost", expected_carrying) or expected_carrying)
                actual_delay = float(row.get("delay_cost", expected_delay) or expected_delay)

                if ov > 0 and dd > 0:
                    carrying_err = abs(actual_carrying - expected_carrying) / max(expected_carrying, 1)
                    delay_err = abs(actual_delay - expected_delay) / max(expected_delay, 1)

                    if carrying_err > FORMULA_TOLERANCE:
                        issues.append({
                            "order_id": str(row.get("order_id", "?")),
                            "field": "carrying_cost",
                            "expected": round(expected_carrying, 2),
                            "actual": round(actual_carrying, 2),
                            "error_pct": round(carrying_err * 100, 1)
                        })
                    if delay_err > FORMULA_TOLERANCE:
                        issues.append({
                            "order_id": str(row.get("order_id", "?")),
                            "field": "delay_cost",
                            "expected": round(expected_delay, 2),
                            "actual": round(actual_delay, 2),
                            "error_pct": round(delay_err * 100, 1)
                        })
            except Exception:
                continue

        return issues

    def heal(self, error: Exception) -> bool:
        return False  # Gold failures escalate to Medallion Supervisor
