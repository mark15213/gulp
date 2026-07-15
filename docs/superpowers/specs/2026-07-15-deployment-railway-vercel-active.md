# Deployment — Vercel (web) + Railway (backend), managed & push-to-deploy

**Date:** 2026-07-15
**Status:** approved (design) — **the active deployment plan**
**Scope:** first hosted deployment of the web-first stack as a **private beta**, on managed platforms with **push-to-deploy**. Vercel hosts `apps/web`; Railway hosts one combined api+worker service plus managed Postgres + Redis (and optionally RSSHub). Config + **two small code changes** (§8).

> **Supersedes** both prior deployment specs:
> - [`2026-07-07-deployment-railway-vercel-design.md`](2026-07-07-deployment-railway-vercel-design.md) — same platforms, but it predates the same-origin cookie model, BYOK/`CREDENTIAL_SECRET`, the invite gate, the figures feature, and the RSSHub subscription system. This doc is the current, reconciled version.
> - [`2026-07-15-deployment-aliyun-selfhost-design.md`](2026-07-15-deployment-aliyun-selfhost-design.md) — the self-host route the owner tried and set aside for being too heavy. Its **invite-code gate carries over**; its self-host infra kit was removed.

## 1. Problem & goal

Put the stack online for a small invited group with **minimum ops** and **push-to-deploy** (the deciding requirement). `services/worker` is a **persistent arq process** (blocking-consumes a Redis queue), not a request handler — that rules out all-serverless and mandates an always-on container host. Railway runs always-on containers + managed Postgres/Redis with per-service git watching; Vercel is the best Next.js host with global edge + PR previews.

**Confirmed decisions (owner):**
- Platforms: **Vercel** (web) + **Railway** (backend). Push-to-deploy from GitHub (`origin = git@github.com:mark15213/gulp.git`).
- **api + worker run in ONE Railway service** (a start script launches both) so they share a filesystem — required because Railway volumes are single-service and the worker **writes** figures while the api **reads** them (`gulp_shared/media.py`).
- A **Railway Volume** at `/data/media` persists figures across redeploys.
- Registration gated by invite code `5566` (already built).

## 2. Decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Platforms | Vercel (web) + Railway (backend). |
| D2 | Backend shape | **One combined Railway service** running api (uvicorn on `$PORT`) **and** worker (arq) via `infra/start-combined.sh` (`trap 'kill 0' EXIT` + `wait -n`: if either process exits, the service exits and Railway restarts both — no silent worker death). Managed **Postgres** + **Redis** plugins. |
| D3 | Media | Single Railway **Volume** mounted at `/data/media`; `MEDIA_DIR=/data/media`, `EXPORT_DIR=/data/exports`. The combined service is what makes the shared filesystem possible. |
| D4 | Same-origin routing | Browser hits only the Vercel origin; the Next rewrite proxies `/api/*` to the Railway backend URL (`API_INTERNAL_URL=https://<railway-app>`). First-party cookie, **no CORS, no code change** (api-client browser base is the static `/api`). Better than the 2026-07-07 spec's cross-origin CORS. |
| D5 | Postgres DSN | **Code change:** a `field_validator` on `settings.database_url` rewrites a leading `postgresql://` / `postgres://` to `postgresql+psycopg://`, because Railway's Postgres plugin injects the bare `postgresql://` DSN and SQLAlchemy needs the psycopg-3 driver prefix (§8). |
| D6 | Images | Reuse `infra/Dockerfile.python` for the combined service (full uv workspace synced). Web needs **no Dockerfile** — Vercel builds Next natively via Turborepo. Revert `output: "standalone"` (added for the dropped self-host web image, unused on Vercel). |
| D7 | Migrations | Railway **pre-deploy (release) command**: `cd services/api && uv run --no-sync --package gulp-api alembic upgrade head`, before the new release serves. |
| D8 | Registration gate | `INVITE_CODE=5566` on the Railway service (feature already shipped). |
| D9 | RSSHub | Optional 5th Railway service (`diygod/rsshub`) or point `RSSHUB_BASE_URL` at a public instance; feeds are non-core for the initial beta. |
| D10 | Deploy trigger | Push to GitHub `main` → Railway + Vercel auto-deploy (PR previews on Vercel). |

**Non-goals:** multi-region; horizontal scale; independent api/worker scaling (they share one service now); object-storage media (the scale-up path if the combined service outgrows one box); centralized logs/metrics; mobile.

## 3. Architecture / topology

```
                Browser
                   │  https  (one origin: the Vercel domain)
          ┌────────▼─────────┐
          │  Vercel: apps/web │  Next rewrite: /api/* ──▶ API_INTERNAL_URL
          └────────┬─────────┘                              (Railway app URL)
                   │ server-to-server (SSR + rewrite proxy)
          ┌────────▼───────────────────────────────┐
          │  Railway project "gulp"                 │
          │  ┌───────────────────────────────────┐ │
          │  │ app service (infra/Dockerfile.py)  │ │
          │  │   start-combined.sh:               │ │
          │  │     • uvicorn app.main:app :$PORT  │ │ ◀── public URL, /health
          │  │     • python -m app.tasks (arq)    │ │
          │  │   Volume ▶ /data/media             │ │
          │  └───────────────────────────────────┘ │
          │   Postgres plugin    Redis plugin       │
          │   [rsshub service — optional]           │
          └─────────────────────────────────────────┘
```

