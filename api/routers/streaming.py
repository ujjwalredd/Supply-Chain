"""
ksqlDB streaming aggregations API router.
Exposes real-time 5-minute rolling metrics computed by ksqlDB persistent queries.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

router = APIRouter(prefix="/streaming", tags=["streaming"])


@router.get("/aggregations")
async def get_streaming_aggregations() -> dict[str, Any]:
    """
    Return latest ksqlDB 5-minute window aggregations:
    - supplier_delay_rates: delay rate per supplier
    - region_demand: order demand per region
    Falls back gracefully if ksqlDB is unavailable.
    """
    try:
        from streaming.ksql_queries import get_supplier_delay_rates, get_region_demand
        supplier_rates = get_supplier_delay_rates(limit=20)
        region_demand = get_region_demand(limit=10)
        return {
            "supplier_delay_rates": supplier_rates,
            "region_demand": region_demand,
            "source": "ksqldb",
        }
    except Exception as exc:
        return {
            "supplier_delay_rates": [],
            "region_demand": [],
            "source": "unavailable",
            "error": str(exc),
        }


@router.get("/supplier-delay-rates")
async def get_supplier_delay_rates(limit: int = Query(20, le=100)) -> dict[str, Any]:
    """5-minute rolling delay rate per supplier from ksqlDB."""
    try:
        from streaming.ksql_queries import get_supplier_delay_rates as _get
        return {"data": _get(limit=limit), "source": "ksqldb"}
    except Exception as exc:
        return {"data": [], "error": str(exc)}


@router.get("/region-demand")
async def get_region_demand(limit: int = Query(10, le=50)) -> dict[str, Any]:
    """5-minute rolling demand aggregation per region from ksqlDB."""
    try:
        from streaming.ksql_queries import get_region_demand as _get
        return {"data": _get(limit=limit), "source": "ksqldb"}
    except Exception as exc:
        return {"data": [], "error": str(exc)}


@router.post("/init")
async def init_ksql() -> dict[str, Any]:
    """
    Initialize ksqlDB streams and persistent queries.
    Safe to call multiple times (CREATE IF NOT EXISTS).
    """
    try:
        from streaming.ksql_queries import init_ksql_streams
        success = init_ksql_streams()
        return {"success": success, "message": "ksqlDB streams initialized" if success else "ksqlDB unavailable"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
