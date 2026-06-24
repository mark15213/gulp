# services/api — FastAPI HTTP API

The responsive HTTP surface. **Conventional layering** (docs/05 D4) — keep the layers honest:

- `app/routers/` — HTTP endpoints, grouped by resource. **Thin**: parse/validate, call a service, return. No business logic here.
- `app/services/` — business logic; orchestrates the `gulp_shared` ORM models.
- `app/schemas/` — Pydantic request/response models (this is what becomes OpenAPI).
- `app/core/` — auth, config, dependency wiring (server side of S0 Foundation).
- Persistence (ORM models, db session, settings) lives in **`gulp_shared`**, not here.

## Rules

- **Capture never blocks on AI** (docs/04 S1). Heavy/slow work is enqueued for `services/worker`; the handler returns immediately.
- The API is the **source of truth for the contract**: `app/schemas` → OpenAPI → `packages/api-client`. After changing schemas, run `just gen-client`.

## Commands

- `just api` — dev server (uvicorn, reload)
- `just migrate "msg"` / `just migrate-up` — Alembic
- `uv run pytest` (from repo root via `just test`)