## 4. Reconciliation — carries over / dropped / new

- **Carries over (already on `main`):** invite-code gate (backend + web + client). Reused: `infra/Dockerfile.python`, repo-root `.dockerignore`, `infra/docker-compose.yml` (local dev).
- **Dropped (self-host only):** `infra/Dockerfile.web`, `compose.prod.yml`, `Caddyfile`, `deploy.sh`, `backup.sh`, `env.prod.example`, `README.md`.
- **New:** the DSN validator (§8), `infra/start-combined.sh`, `railway.json` (build + start + release config-as-code), `vercel.json`, revert of `output: "standalone"`, and the deploy guide `docs/deploy-railway-vercel.md`.

## 5. Environment / secrets

**Railway — combined `app` service** (secrets generated with `openssl rand -hex 32`; set in the Railway dashboard, never committed):

| Variable | Value |
|---|---|
| `DATABASE_URL` | reference the Postgres plugin var (bare `postgresql://…`; normalized by the D5 validator) |
| `REDIS_URL` | reference the Redis plugin var |
| `AUTH_SECRET` | secret |
| `CREDENTIAL_SECRET` | secret — encrypts BYOK keys; **back up off-platform** (losing it makes stored keys undecryptable) |
| `SESSION_COOKIE_SECURE` | `true` |
| `INVITE_CODE` | `5566` |
| `ANTHROPIC_API_KEY` | empty (BYOK) |
| `WEB_ORIGIN` | `https://<vercel-domain>` |
| `MEDIA_DIR` / `EXPORT_DIR` | `/data/media` / `/data/exports` (the volume) |
| `RSSHUB_BASE_URL` | the rsshub service URL or a public instance |
| `LOG_LEVEL` | `INFO` |
| `PORT` | injected by Railway; uvicorn binds it |

**Vercel — web:** `API_INTERNAL_URL = https://<railway-app-url>` (the Next rewrite target + SSR base). `NEXT_PUBLIC_API_URL` is unused on the same-origin path.

## 6. Migrations & first-boot

- Railway **pre-deploy command** runs `alembic upgrade head` (cwd `services/api`) before the new release serves; the worker performs no migrations.
- **Seeded dev account** (`dev@example.com`): remove or change its password immediately after first deploy.

## 7. Deploy flow

Push to GitHub `main` → Railway rebuilds the app service (release command migrates, then start-combined.sh boots api+worker) and Vercel rebuilds web. PRs get Vercel previews. Rollback: Railway/Vercel dashboards keep prior deploys (one-click redeploy), or revert the commit and push.

## 8. Code changes (the only two)

1. **DSN normalization** — `services/shared/gulp_shared/settings.py`: a pydantic `field_validator` on `database_url` rewriting `postgresql://` / `postgres://` → `postgresql+psycopg://` (idempotent; leaves an already-prefixed DSN untouched). Portable to any provider's raw DSN. Test-covered.
2. **Revert standalone** — remove `output: "standalone"` from `apps/web/next.config.ts` (unused on Vercel).

Plus config-as-code (not app logic): `infra/start-combined.sh`, `railway.json`, `vercel.json`, and file removals (§4).

## 9. Console setup (owner; full steps in `docs/deploy-railway-vercel.md`)

- **Railway:** new project from the GitHub repo → app service (Dockerfile `infra/Dockerfile.python`, start `bash infra/start-combined.sh`, pre-deploy the migration) + Postgres plugin + Redis plugin + a Volume at `/data/media` + the env vars (§5) + (optional) an rsshub service.
- **Vercel:** import the repo, root directory `apps/web`, add `API_INTERNAL_URL`, deploy.
- **DNS/domain:** optional custom domains on both; platform-provided `*.vercel.app` / `*.up.railway.app` work for a beta.

## 10. Verification / smoke test

1. `GET https://<railway-app>/health` → `{"status":"ok"}`.
2. Load the Vercel app; browser Network tab shows `/api/...` hitting the Vercel origin and returning 200 (same-origin rewrite + first-party cookie).
3. Register with invite code `5566`; wrong/absent code is rejected.
4. Forward a capture → the worker (same service) picks up the arq job → snapshot advances to a ready pack; a paper's figures render (proves the shared volume).
5. Redeploy; confirm figures still render (volume persistence) and re-login works.

## 11. Out of scope / future

- Object-storage media (R2/S3) — the upgrade if api+worker need to split back into separate services.
- Independent api/worker scaling; multi-region; centralized logs/metrics.
- Custom domains / gating deploys on green CI.
