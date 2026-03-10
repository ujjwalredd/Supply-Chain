"""
ksqlDB HTTP API client — execute streaming queries and fetch aggregation results.

Usage:
    from streaming.ksql_queries import get_supplier_delay_rates, get_region_demand
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

KSQLDB_URL = os.getenv("KSQLDB_URL", "http://ksqldb-server:8088")
_TIMEOUT = 5


def _ksql(statement: str) -> list[dict]:
    """Execute a ksqlDB statement. Returns rows or []."""
    try:
        resp = requests.post(
            f"{KSQLDB_URL}/ksql",
            json={"ksql": statement, "streamsProperties": {}},
            timeout=_TIMEOUT,
            headers={"Accept": "application/vnd.ksql.v1+json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            rows = data[0].get("rows", [])
            columns = data[0].get("columnNames", [])
            return [dict(zip(columns, row)) for row in rows]
        return []
    except Exception as exc:
        logger.warning("ksqlDB query failed: %s", exc)
        return []


def get_supplier_delay_rates(limit: int = 20) -> list[dict]:
    """Fetch latest 5-minute delay rates per supplier from ksqlDB materialised table."""
    return _ksql(
        f"SELECT supplier_id, total_orders, delayed_orders, delay_rate, "
        f"avg_delay_days, avg_inventory_level, window_start, window_end "
        f"FROM supplier_delay_rate_5m LIMIT {limit};"
    )


def get_region_demand(limit: int = 10) -> list[dict]:
    """Fetch latest 5-minute demand aggregations per region."""
    return _ksql(
        f"SELECT region, order_count, total_order_value, avg_order_value, "
        f"total_quantity, window_start, window_end "
        f"FROM region_demand_5m LIMIT {limit};"
    )


def init_ksql_streams() -> bool:
    """
    Execute ksql_init.sql against the ksqlDB server.
    Safe to call multiple times (CREATE IF NOT EXISTS).
    Returns True on success, False if ksqlDB unavailable.
    """
    sql_path = os.path.join(os.path.dirname(__file__), "ksql_init.sql")
    try:
        with open(sql_path) as f:
            content = f.read()

        # Split on semicolons, skip empty/comment-only blocks
        statements = [s.strip() for s in content.split(";") if s.strip() and not s.strip().startswith("--")]

        ok = 0
        for stmt in statements:
            if not stmt:
                continue
            try:
                resp = requests.post(
                    f"{KSQLDB_URL}/ksql",
                    json={"ksql": stmt + ";", "streamsProperties": {}},
                    timeout=10,
                    headers={"Accept": "application/vnd.ksql.v1+json"},
                )
                if resp.status_code in (200, 201, 400):  # 400 = already exists = ok
                    ok += 1
            except Exception as e:
                logger.debug("ksqlDB stmt skipped: %s", e)

        logger.info("ksqlDB init: %d/%d statements processed", ok, len(statements))
        return True
    except Exception as exc:
        logger.warning("ksqlDB init failed: %s — streaming aggregations disabled", exc)
        return False
