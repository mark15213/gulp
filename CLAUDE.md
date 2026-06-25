# Gulp — repo guide for Claude

Personal learning system: forward anything → AI knowledge pack → daily "Gulp mode" practice → tracked mastery.
**Product specs live in `docs/` (00–05). This file is *how to work the repo*, not what the product is — read `docs/` for the what/why.**

> **Current focus: web-first.** Build `apps/web`. `apps/mobile` is deferred (`docs/04 §5`) — don't build mobile features yet; it stays a reserved placeholder until the web client is established.

## Layout (see `docs/05-repo-structure.md` for the full rationale)

- `apps/web` — Next.js web client (TypeScript)
- `apps/mobile` — Expo / React Native mobile client (TypeScript)
- `services/api` — FastAPI HTTP API (Python) — conventional layering
- `services/worker` — async AI pipeline + background jobs (Python)
- `services/shared` — Python shared layer: ORM models, db, settings, domain (api + worker depend on it)
- `packages/api-client` — TS client generated from the API's OpenAPI = the data-model contract
- `packages/ui` — shared design system (implements `docs/03`)
- `packages/core` — shared framework-free TS logic
- `packages/config` — shared tsconfig / eslint / prettier presets

## Commands — use the `justfile`, don't improvise

- `just setup` — install everything (pnpm + uv)
- `just up` / `just down` — local infra (Postgres, Redis)
- `just dev` — run the web-first stack: web + api + worker (mobile via `just mobile`)
- `just lint` / `just test` / `just format` — quality gates (both languages)
- `just gen-client` — regenerate `packages/api-client` from the API's OpenAPI
- `just migrate "msg"` / `just migrate-up` — Alembic migrations

## Rules

1. **Two languages, one command surface.** TS via pnpm + Turborepo; Python via uv. Never reach for the underlying tool when a `just` recipe exists.
2. **The data model is the contract** (`docs/04 §2.5`). Python (`services/shared`) is the source of truth; the TS clients consume the generated `packages/api-client`. Don't hand-write types that duplicate it.
3. **Conventional layering in the API** — routers stay thin, business logic lives in `services/api/app/services`, persistence in `services/shared`.
4. **Capture never blocks on AI** (`docs/04 §4 S1`). Heavy work goes to `services/worker` via the queue, not into a request handler.
5. **Build incrementally** (`docs/04 §5`). The skeleton is fully laid out, but only the current subsystem's slice is filled — empty dirs are intentional placeholders.
6. **Write in English.** All design docs, code comments, commit messages, and LLM prompts are written in English. Product UI copy is exempt — the app is bilingual (`locale ∈ {zh·en}`).
7. Subproject-specific conventions live in nested `CLAUDE.md` files (`apps/*`, `services/*`).
