# Gulp — repo guide for Claude

Personal learning system: forward anything → AI knowledge pack → daily "Gulp mode" practice → tracked mastery.
**Product specs live in `docs/` (00–05). This file is *how to work the repo*, not what the product is — read `docs/` for the what/why.**

> **Current focus: web is built; the iOS client is designed, not started.** `apps/ios` is a native SwiftUI client scoped to the consumption end — read [`docs/superpowers/specs/2026-07-25-ios-client-design.md`](docs/superpowers/specs/2026-07-25-ios-client-design.md) before touching it. The Expo placeholder that used to sit at `apps/mobile` is gone; Android is out of scope.

## Layout (see `docs/05-repo-structure.md` for the full rationale)

- `apps/web` — Next.js web client (TypeScript)
- `apps/ios` — native SwiftUI client (Swift) — the consumption end: forward · Today · Gulp session · read
- `services/api` — FastAPI HTTP API (Python) — conventional layering
- `services/worker` — async AI pipeline + background jobs (Python)
- `services/shared` — Python shared layer: ORM models, db, settings, domain (api + worker depend on it)
- `packages/api-client` — TS client generated from the API's OpenAPI = the data-model contract
- `packages/ui` — design tokens + web primitives (`docs/03`); iOS transcribes the tokens into Swift
- `packages/core` — shared framework-free TS logic
- `packages/config` — shared tsconfig / eslint / prettier presets
- `integrations/` — per-agent client configs for the MCP job channel (CC skill; Codex later)

## Commands — use the `justfile`, don't improvise

- `just setup` — install everything (pnpm + uv)
- `just up` / `just down` — local infra (Postgres, Redis)
- `just dev` — run the stack: web + api + worker (`just ios` opens the Xcode project)
- `just lint` / `just test` / `just format` — quality gates (TS + Python; Swift runs via `just ios-test`)
- `just gen-client` — regenerate **both** clients (TS + Swift) from the API's OpenAPI
- `just migrate "msg"` / `just migrate-up` — Alembic migrations

## Rules

1. **Three languages, one command surface.** TS via pnpm + Turborepo; Python via uv; Swift via Xcode / SwiftPM. Never reach for the underlying tool when a `just` recipe exists — `just ios`, `just ios-test` and `just gen-client-swift` exist so Swift is no exception.
2. **The data model is the contract** (`docs/04 §2.5`). Python (`services/shared`) is the source of truth; TS consumes the generated `packages/api-client` and Swift the generated `apps/ios/Packages/GulpAPI`, both from one `openapi.json`. `just gen-client` refreshes them together. Don't hand-write types that duplicate it.
3. **Conventional layering in the API** — routers stay thin, business logic lives in `services/api/app/services`, persistence in `services/shared`.
4. **Capture never blocks on AI** (`docs/04 §4 S1`). Heavy work goes to `services/worker` via the queue, not into a request handler.
5. **Build incrementally** (`docs/04 §5`). The skeleton is fully laid out, but only the current subsystem's slice is filled — empty dirs are intentional placeholders.
6. **Write in English.** All design docs, code comments, commit messages, and LLM prompts are written in English. Product UI copy is exempt — the app is bilingual (`locale ∈ {zh·en}`).
7. Subproject-specific conventions live in nested `CLAUDE.md` files (`apps/*`, `services/*`).
