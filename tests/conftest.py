"""Pytest configuration for the supply-chain-os test suite."""

import os

# Set dummy env vars so modules that read them at import time don't crash.
os.environ.setdefault("ANTHROPIC_API_KEY", "ci-placeholder")
os.environ.setdefault("DATABASE_URL", "postgresql://supplychain:supplychain_secret@localhost:5432/supply_chain_db")
os.environ.setdefault("GOLD_PATH", "data/gold")
os.environ.setdefault("SILVER_PATH", "data/silver")
os.environ.setdefault("BRONZE_PATH", "data/bronze")

# Pre-import api.database so that patch("api.database.init_db") resolves correctly.
# unittest.mock.patch uses pkgutil.resolve_name which calls getattr(api, 'database')
# and that only works if api.database has already been imported as a submodule.
import api.database  # noqa: F401, E402
