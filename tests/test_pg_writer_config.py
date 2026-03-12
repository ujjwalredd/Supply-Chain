"""Configuration tests for ingestion.pg_writer import-time DB URL setup."""

import importlib
import sys

import pytest
from sqlalchemy.engine.url import make_url


MODULE_NAME = "ingestion.pg_writer"


@pytest.fixture(autouse=True)
def _cleanup_pg_writer_module():
    """Force a clean module import for each test (config is evaluated at import)."""
    sys.modules.pop(MODULE_NAME, None)
    yield
    sys.modules.pop(MODULE_NAME, None)


def _import_pg_writer():
    return importlib.import_module(MODULE_NAME)


def test_builds_database_url_from_postgres_parts_with_special_password(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "sc_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "pa@ss:wo?rd/with#chars")
    monkeypatch.setenv("POSTGRES_HOST", "db.local")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "supply_db")

    pg_writer = _import_pg_writer()
    parsed = make_url(pg_writer.DATABASE_URL)

    assert parsed.username == "sc_user"
    assert parsed.password == "pa@ss:wo?rd/with#chars"
    assert parsed.host == "db.local"
    assert parsed.port == 5432
    assert parsed.database == "supply_db"


def test_database_url_env_takes_precedence(monkeypatch):
    explicit = "postgresql://app:pw@postgres:5432/prod_db"
    monkeypatch.setenv("DATABASE_URL", explicit)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    pg_writer = _import_pg_writer()
    assert pg_writer.DATABASE_URL == explicit


def test_missing_database_credentials_raises_runtime_error(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)

    with pytest.raises(RuntimeError, match="database credentials not configured"):
        _import_pg_writer()


def test_invalid_postgres_port_raises_runtime_error(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "sc_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "pw")
    monkeypatch.setenv("POSTGRES_HOST", "db.local")
    monkeypatch.setenv("POSTGRES_PORT", "not-a-port")
    monkeypatch.setenv("POSTGRES_DB", "supply_db")

    with pytest.raises(RuntimeError, match="invalid POSTGRES_PORT"):
        _import_pg_writer()
