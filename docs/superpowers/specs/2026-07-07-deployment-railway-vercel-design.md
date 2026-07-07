# Deployment — Railway (backend) + Vercel (web), auto-deploy on push

**Date:** 2026-07-07
**Status:** approved (design)
**Scope:** first production deployment of the web-first stack (web + api + worker + Postgres + Redis) with push-triggered redeploys. Infra/config only — no business-logic changes except one settings normalization. China-market deployment, media persistence, and custom domains are explicitly out of scope (see §9).

## Problem

The system runs locally via `just dev` (web + api + worker) and `just up` (Postgres + Redis in Docker), but has no hosted environment. We need a deployment target that:

- hosts all five pieces: `apps/web` (Next.js), `services/api` (FastAPI), `services/worker` (**arq**, a long-running process), plus managed Postgres and Redis;
- **redeploys automatically on `git push`** — the core requirement;
- fits an **early-stage, cost-sensitive, low-ops personal project** with **no existing cloud accounts** and a user base that is currently **split / undecided between China and abroad**.

## Decision

**Railway** hosts the backend (`api`, `worker`, Postgres, Redis); **Vercel** hosts the Next.js web app.

The deciding constraint is architectural: `services/worker` is a **persistent arq process** (`run_worker(WorkerSettings)`, blocking-consumes a Redis queue), not a request/response handler. That rules out an all-serverless design (Vercel/Netlify functions time out and cannot host it). The stack needs a platform that runs always-on containers *and* offers managed Postgres + Redis with push-to-deploy — Railway does all of it in one project with per-service git watching.

Web is split onto Vercel because it is the best-in-class Next.js host (global edge CDN, PR preview deploys, best DX), and its edge network is the most useful hedge for the "geography undecided" answer — the front-end is served fast globally while the backend stays a single Railway region.

### Rejected alternatives

- **AWS** — the same stack means App Runner/ECS + RDS + ElastiCache + VPC/IAM. Too much ops for an early, cost-sensitive project with no credits. It is the *scale-up* target, not the starting point.
- **Alibaba/Tencent Cloud** — only justified if mainland China is the *confirmed primary* market **and** we accept ICP filing (China entity + domain, multi-week lead time). Users are "both/undecided," so this violates the low-ops, low-cost constraint. Revisit as a separate project if China becomes primary.
- **All-on-Railway (web included)** — viable and simplest (one dashboard), but forgoes Vercel's edge/DX advantage for the front-end. Kept as the fallback if the two-dashboard split proves annoying.
- **Render / Fly.io** — near-equivalents. Render's free Postgres expires at 90 days; Fly is stronger for future multi-region but heavier to operate. Not chosen, but either would work.

## Architecture / topology

**Railway project `gulp`** — four services, all tracking the same GitHub repo:

| Service    | Process                                   | Exposure          |
|------------|-------------------------------------------|-------------------|
| `api`      | `uvicorn app.main:app` (has `/health`)    | public domain     |
| `worker`   | `python -m app.tasks` (arq, always-on)    | none (no port)    |
| Postgres   | Railway managed plugin                     | private network   |
| Redis      | Railway managed plugin (arq queue)         | private network   |

**Vercel project** — `apps/web` (Next.js 15). Root directory `apps/web`; built through Turborepo so its workspace deps (`@gulp/api-client`, `@gulp/ui`, `@gulp/core`) compile as part of the build.

## Build strategy

- **api / worker** — one **Dockerfile each**, committed under `infra/` (e.g. `infra/api.Dockerfile`, `infra/worker.Dockerfile`). Build context is the **repo root** because this is a `uv` workspace: the build needs `uv.lock`, root `pyproject.toml`, and `services/shared`. Each image installs exactly one service (`uv sync --package gulp-api` / `--package gulp-worker`), which also sidesteps the known api-vs-worker top-level `app` package collision — only one `app` package exists per image. Multi-stage to keep images slim.
  - `api` image `CMD`: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (Railway injects `$PORT`).
  - `worker` image `CMD`: `python -m app.tasks`.
- **web** — no Dockerfile. Vercel natively detects pnpm + Turborepo; root directory `apps/web`, default Next.js build.

Committing the Dockerfiles keeps the backend build reproducible and config-as-code. Railway managed plugins (Postgres/Redis) and per-service settings (watch paths, pre-deploy, env references) are configured in the Railway dashboard; a `railway.json` per service is optional and can be added later.

