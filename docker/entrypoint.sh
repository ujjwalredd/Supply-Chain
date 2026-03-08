#!/bin/bash
# Supply Chain AI OS — FastAPI entrypoint
# Runs Alembic migrations, seeds DB if empty, then starts the API server.
set -e

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "WARNING: ANTHROPIC_API_KEY is not set — /ai/analyze endpoints will return 503"
fi

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Seeding database (idempotent — skips if already seeded)..."
timeout 60 python scripts/seed_db.py || echo "WARNING: seed_db timed out or failed — continuing with existing data"

echo "==> Starting Supply Chain API..."
exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-1}" \
    --log-level "${LOG_LEVEL:-info}"
