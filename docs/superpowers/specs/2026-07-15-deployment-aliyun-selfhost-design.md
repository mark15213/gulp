# Deployment — self-hosted single VPS on Alibaba Cloud (Singapore), Docker Compose + Caddy

**Date:** 2026-07-15
**Status:** approved (design)
**Scope:** first real hosted deployment of the web-first stack (web + api + worker + Postgres + Redis + RSSHub) as a **private beta** — self plus a handful of invited users. One overseas host, all services in one Docker Compose stack behind Caddy (automatic HTTPS), deployed by a shell script. Infra/config plus **three small code changes** (§10).

> **Supersedes [`2026-07-07-deployment-railway-vercel-design.md`](2026-07-07-deployment-railway-vercel-design.md).** That spec targeted managed PaaS (Railway backend + Vercel web, cross-origin, push-to-deploy) for a "geography-undecided" audience. This one replaces it: a single self-hosted VPS keeps the **same-origin cookie model** intact (no CORS/cross-origin split), fits the private-beta scale, and is fully config-as-code. The prior spec **rejected Alibaba Cloud** only for the *mainland-China + ICP filing* scenario — this deployment uses Alibaba Cloud's **Singapore international region**, which is an ordinary overseas host: clean egress, **no ICP filing**, no proxy layer. The two are not in conflict.

## 1. Problem & goal

The system runs locally via `just dev` (web + api + worker) + `just up` (Postgres + Redis + RSSHub in Docker), but has no hosted environment. We need to put it online for a small invited group so it is reachable from any device over HTTPS, with the knowledge graph safely persisted and backed up.

**Constraints that shaped the design (all confirmed with the owner):**

- **Audience:** small private beta — self + a few invited users. Not a public launch (no autoscaling / multi-region / abuse-hardening yet).
- **Host:** Alibaba Cloud **Simple Application Server** (轻量应用服务器), **Singapore** region, **2 vCPU / 8 GB**.
- **Topology:** single host, everything in one Docker Compose stack, **same-origin** (web and api on one domain), deployed by a script (not CI/CD).
- **Domain:** a new domain (to be purchased), HTTPS mandatory (secure session cookie + BYOK).
- **Network:** overseas region → direct egress to Anthropic/OpenAI/RSSHub upstreams; **no proxy layer**, **no ICP filing**.
- **Registration:** gated by an **invite code** for the beta.

