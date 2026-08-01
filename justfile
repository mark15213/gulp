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

# Run the dev stack: web + api + worker (the iOS client runs from Xcode — `just ios`)
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
ios:
    open apps/ios/Gulp.xcodeproj
# Unit tests only. The integration suite is skipped by name rather than
# self-skipping on a missing variable: a test that quietly passes when it
# never ran is worse than no test.
ios-test device="iPhone 17":
    xcodebuild test -project apps/ios/Gulp.xcodeproj -scheme Gulp \
      -destination 'platform=iOS Simulator,name={{device}}' \
      -skip-testing:GulpTests/AuthIntegrationTests | tail -40

# Everything, including the integration suite, against a running `just dev`.
# The API address lives in the scheme's test environment (GULP_TEST_API) —
# xcodebuild only forwards a unit-test target's environment from there, and it
# does not expand $(...) in that value, so it is a literal. Point it elsewhere
# by editing the scheme.
ios-test-live device="iPhone 17":
    xcodebuild test -project apps/ios/Gulp.xcodeproj -scheme Gulp \
      -destination 'platform=iOS Simulator,name={{device}}' | tail -45
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

# Regenerate every client from the API's OpenAPI schema. The schema is the
# contract (docs/05 D2), so all generated clients are refreshed together —
# never regenerate one and leave the others behind.
gen-client:
    uv run --package gulp-api python -m app.export_openapi > packages/api-client/openapi.json
    pnpm --filter @gulp/api-client generate
    just gen-client-swift

# Swift half of gen-client: normalise the schema, then regenerate. No-ops
# until the iOS package exists so a repo without a Swift toolchain can still
# run `just gen-client`. The normalisation step is not optional — see
# apps/ios/Tools/openapi_for_swift.py for what it repairs.
gen-client-swift:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -d apps/ios/Packages/GulpAPI ]; then
      echo "skip: apps/ios/Packages/GulpAPI not scaffolded yet"
      exit 0
    fi
    python3 apps/ios/Tools/openapi_for_swift.py \
      packages/api-client/openapi.json \
      apps/ios/Packages/GulpAPI/Sources/GulpAPI/openapi.json
    cd apps/ios/Packages/GulpAPI && swift package \
      --allow-writing-to-package-directory \
      generate-code-from-openapi --target GulpAPI

# Alembic migrations (run from services/api/ so alembic.ini is picked up)
migrate message:
    cd services/api && uv run --package gulp-api alembic revision --autogenerate -m "{{message}}"
migrate-up:
    cd services/api && uv run --package gulp-api alembic upgrade head
