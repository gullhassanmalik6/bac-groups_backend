#!/bin/sh
set -eu
cd /app
echo "[start] running alembic migrations..."
alembic upgrade head
if [ "${RUN_SEED_ON_START:-true}" = "true" ]; then
  echo "[start] running database seed..."
  python -m scripts.seed
fi
echo "[start] launching uvicorn on port ${PORT:-8000}..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