## 2. Decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Host | Alibaba Cloud Simple Application Server, Singapore, 2 vCPU / 8 GB. 8 GB (or 4 GB + swap) is sized for the Next.js **build** memory spike; runtime footprint is ~1–1.5 GB. |
| D2 | Orchestration | One `docker compose` stack on the host: `caddy`, `web`, `api`, `worker`, `db`, `redis`, `rsshub`. |
| D3 | Ingress / TLS | **Caddy** reverse-proxy with automatic Let's Encrypt HTTPS. Only 80/443 exposed to the internet; every other service lives on the internal Docker network with **no host port mapping**. |
| D4 | Same-origin routing | Browser hits only `https://<domain>`; `/api/*` is proxied by the existing Next.js rewrite to the `api` container. This keeps the first-party httpOnly session cookie and BYOK traffic on one HTTPS origin — **no CORS split, no code change** (the api-client already hardcodes browser base = `/api`, §4). |
| D5 | Images | **One Python image** — full uv workspace synced, `uv` retained. api and worker both expose a top-level `app` package (they'd collide if imported ambiguously — the reason `just test`/`just lint` run per-package); the compose file disambiguates at run time exactly as the `justfile` does, by setting each service's `command` to `uv run --package gulp-api` / `--package gulp-worker` (+ `working_dir` for the worker). One **web Dockerfile** (Next.js standalone). |
| D6 | Build location | Build **on the host** (`docker compose build`), matching the script-deploy model — no registry to operate. Cost: build RAM (mitigated by D1). Registry/CI build is the deferred upgrade path (§11). |
| D7 | Deploy | A `deploy.sh` on the host: `git pull` → `build` → `alembic upgrade head` → `up -d` → smoke-check. Rollback = `git checkout <prev tag> && ./deploy.sh`. Brief recreate blip is acceptable at beta scale. |
| D8 | Registration gate | New `INVITE_CODE` setting; the register endpoint rejects a mismatch. Empty = open (dev default). Beta value `5566`, set in the host `.env` (not committed). |
| D9 | Persistence | Named volumes for Postgres data, extracted media, and Redis AOF; nightly `pg_dump` shipped to **OSS** (Singapore bucket). |

**Non-goals (this slice):** CI/CD auto-deploy; multi-region / CDN front (Cloudflare can be added later); horizontal scaling; centralized log/metrics stack; mobile client. See §11.

## 3. Architecture / topology

```
                         Internet
                            │  80 / 443   (only ports open in the firewall)
                   ┌────────▼─────────┐
                   │  caddy           │  automatic HTTPS (Let's Encrypt)
                   └────────┬─────────┘
                            │ web:3000
                   ┌────────▼─────────┐
                   │  web (Next.js)   │  /api/* ── rewrite ──▶ api:8000
                   └────────┬─────────┘
         internal docker network (no host-published ports below)
   ┌───────────┬────────────┼────────────┬──────────────┐
   ▼           ▼            ▼            ▼              ▼
 api:8000    worker       db:5432      redis:6379     rsshub:1200
(uvicorn,   (arq,        (Postgres    (AOF on,        (no PROXY_URI —
 /health)    single)      17)          requirepass)    direct egress)
   │           │            │             │
   └───────────┴───▶ volumes: pgdata · media (api+worker) · redis-data
```

| Service | Process | Public? |
|---|---|---|
| `caddy` | reverse proxy + TLS | **yes** (80/443) |
| `web` | `next start` (standalone) | no (via Caddy) |
| `api` | `uvicorn app.main:app --host 0.0.0.0 --port 8000` (`/health`) | no |
| `worker` | `python -m app.tasks` (arq, **exactly one replica**) | no |
| `db` | Postgres 17 | no |
| `redis` | Redis 7, `--appendonly yes --requirepass <pw>` | no |
| `rsshub` | `diygod/rsshub` (feeds); **`PROXY_URI` dropped** in prod | no |

> **Worker singleton rule.** Exactly one `worker` replica, and never hand-start a second `python -m app.tasks` on the host — a stale/duplicate arq worker silently consumes jobs it can't handle (export/generate then 404 forever). This has bitten us before; the compose file pins one replica and the runbook repeats the warning.

## 4. Same-origin routing (why no code change is needed)

`packages/api-client/src/index.ts` already computes its base URL by environment:

```ts
export const baseUrl =
  typeof window === "undefined"
    ? process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    : "/api"; // browser: same-origin, proxied by the Next rewrite
```

- **Browser** always calls `/api/...` on its own origin → Caddy → `web` → Next rewrite (`/api/:path*` → `${API}/:path*`) → `api:8000`. First-party httpOnly cookie, HTTPS.
- **SSR** (Next server, and the rewrite target) uses `API_INTERNAL_URL` → `http://api:8000` on the internal network; `apps/web/lib/serverApi.ts` forwards the incoming request cookie.

Therefore prod only needs **`API_INTERNAL_URL=http://api:8000`** on the `web` container. `NEXT_PUBLIC_API_URL` is unused on the same-origin path and is dropped in prod. No routing code change — a divergence from the superseded Railway/Vercel spec, which relied on cross-origin CORS.

## 5. Build strategy

- **Python (api + worker)** — **one image**, build context = **repo root** (uv workspace needs `uv.lock`, root `pyproject.toml`, `services/*`). `uv sync --frozen --no-dev` installs the whole workspace and `uv` stays in the image. The two services are separated by the **compose command**, mirroring the proven `justfile` invocation so the colliding top-level `app` packages resolve correctly:
  - `api` → `working_dir /app`, command `uv run --no-sync --package gulp-api uvicorn app.main:app --host 0.0.0.0 --port 8000`.
  - `worker` → `working_dir /app/services/worker`, command `uv run --no-sync --package gulp-worker python -m app.tasks` (`python -m` needs the service dir as cwd).
  - migrations → one-off `uv run --no-sync --package gulp-api alembic upgrade head` with `working_dir /app/services/api` (where `alembic.ini` lives).
- **web** — Next.js Dockerfile, build context = repo root (pnpm + Turborepo workspace; deps `@gulp/api-client`, `@gulp/ui`, `@gulp/core` compile as part of the build). Requires **`output: "standalone"`** in `apps/web/next.config.ts` (§10) so the runtime image ships only the standalone server + static assets. **`API_INTERNAL_URL=http://api:8000` must be set at *build* time** — Next bakes the `/api/*` rewrite destination into the routes manifest during `next build` — and again at runtime (SSR api-client reads it then). It is an internal compose hostname, not a secret, so baking it is fine; the browser base stays the static `/api`.

## 6. Configuration & secrets

A root-owned, git-ignored **`.env` on the host**, injected via compose `env_file`. Values that differ from dev:

```bash
DATABASE_URL=postgresql+psycopg://gulp:<strong-pw>@db:5432/gulp   # full +psycopg DSN — no normalization needed
REDIS_URL=redis://:<redis-pw>@redis:6379/0
AUTH_SECRET=<openssl rand -hex 32>
CREDENTIAL_SECRET=<openssl rand -hex 32>   # encrypts BYOK keys — back up separately, off-host
SESSION_COOKIE_SECURE=true                 # HTTPS
ANTHROPIC_API_KEY=                          # empty — BYOK
WEB_ORIGIN=https://<domain>                 # drives CORS allow-list (belt-and-suspenders for same-origin)
API_INTERNAL_URL=http://api:8000            # web: SSR fetch base (runtime) + rewrite target (also baked at build, §5)
RSSHUB_BASE_URL=http://rsshub:1200
EXPORT_DIR=/data/exports                    # moved off /tmp onto a volume
MEDIA_DIR=/data/media                       # moved off /tmp onto a volume (else images 404 after restart)
INVITE_CODE=5566                            # beta registration gate (§8)
LOG_LEVEL=INFO
```

**Two keys, two different loss consequences:**

- **`CREDENTIAL_SECRET`** — losing/rotating it makes every stored BYOK provider key undecryptable (**irreversible**). Copy it into a password manager the moment it's generated.
- **`AUTH_SECRET`** — rotating it only invalidates active sessions (users re-login). Lower stakes.

Since we author `DATABASE_URL` ourselves with the `+psycopg` prefix, the DSN-normalization code change from the prior spec is **not required** here (harmless if already present).

## 7. Persistent state

| Volume | Mounted at | Loss impact |
|---|---|---|
| `pgdata` | `db:/var/lib/postgresql/data` | the entire knowledge graph — the crown jewel |
| `media` | **both** `api` and `worker` → `/data/media` | worker writes figures, api serves them; missing on either → 404s |
| `redis-data` | `redis` (AOF) | active sessions invalidated + queued jobs lost |
| `exports` | `/data/exports` (optional) | only transient zips; safe to leave ephemeral |

`media` must be mounted on **both** api and worker. Internal services publish **no host ports** (reachable only inside the Docker network).

## 8. Migrations, first-boot, registration gate

- **Migrations** run before serving: `docker compose run --rm api alembic upgrade head` (cwd = `services/api`, where `alembic.ini` lives), then start `api`/`worker`. The worker performs no migrations.
- **Seeded dev account** (`dev@example.com` / `gulp-dev-2026`) — created by migration seed. On first boot in prod, **delete it or change its password immediately** (runbook step, flagged).
- **Invite-code gate** (§10, code change): add `invite_code: str = ""` to `Settings`. The register endpoint (`services/api/app/routers/auth.py`) rejects a request whose submitted code ≠ `settings.invite_code` (e.g. `400 invite_required`) when the setting is non-empty; empty preserves today's open registration for dev/tests. The web sign-up form gains an invite-code field threaded through the register call; `just gen-client` regenerates the request type. Beta value `5566` lives only in the host `.env`.
  - *Note:* a 4-digit code only deters casual open sign-up, not a determined actor — acceptable for a private beta. Lengthen it later if the beta widens.

## 9. Deploy workflow (`deploy.sh` on the host)

```bash
set -euo pipefail
cd /opt/gulp
git pull                                                             # main, or a release tag
docker compose -f infra/compose.prod.yml build                       # web + 2 python images
docker compose -f infra/compose.prod.yml run --rm api alembic upgrade head
docker compose -f infra/compose.prod.yml up -d
docker image prune -f
curl -fsS https://<domain>/api/health                                # smoke check → {"status":"ok"}
```

- **Rollback:** images are built from the checkout, so `git checkout <prev tag> && ./deploy.sh` restores the last-known-good. Tag releases so a rollback target always exists.
- **No zero-downtime requirement** at beta scale; the `up -d` recreate blip (seconds) is acceptable. Migrations should stay backward-compatible where practical.

## 10. Code changes (the only three)

1. **`apps/web/next.config.ts`** — add `output: "standalone"` for a slim runtime image (§5).
2. **Invite-code gate** — `Settings.invite_code` + register-endpoint check + web sign-up field + `gen-client` (§8).
3. **Prod infra files** (new, under `infra/`): `compose.prod.yml`, the Python `Dockerfile`, the web `Dockerfile`, `Caddyfile`, `deploy.sh`, `backup.sh`, `env.prod.example`, `.dockerignore`, `README.md` (operator runbook). Config-as-code, committed.

Everything else is host setup and configuration. No change to `DATABASE_URL` handling or the routing layer.

## 11. Backups, monitoring, hardening

**Backups (the knowledge graph is the crown jewel):**

- Nightly host cron: `docker compose exec -T db pg_dump -U gulp gulp | gzip > gulp-<date>.sql.gz`, upload to **OSS** (Singapore, same-region bucket), rotate/retain N days.
- Also back up: the host `.env` (especially `CREDENTIAL_SECRET`) and `/data/media`.
- **Run one restore drill** — an unverified backup is not a backup.

**Monitoring (kept light for beta):**

- Every container `restart: unless-stopped` + compose healthchecks (db `pg_isready`, api `/health`, redis `redis-cli ping`).
- External uptime probe (UptimeRobot or Alibaba Cloud site monitor) on `https://<domain>/api/health` → alert on failure.
- Logs via `docker compose logs` (structured, request-id tagged already); centralization deferred.

**Hardening:**

- Simple Application Server firewall opens **only 22 / 80 / 443**; pg/redis/rsshub/api are internal-only.
- SSH key auth, root password login disabled.
- Redis `--requirepass` even on the internal network.
- Docker `json-file` log rotation (`max-size`) so logs can't fill the disk.
- OS automatic security updates.

## 12. Rollout checklist (ordered)

```
0. Provision:   buy domain · create Simple App Server (Singapore, 2C8G) · install Docker + compose · open 22/80/443
1. Code PR:     ① next standalone  ② invite-code gate  ③ infra/ (compose.prod + 2 Dockerfiles + Caddyfile + deploy.sh) — verify locally
2. DNS:         A record → server public IP; wait for propagation
3. Host:        clone repo to /opt/gulp · write .env (strong pw · 2 random secrets · INVITE_CODE=5566 · SECURE=true · domain)
4. First run:   ./deploy.sh  (build → migrate → up)
5. TLS:         Caddy auto-issues the cert; verify https://<domain> loads and /api/health = ok
6. Smoke:       register with 5566 → Forward one item → watch pack generate (worker OK) → add BYOK key → run one Gulp session
7. Wrap-up:     delete/rotate the seeded dev account · enable nightly pg_dump→OSS · attach uptime probe
8. Invite:      share code 5566, onboard beta users
```

## 13. Verification / smoke test

After first deploy:

1. `GET https://<domain>/api/health` → `{"status":"ok"}`.
2. Browser Network tab: XHRs hit `https://<domain>/api/...` and return 200 (confirms the same-origin rewrite + first-party cookie).
3. Register with the invite code; a wrong/absent code is rejected.
4. Forward a capture → `worker` picks up the arq job (worker logs) → snapshot advances to a ready pack with any figures rendering (proves Redis wiring + always-on worker + media volume).
5. Add a BYOK key, run one Gulp session end-to-end.
6. Restart the stack; confirm sessions/media/data survive (proves volume + AOF wiring).

## 14. Out of scope / future

- **CI/CD auto-deploy** (build → push to ACR/GHCR → pull on host, gated on green CI).
- **CDN / edge front** (Cloudflare) for faster domestic access.
- **Horizontal scale / managed Postgres+Redis** (the scale-up target, not the start).
- **Centralized logs/metrics** (Loki / Alibaba Cloud Log Service).
- **Mobile client** (deferred per `docs/04 §5`).
- **Stronger registration** (longer codes, email allowlist, or real onboarding) if the beta widens.