## The one code change: Postgres DSN prefix normalization

`settings.database_url` defaults to `postgresql+psycopg://…` — SQLAlchemy needs the `+psycopg` driver prefix for psycopg 3. **Railway's Postgres plugin provides `DATABASE_URL` as `postgresql://…`** (no prefix), which SQLAlchemy would route to the absent psycopg2 driver and fail.

Fix in `services/shared/gulp_shared/settings.py`: add a pydantic field validator on `database_url` that rewrites a leading `postgresql://` (and `postgres://`) to `postgresql+psycopg://`. This makes the app portable to any provider's raw DSN and is more robust than hand-assembling the DSN from Railway's individual `PG*` variables.

Redis needs no change: `RedisSettings.from_dsn(settings.redis_url)` accepts Railway's `redis://…` directly.

## Migrations

Alembic runs as the `api` service's **pre-deploy command**: `alembic upgrade head`, executed with working directory = the api service dir in the image (where `alembic.ini` lives), so the new schema is in place before the new revision starts serving. The worker performs no migrations.

## Environment / secrets

**Railway — `api`** (worker shares `DATABASE_URL` / `REDIS_URL` / `ANTHROPIC_API_KEY`):

| Variable            | Value                                                        |
|---------------------|-------------------------------------------------------------|
| `DATABASE_URL`      | reference to Postgres plugin (normalized by the validator)  |
| `REDIS_URL`         | reference to Redis plugin                                    |
| `ANTHROPIC_API_KEY` | secret                                                      |
| `AUTH_SECRET`       | secret                                                      |
| `WEB_ORIGIN`        | `https://<vercel-production-domain>` (drives CORS allow-list)|

**Vercel — web:**

| Variable              | Value                          |
|-----------------------|--------------------------------|
| `NEXT_PUBLIC_API_URL` | `https://<railway-api-domain>` |

**CORS:** already derived from `web_origin` via `settings.cors_origins` — no code change; only the production `WEB_ORIGIN` value needs setting.

## Auto-deploy on push

- **Railway** — connect the GitHub repo; each service tracks `main` with **watch paths** so only the relevant service rebuilds: `api` on `services/api/**` + `services/shared/**` + `infra/api.Dockerfile`; `worker` on `services/worker/**` + `services/shared/**` + `infra/worker.Dockerfile`. Push → build → deploy (api runs the pre-deploy migration first).
- **Vercel** — connect the repo; push to `main` = production deploy, pull requests get **preview deploys** automatically.
- **CI stays the quality gate** — the existing `.github/workflows/ci.yml` (lint/test/build) keeps running on push/PR. Deploys are triggered by each platform's own GitHub integration; we do **not** hand-write a deploy Action. (Gating deploys on green CI is a possible later refinement, not part of this slice.)

## Known limitations (accepted for now)

- **Ephemeral filesystem** — `export_dir` / `media_dir` default to `/tmp`, which is wiped on every Railway restart/redeploy. Exports and extracted media do **not** persist across deploys. Acceptable at this stage; a Railway Volume or object storage is deferred (§9). Worth a one-line note in the deploy runbook so it isn't mistaken for a bug.
- **Single backend region** — cross-border latency to the API is unaddressed; only the Vercel-hosted front-end benefits from edge distribution.

## Verification / smoke test

After first deploy:
1. `GET https://<api>/health` → `{"status":"ok"}`.
2. Load the Vercel web app; confirm it reaches the API (no CORS error in the browser console) — i.e. `WEB_ORIGIN` ↔ `NEXT_PUBLIC_API_URL` are consistent.
3. Submit a capture; confirm the `worker` picks up the arq job (worker logs) and the snapshot advances — proves Redis wiring + always-on worker.
4. Confirm the pre-deploy migration ran (api deploy logs show `alembic upgrade head`).

## Out of scope / future

- **China-market deployment** — ICP filing + Alibaba/Tencent, or cross-border acceleration. Separate project, triggered only if China becomes the confirmed primary market.
- **Persistent media/exports** — Railway Volume or S3-compatible object storage.
- **Custom domains** on both api and web (start on the platform-provided `*.up.railway.app` / `*.vercel.app`).
- **Multi-region backend** (would revisit Fly.io).
- **Gating deploys on green CI.**
