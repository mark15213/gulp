#!/usr/bin/env bash
# Build -> migrate -> up -> smoke. Run on the host from anywhere.
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root
COMPOSE=(docker compose --env-file infra/.env -f infra/compose.prod.yml)

git pull --ff-only
"${COMPOSE[@]}" build
# One-off migration before the new revisions start serving (alembic.ini is in services/api).
"${COMPOSE[@]}" run --rm --workdir /app/services/api api \
  uv run --no-sync --package gulp-api alembic upgrade head
"${COMPOSE[@]}" up -d
docker image prune -f

# Smoke: /api/health is proxied by the Next rewrite to api:8000/health.
set -a; source infra/.env; set +a
curl -fsS "https://${DOMAIN}/api/health" && echo "  deploy OK"
