"""Tests for FastAPI app setup and router structure — no DB required.

Uses starlette TestClient with init_db mocked so no live PostgreSQL is needed.
"""

from unittest.mock import AsyncMock, patch


def test_health_returns_ok():
    """GET /health should return {status: ok} without a live database."""
    with patch("api.database.init_db", new_callable=AsyncMock):
        from api.main import app
        from starlette.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["service"] == "supply-chain-api"


def test_root_lists_endpoints():
    """GET / should list known endpoints."""
    with patch("api.database.init_db", new_callable=AsyncMock):
        from api.main import app
        from starlette.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "endpoints" in data
    for key in ("orders", "suppliers", "forecasts", "network"):
        assert key in data["endpoints"], f"Missing endpoint key: {key}"


def test_unknown_route_returns_404():
    """Unknown paths should 404."""
    with patch("api.database.init_db", new_callable=AsyncMock):
        from api.main import app
        from starlette.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/this_route_does_not_exist")
    assert resp.status_code == 404


def test_forecasts_summary_no_parquet(tmp_path):
    """GET /forecasts/summary returns zero counts when gold parquet is missing."""
    import api.routers.forecasts as fr_module
    original = fr_module.GOLD_PATH
    fr_module.GOLD_PATH = str(tmp_path / "nonexistent")
    try:
        with patch("api.database.init_db", new_callable=AsyncMock):
            from api.main import app
            from starlette.testclient import TestClient
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/forecasts/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["at_risk_count"] == 0
        assert data["suppliers_affected"] == 0
    finally:
        fr_module.GOLD_PATH = original
