# User System (S0 real sign-in) — design

**Date:** 2026-07-10
**Status:** approved for planning
**Subsystem:** `S0 · Foundation` — "account & auth" (`docs/04 §S0`, `docs/02 §4.1`, `docs/01 §F8`)

## 1. Problem & goal

Gulp's data model is already multi-tenant-shaped — a real `User` model exists and the aggregate roots (`Source`, `GulpSession`, `ReviewEvent`) carry `owner_id → users.id`, with everything else scoping transitively through `Source`. But there is **no real authentication**: `services/api/app/core/auth.py::get_current_user` is a stub (spec C6) that always returns one hardcoded seeded user (`DEV_USER_ID`), and the web client sends nothing identifying. Its own docstring says *"Swap for real sign-in (S0)."*

**Goal:** implement S0's real sign-in — replace the dev-user stub with genuine accounts so that anyone can register, log in, and see only their own data. The per-user isolation is already wired; this work supplies identity, credentials, sessions, and the web sign-in surface.

## 2. Decisions (locked during brainstorming)

| # | Decision | Choice |
|---|---|---|
| D1 | Tenancy | **Open multi-tenant** — public self-service registration; each user's data fully isolated. |
| D2 | Auth method | **Email + password, self-managed** (no external identity provider). argon2id hashing. |
| D3 | Recovery scope for v1 | **Auth core now; recovery later.** Ship register / login / logout / session / route-protection. **Defer** email verification and password reset (no outbound email infra exists yet). |
| D4 | Session architecture | **Opaque server-side session token in an httpOnly cookie**, Redis-backed (already in the stack). Web reaches the API **same-origin via a Next.js rewrite** so the cookie is first-party. Revocable + XSS-safe. |
| D5 | Concept-graph ownership | Add `owner_id` to the two currently user-less tables (`concepts`, `concept_edges`) now, while they are empty (S3 unbuilt), to keep the isolation invariant uniform. |
| D6 | Existing data | The seeded **dev user becomes a real account** (`dev@gulp.local` + a documented dev password). All existing local data (snapshots, cards, packs) stays owned by it — the owner logs in as `dev@gulp.local` to retain it. Production starts empty. |

**Non-goals (deferred):** email verification, password reset / forgot-password, social OAuth, magic links, "active sessions" management UI, team/sharing (`docs/01 §11`), the mobile client (web-first, `docs/04 §5`).

## 3. Data model changes (`services/shared/gulp_shared`)

### 3.1 `User` gains identity/credentials (`models/user.py`)
- `email: str` — stored **lowercased**, `unique=True`, indexed, `NOT NULL`.
- `password_hash: str` — argon2id hash, `NOT NULL`.
- Unchanged: `display_name`, `locale`, `gulp_session_minutes`. `DEV_USER_ID` constant stays (now a real, credentialed account).

### 3.2 Concept graph gets an owner
- Add `owner_id: uuid → users.id` (indexed, `NOT NULL`) to `Concept` and `ConceptEdge` (`models/concept.py`).
- Join tables `card_concepts` and `source_concepts` remain owner-less: they scope transitively through their `card_id`/`source_id` (which scope through `owner`). No change to them.

### 3.3 Public user shape
A `UserPublic` projection (id, email, display_name, locale, gulp_session_minutes, timestamps) is the only user shape ever returned over the wire. **`password_hash` is never serialized.**

## 4. Migration (Alembic, `services/api/alembic`)

Single revision, `down_revision` = current head (`033e0b57ef69`, `reader_chat_pack_messages`):

1. **users:** add `email` and `password_hash` as **nullable** → backfill the existing `DEV_USER_ID` row (`email='dev@gulp.local'`, `password_hash=<argon2id of a documented dev password>`) → `ALTER COLUMN ... SET NOT NULL` → add unique index on `email`.
2. **concepts / concept_edges:** add `owner_id` (`NOT NULL`, FK → `users.id`, indexed). Tables are empty (S3 unbuilt), so no backfill is needed; if any rows exist locally, backfill to `DEV_USER_ID` before `SET NOT NULL`.
3. `downgrade()` drops the columns/indexes in reverse.

The dev password is documented in `.env.example` / a dev README note so local login works immediately after `just migrate-up`.

## 5. API (`services/api/app`)

### 5.1 New endpoints — `routers/auth.py` (thin, per `docs/05 D4`)
| Method | Path | Auth | Body | Returns |
|---|---|---|---|---|
| POST | `/auth/register` | none | `{email, password, display_name?, locale?}` | `201` `UserPublic` + `Set-Cookie` |
| POST | `/auth/login` | none | `{email, password}` | `200` `UserPublic` + `Set-Cookie` |
| POST | `/auth/logout` | session | — | `204`, cookie cleared |
| GET | `/auth/me` | session | — | `200` `UserPublic` |

### 5.2 New modules
- `schemas/auth.py` — `RegisterRequest`, `LoginRequest`, `UserPublic` (Pydantic; becomes OpenAPI → run `just gen-client`).
- `services/auth.py` — business logic: register (validate, uniqueness, hash, create user, open session), authenticate (verify), logout (revoke).
- `core/security.py` — `hash_password` / `verify_password` (argon2id via `argon2-cffi`); `new_session_token()` = `secrets.token_urlsafe(32)`.
- `core/sessions.py` — Redis-backed session store:
  - `create(user_id) -> token` — writes `session:<token> -> user_id` with TTL; adds token to per-user set `user_sessions:<user_id>`.
  - `resolve(token) -> user_id | None` — reads + **slides** the TTL on hit.
  - `revoke(token)` and `revoke_all(user_id)` (logout-everywhere via the per-user set).
  - Redis-only (no DB session table) — losing Redis just forces re-login; a DB-backed store is a trivial future add if an "active sessions" UI is ever wanted.

