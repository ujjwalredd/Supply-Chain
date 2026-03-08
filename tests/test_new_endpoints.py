"""Tests for /alerts/trend and /actions/stats endpoints."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_session_with_all(rows):
    """Return an AsyncSession mock whose execute().all() returns rows."""
    mock_result = MagicMock()
    mock_result.all.return_value = rows
    session = AsyncMock()
    session.execute.return_value = mock_result
    return session


def _mock_session_with_one(row):
    """Return an AsyncSession mock whose execute().one() returns row."""
    mock_result = MagicMock()
    mock_result.one.return_value = row
    session = AsyncMock()
    session.execute.return_value = mock_result
    return session


def _client_with_db(mock_session):
    """Return (TestClient, get_db) with the DB dependency overridden."""
    with patch("api.database.init_db", new_callable=AsyncMock):
        from api.database import get_db
        from api.main import app
        from starlette.testclient import TestClient

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app, raise_server_exceptions=False)
        return client, get_db


# ── /alerts/trend ─────────────────────────────────────────────────────────────

def test_alerts_trend_returns_7_days():
    """GET /alerts/trend returns a list of exactly 7 day buckets."""
    session = _mock_session_with_all([])
    client, get_db_key = _client_with_db(session)
    try:
        resp = client.get("/alerts/trend?days=7")
    finally:
        from api.main import app
        app.dependency_overrides.pop(get_db_key, None)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 7
    for entry in data:
        assert "date" in entry
        assert "CRITICAL" in entry
        assert "HIGH" in entry
        assert "MEDIUM" in entry
        assert "total" in entry


def test_alerts_trend_fills_severity_counts():
    """GET /alerts/trend populates counts from returned DB rows."""
    today = date.today().isoformat()
    mock_row = MagicMock()
    mock_row.day = today
    mock_row.severity = "HIGH"
    mock_row.count = 4

    session = _mock_session_with_all([mock_row])
    client, get_db_key = _client_with_db(session)
    try:
        resp = client.get("/alerts/trend?days=7")
    finally:
        from api.main import app
        app.dependency_overrides.pop(get_db_key, None)

    assert resp.status_code == 200
    data = resp.json()
    today_entry = next((d for d in data if d["date"] == today), None)
    assert today_entry is not None
    assert today_entry["HIGH"] == 4
    assert today_entry["total"] == 4
    assert today_entry["CRITICAL"] == 0


def test_alerts_trend_unknown_severity_maps_to_medium():
    """Severities not in CRITICAL/HIGH/MEDIUM are bucketed under MEDIUM."""
    today = date.today().isoformat()
    mock_row = MagicMock()
    mock_row.day = today
    mock_row.severity = "LOW"
    mock_row.count = 2

    session = _mock_session_with_all([mock_row])
    client, get_db_key = _client_with_db(session)
    try:
        resp = client.get("/alerts/trend?days=7")
    finally:
        from api.main import app
        app.dependency_overrides.pop(get_db_key, None)

    assert resp.status_code == 200
    data = resp.json()
    today_entry = next((d for d in data if d["date"] == today), None)
    assert today_entry is not None
    assert today_entry["MEDIUM"] == 2


def test_alerts_trend_days_param_controls_length():
    """The days query param controls how many buckets are returned."""
    session = _mock_session_with_all([])
    client, get_db_key = _client_with_db(session)
    try:
        resp = client.get("/alerts/trend?days=3")
    finally:
        from api.main import app
        app.dependency_overrides.pop(get_db_key, None)

    assert resp.status_code == 200
    assert len(resp.json()) == 3


# ── /actions/stats ─────────────────────────────────────────────────────────────

def test_actions_stats_returns_mttr():
    """GET /actions/stats returns total_completed and mttr_minutes."""
    mock_row = MagicMock()
    mock_row.total = 5
    mock_row.avg_resolve_seconds = 1800.0  # 30 minutes

    session = _mock_session_with_one(mock_row)
    client, get_db_key = _client_with_db(session)
    try:
        resp = client.get("/actions/stats")
    finally:
        from api.main import app
        app.dependency_overrides.pop(get_db_key, None)

    assert resp.status_code == 200
    data = resp.json()
    assert "total_completed" in data
    assert "mttr_minutes" in data
    assert data["total_completed"] == 5
    assert data["mttr_minutes"] == 30.0


def test_actions_stats_no_completed_actions():
    """GET /actions/stats returns zeros when no completed actions exist."""
    mock_row = MagicMock()
    mock_row.total = 0
    mock_row.avg_resolve_seconds = None

    session = _mock_session_with_one(mock_row)
    client, get_db_key = _client_with_db(session)
    try:
        resp = client.get("/actions/stats")
    finally:
        from api.main import app
        app.dependency_overrides.pop(get_db_key, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_completed"] == 0
    assert data["mttr_minutes"] == 0.0


def test_actions_stats_mttr_rounds_to_one_decimal():
    """mttr_minutes is rounded to 1 decimal place."""
    mock_row = MagicMock()
    mock_row.total = 3
    mock_row.avg_resolve_seconds = 754.0  # 12.566... minutes

    session = _mock_session_with_one(mock_row)
    client, get_db_key = _client_with_db(session)
    try:
        resp = client.get("/actions/stats")
    finally:
        from api.main import app
        app.dependency_overrides.pop(get_db_key, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["mttr_minutes"] == round(754.0 / 60, 1)
