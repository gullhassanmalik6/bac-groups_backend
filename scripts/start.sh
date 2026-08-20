#!/bin/sh
set -eu
cd /app
alembic upgrade head
python -m scripts.seed
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
