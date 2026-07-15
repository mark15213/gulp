#!/usr/bin/env bash
# Single Railway service running BOTH api and worker.
#
# Why combined: Railway volumes attach to one service, but the worker WRITES
# figures that the api READS (gulp_shared/media.py) — so they must share one
# filesystem. Running both here + one Volume at /data/media is the lightweight
# way to keep that working.
#
# If either process exits, `trap 'kill 0'` tears the whole service down so
# Railway restarts BOTH — never a silently-dead worker eating jobs.
set -euo pipefail
trap 'kill 0' EXIT

cd /app

# Migrate before serving (idempotent — no-op when already at head). alembic.ini
# lives in services/api.
( cd services/api && uv run --no-sync --package gulp-api alembic upgrade head )

# api binds Railway's $PORT (8000 locally); worker is the always-on arq consumer.
uv run --no-sync --package gulp-api uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" &
( cd services/worker && exec uv run --no-sync --package gulp-worker python -m app.tasks ) &

wait -n   # return as soon as either exits
exit 1    # non-zero → Railway restarts the service (trap kills the survivor)