### 5.3 The single swap point — `core/auth.py`
Rewrite `get_current_user`: read the session cookie → `sessions.resolve(token)` → `db.get(User, user_id)` → return; on missing/invalid/expired session raise `401`. **Every router already depends on `get_current_user`, so this one edit protects the entire API.** The register/login endpoints must NOT depend on it (open); logout/me use it.

### 5.4 Cookie & CORS
- Cookie: `httpOnly`, `SameSite=Lax`, `Secure` in prod (from settings), `Path=/`, `Max-Age` = session TTL, name from settings (`gulp_session`).
- Same-origin via the Next rewrite (§6) means `SameSite=Lax` suffices and CORS/`allow_credentials` cross-origin friction is avoided in both dev (`:3000`↔`:8000`) and prod (Vercel↔Railway, per `2026-07-07-deployment-railway-vercel-design.md`).

### 5.5 Errors & abuse
- `401` — no/invalid/expired session; bad login credentials (generic *"invalid email or password"*, no user enumeration).
- `409` — register with an already-registered email.
- `400` — malformed email or password shorter than the minimum (8).
- **Light login throttle:** a Redis per-`email`+IP failure counter locks further attempts for a short window after N failures. Cheap, and warranted because signup is open.

## 6. Web client (`apps/web` + `packages/api-client`)

- **Next.js rewrite** (`apps/web/next.config.*`): `/api/:path*` → `${API_URL}/:path*`. This makes the browser talk to the API same-origin (first-party cookie) and also resolves prod cross-origin (Vercel web ↔ Railway API).
- **api-client** (`packages/api-client/src/index.ts`): `baseUrl = "/api"`; set `credentials: 'include'` on the openapi-fetch client so the session cookie rides every request. Regenerate types after the schema change.
- **Pages:** `/login` and `/register` (bilingual zh/en copy per `docs` rule 6) — email + password forms; on success redirect into the app shell.
- **Route protection:**
  - `apps/web/middleware.ts` — gate app navigation on **presence** of the session cookie; redirect unauthenticated navigations to `/login`. (Real validation stays server-side — middleware only gates the shell.)
  - **Auth context/provider** — bootstrap the current user via `GET /auth/me` on load; a global `401` handler in the api-client layer redirects to `/login` (covers expired/revoked sessions mid-session).
- **Logout** control in the shell sidebar → `POST /auth/logout` → redirect to `/login`. Show `display_name`/`email` in the shell.

## 7. Ownership enforcement audit

Multi-user is no longer hypothetical, so before shipping, sweep every service to confirm each read/write is scoped to `user.id` and no by-id fetch leaks cross-user data. The existing pattern (`_owned_snapshot` raising `404` on `owner_id` mismatch) is the model; verify library / capture / cards / pack / feeds / today / inbox / gulp / export services all follow it. The concept-graph services (when S3 lands) must filter by the new `owner_id`.

## 8. Config (`services/shared/gulp_shared/settings.py`)
Add: `session_ttl_days: int = 30`, `session_cookie_name: str = "gulp_session"`, `session_cookie_secure: bool = False` (True in prod), login-throttle knobs (`login_max_attempts`, `login_lockout_seconds`). `auth_secret`/`AUTH_SECRET` already scaffolded (kept for future signed-token / CSRF needs; opaque tokens don't require it).

## 9. Testing
Per-package (`cd services/api && uv run pytest`; `cd services/shared && uv run pytest`):
- **shared:** `User.email` uniqueness + lowercasing; concept `owner_id` present.
- **api:** register (success / duplicate-email `409` / weak-password `400`); login (success / bad creds `401`, generic message); logout revokes session; `/auth/me`; unauthenticated protected request → `401`; session expiry / sliding TTL; **cross-user isolation** — user A cannot read user B's `Source` (→ `404`/`401`); password hash round-trip; session store create/resolve/revoke/revoke_all; login throttle locks after N failures.
- **web** (vitest, classic JSX transform — `import React` in JSX files per repo convention): login/register form + auth-context render/redirect behavior.
- **migration:** `just migrate-up` succeeds and `dev@gulp.local` logs in with existing data intact.
- Keep `just lint` green (ruff/mypy/eslint) and add the new `argon2-cffi` dependency to `services/api` (and `services/shared` if hashing utilities land there).

## 10. Rollout order (feeds the implementation plan)
1. shared model + concept `owner_id` + migration + dev-user backfill.
2. `core/security.py` + `core/sessions.py` + settings.
3. `schemas/auth.py` + `services/auth.py` + `routers/auth.py`; rewrite `core/auth.py`; wire router in `main.py`; `just gen-client`.
4. Ownership audit sweep.
5. web: Next rewrite + api-client `credentials` + auth pages + middleware + auth context + logout.
6. tests across the vertical slice; `just lint` / `just test` green; verify `just migrate-up` + dev login.
