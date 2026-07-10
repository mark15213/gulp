# Gulp — unified command entry. One surface for two languages.
# See docs/05-repo-structure.md §5.3.
set shell := ["bash", "-cu"]

# List recipes
default:
    @just --list

# Bring the whole repo up (TS + Python deps)
setup:
    corepack enable
    pnpm install
    uv sync

# Local infra (Postgres, Redis queue)
up:
    docker compose -f infra/docker-compose.yml up -d
down:
    docker compose -f infra/docker-compose.yml down

# Run the web-first dev stack: web + api + worker (mobile deferred — use `just mobile`)
dev:
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill 0' EXIT
    pnpm --filter @gulp/web dev &
    uv run --package gulp-api uvicorn app.main:app --reload &
    (cd services/worker && uv run --package gulp-worker python -m app.tasks) &
    wait

# Individual processes
web:
    pnpm --filter @gulp/web dev
mobile:
    pnpm --filter @gulp/mobile start
api:
    uv run --package gulp-api uvicorn app.main:app --reload
worker:
    cd services/worker && uv run --package gulp-worker python -m app.tasks

# Quality gates (both languages)
lint:
    pnpm turbo run lint
    uv run ruff check .
    # mypy runs per service: api and worker both expose a top-level `app`
    # package, and each service has a tests/conftest.py (same reason pytest
    # runs per package).
    uv run mypy services/shared
    uv run mypy services/api
    uv run mypy services/worker
format:
    pnpm exec prettier --write .
    uv run ruff format .
test:
    pnpm turbo run test
    # api and worker both expose a top-level `app` package, so run pytest per
    # Python package just like mypy.
    uv run pytest services/shared services/api
    cd services/worker && uv run --package gulp-worker pytest

# Regenerate the TS api-client from the API's OpenAPI schema
gen-client:
    uv run --package gulp-api python -m app.export_openapi > packages/api-client/openapi.json
    pnpm --filter @gulp/api-client generate

# Alembic migrations (run from services/api/ so alembic.ini is picked up)
migrate message:
    cd services/api && uv run --package gulp-api alembic revision --autogenerate -m "{{message}}"
migrate-up:
    cd services/api && uv run --package gulp-api alembic upgrade head
