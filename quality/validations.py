"""
Data quality validations and safe backfill strategies.

- Great Expectations-style checks
- Row-level validation
- Schema validation
- Safe backfill: dry-run, incremental, full
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    rule: str
    passed: bool
    failed_count: int = 0
    total_count: int = 0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


def validate_not_null(df, column: str) -> ValidationResult:
    """Expect column values to not be null."""
    try:
        total = len(df)
        nulls = df[column].isna().sum()
        passed = nulls == 0
        return ValidationResult(
            rule=f"expect_{column}_not_null",
            passed=passed,
            failed_count=int(nulls),
            total_count=total,
            message=f"{nulls} nulls in {column}" if not passed else "OK",
        )
    except Exception as e:
        return ValidationResult(
            rule=f"expect_{column}_not_null",
            passed=False,
            message=str(e),
        )


def validate_in_set(df, column: str, value_set: set) -> ValidationResult:
    """Expect column values to be in allowed set."""
    try:
        total = len(df)
        invalid = ~df[column].isin(value_set)
        failed = invalid.sum()
        passed = failed == 0
        return ValidationResult(
            rule=f"expect_{column}_in_set",
            passed=passed,
            failed_count=int(failed),
            total_count=total,
            message=f"{failed} invalid values" if not passed else "OK",
            details={"allowed": list(value_set), "invalid_sample": df.loc[invalid, column].head(5).tolist()},
        )
    except Exception as e:
        return ValidationResult(rule=f"expect_{column}_in_set", passed=False, message=str(e))


def validate_between(df, column: str, min_val: float, max_val: float) -> ValidationResult:
    """Expect column values to be between min and max."""
    try:
        total = len(df)
        invalid = (df[column] < min_val) | (df[column] > max_val)
        failed = invalid.sum()
        passed = failed == 0
        return ValidationResult(
            rule=f"expect_{column}_between",
            passed=passed,
            failed_count=int(failed),
            total_count=total,
            message=f"{failed} out of range [{min_val}, {max_val}]" if not passed else "OK",
        )
    except Exception as e:
        return ValidationResult(rule=f"expect_{column}_between", passed=False, message=str(e))


def run_validation_suite(df, suite: str = "orders") -> list[ValidationResult]:
    """Run validation suite (orders or deviations)."""
    results: list[ValidationResult] = []
    if suite == "orders":
        if "order_id" in df.columns:
            results.append(validate_not_null(df, "order_id"))
        if "delay_days" in df.columns:
            results.append(validate_between(df, "delay_days", 0, 365))
        if "status" in df.columns:
            results.append(
                validate_in_set(
                    df,
                    "status",
                    {"PENDING", "IN_TRANSIT", "DELIVERED", "DELAYED", "CANCELLED", "CRF", "DTD"},
                )
            )
    return results


def safe_backfill(
    source_path: str,
    target_path: str,
    mode: str = "full",  # full | incremental | dry_run
    since: datetime | None = None,
) -> dict[str, Any]:
    """
    Safe backfill strategy.
    - dry_run: validate only, no write
    - incremental: append rows where created_at > since
    - full: overwrite target
    """
    import pandas as pd

    result = {"mode": mode, "rows_read": 0, "rows_written": 0, "validations": [], "error": None}
    try:
        df = pd.read_csv(source_path) if source_path.endswith(".csv") else pd.read_parquet(source_path)
        result["rows_read"] = len(df)

        if mode == "dry_run":
            val_results = run_validation_suite(df)
            result["validations"] = [
                {"rule": v.rule, "passed": v.passed, "message": v.message} for v in val_results
            ]
            result["rows_written"] = 0
            return result

        if mode == "incremental" and since and "created_at" in df.columns:
            df["_ts"] = pd.to_datetime(df["created_at"], errors="coerce")
            df = df[df["_ts"] >= since].drop(columns=["_ts"])

        val_results = run_validation_suite(df)
        failed = [v for v in val_results if not v.passed]
        if failed:
            result["error"] = f"Validation failed: {[v.rule for v in failed]}"
            result["validations"] = [{"rule": v.rule, "passed": v.passed} for v in val_results]
            return result

        target = Path(target_path)
        if mode == "full":
            target.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(target_path, index=False)
        else:
            existing = pd.read_parquet(target_path) if target.exists() else pd.DataFrame()
            combined = pd.concat([existing, df]).drop_duplicates(subset=["order_id"], keep="last")
            combined.to_parquet(target_path, index=False)

        result["rows_written"] = len(df)
        result["validations"] = [{"rule": v.rule, "passed": v.passed} for v in val_results]
    except Exception as e:
        result["error"] = str(e)
        logger.exception("Backfill failed: %s", e)

    return result
