#!/bin/bash
# Supply Chain AI OS — FastAPI entrypoint
# Runs Alembic migrations, seeds DB if empty, then starts the API server.
set -e

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Seeding database (idempotent — skips if already seeded)..."
python scripts/seed_db.py

echo "==> Starting Supply Chain API..."
exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-1}" \
    --log-level "${LOG_LEVEL:-info}"
