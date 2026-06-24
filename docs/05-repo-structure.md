# 05 — Repository Structure

*Gulp · monorepo layout & development conventions · v1 · 2026-06-24*

> Companion to [`00-product-one-pager.md`](00-product-one-pager.md) (the *what/why*), [`01-interaction-spec.md`](01-interaction-spec.md) (the *how the user moves*), [`02-data-model.md`](02-data-model.md) (the *objects it's made of*), [`03-ui-system.md`](03-ui-system.md) (the *how it looks*), and especially [`04-development-plan.md`](04-development-plan.md) (the *how we build it*). Doc `04` cuts the system into subsystems `S0`–`S8`; **this doc lays out the physical repository those subsystems are built in** — where code lives, how packages and environments are managed, and how every contributor (human or AI) picks up the conventions on day one.
>
> **Altitude:** physical repository layout + toolchain + conventions. It does exactly three things — **① define the directory tree · ② fix package management and reproducible environments · ③ make the development conventions discoverable and enforced.** It deliberately stops *above* per-subsystem internals (those live in `docs/subsystems/SN-*.md`, per `04 §6`).

---

## 1. Locked decisions

The structure hangs off these. They are settled; the rest of the doc is their consequence.

| # | Decision | Choice |
|---|---|---|
| D1 | Repository topology | **Single polyglot monorepo** — TS and Python in one tree |
| D2 | Frontend stack | **TypeScript** — Web (Next.js) + Mobile (Expo / React Native), sharing TS packages |
| D3 | Backend stack | **Python** — FastAPI API + a Python async worker for the AI pipeline |
| D4 | Backend code organization | **Conventional layering** (router / service / model / schema) — *not* mirrored to `S0`–`S8` |
| D5 | TS package management | **pnpm workspaces + Turborepo** |
| D6 | Python package management | **uv** (workspace, single lockfile) — replaces pip / poetry / pyenv / virtualenv |
| D7 | Unified command entry | **`justfile`** at the repo root — one command set, delegating to pnpm and uv |
| D8 | Convention discovery | **Layered `CLAUDE.md`** + machine enforcement (shared lint/format config, pre-commit, CI) |

---

## 2. Top-level layout

```
gulp/
├── apps/                      # End-user applications (TypeScript)
│   ├── web/                   # Next.js (App Router) — web client
│   └── mobile/                # Expo / React Native — mobile client
│
├── services/                  # Server-side (Python)
│   ├── api/                   # FastAPI — HTTP API (conventional layering)
│   ├── worker/                # Async processing engine — the AI pipeline + background jobs
│   └── shared/                # Python shared layer — ORM models, db, settings, domain (api + worker both depend on it)
│
├── packages/                  # Shared across clients (TypeScript)
│   ├── api-client/            # Typed client generated from the API's OpenAPI = the data-model contract
│   ├── ui/                    # Shared design system (implements docs/03)
│   ├── core/                  # Shared pure logic (mastery-state views, dates, formatting…)
│   └── config/                # Shared tsconfig / eslint / prettier presets
│
├── docs/                      # Product & engineering specs (00–05) + subsystems/ design docs
├── design/                    # Design assets (HTML previews, design philosophy, fonts)
├── infra/                     # docker-compose, IaC, deployment manifests
├── scripts/                   # Repo-wide dev / build scripts
├── .github/workflows/         # CI
├── .claude/                   # Claude Code project settings, hooks, commands
│
├── CLAUDE.md                  # AI entry point: repo map + just commands + global rules
├── justfile                   # Unified command entry for humans and AI
├── pnpm-workspace.yaml        # pnpm workspace definition
├── pnpm-lock.yaml             # TS lockfile (committed)
├── pyproject.toml             # uv workspace root
├── uv.lock                    # Python lockfile (committed)
├── ruff.toml                  # Python lint/format config (or folded into pyproject.toml)
├── .pre-commit-config.yaml    # Commit-time lint/format hooks (JS + Python)
├── .nvmrc                     # Pinned Node version
├── .python-version            # Pinned Python version
├── .env.example               # Env template (real .env is gitignored)
└── README.md
```

**Why this cut.** `apps` (who uses it) / `services` (who computes it) / `packages` (what's shared) is the standard partition for a mixed TS+Python monorepo. TS is managed as a pnpm + Turborepo workspace; the three Python services form a uv workspace; a root `justfile` covers both so there is one command surface, not two.

---

## 3. Frontend — `apps/` + `packages/`

```
apps/web/
├── app/                       # Next.js App Router routes
├── components/                # Page-level components
├── lib/                       # api-client calls, client state
└── package.json

apps/mobile/
├── app/                       # Expo Router
├── components/
├── lib/
└── package.json

packages/ui/                   # Design-system primitives shared by web + mobile (color, type, components)
packages/api-client/           # Single contract surface: types + request methods, generated from the API's OpenAPI
packages/core/                 # Framework-free shared logic (e.g. derived mastery views, formatting)
packages/config/               # Shared eslint / prettier / tsconfig presets the apps extend
```

Web and Mobile share the design language through `packages/ui` and share the backend contract through `packages/api-client` — neither client hand-writes its own copy of the types or the design tokens.

---

## 4. Backend — `services/` (conventional layering)

```
services/shared/               # Python shared layer — the contract on the server side
├── gulp_shared/
│   ├── models/                # ORM entities = the docs/02 objects (Source · Snapshot · KnowledgePack · Card · Concept · Conversation · …)
│   ├── db/                    # ORM base, session, engine
│   ├── settings.py            # pydantic-settings — config loaded from env
│   └── domain/                # cross-service domain logic / value types
├── tests/
└── pyproject.toml

services/api/                  # FastAPI — request/response, no heavy work
├── app/
│   ├── main.py                # FastAPI entry
│   ├── core/                  # auth, dependency wiring (the server side of S0 Foundation)
│   ├── schemas/               # Pydantic request/response models
│   ├── routers/               # HTTP endpoints, grouped by resource
│   ├── services/              # business logic (orchestrates shared models)
│   └── deps.py
├── alembic/                   # database migrations
├── tests/
└── pyproject.toml

services/worker/               # The S2 processing engine: capture never blocks, heavy work runs here
├── app/
│   ├── pipeline/              # fetch → parse → chunk → generate pack → draft cards → link concepts
│   ├── prompts/               # LLM prompt templates
│   ├── llm/                   # model / provider clients
│   ├── tasks/                 # job definitions (arq / celery)
│   └── eval/                  # card-quality eval harness (an open question from the S2 charter)
├── tests/
└── pyproject.toml
```

**Why `shared` is extracted.** Both `api` and `worker` read and write the same entities (the `02` objects). Per `04 §2.5` the data model is the shared contract, so the ORM models, DB session, and settings live once in `services/shared` and both services depend on it through the uv workspace — they do not each carry a copy. This is layer extraction, not subsystem mirroring; D4 still holds.

**Why `api` and `worker` are separate services.** `04 §4 (S1)` requires capture to confirm instantly and *never* wait on AI. Splitting the responsive HTTP API from a queue-fed worker that runs the `S2` pipeline is the standard way to honor that — the API enqueues a job and returns; the worker digests asynchronously.

**The cross-language contract flow.** Python is the source of truth for the persisted schema. The flow is:

```
services/shared (Pydantic / ORM)  →  services/api emits OpenAPI  →  generate  →  packages/api-client (TS types + methods)
```

So "the data model is the shared contract" (`04 §2.5`) holds across the language boundary: the Python side defines it, the TS clients follow automatically, and Web/Mobile always consume the same generated types.

---

## 5. Package management & reproducible environments

Two toolchains, each best-in-class for its language, capped by one command entry. The rule: **never make one tool manage both languages — unify at the command layer instead.**

### 5.1 TypeScript — pnpm + Turborepo

- `pnpm` workspaces (strict, fast, disk-efficient; the workspace protocol fits a monorepo).
- `Turborepo` orchestrates and caches `build` / `test` / `lint` incrementally.
- Versions pinned: root `package.json` sets `"packageManager": "pnpm@9.x"` with Corepack; `.nvmrc` pins Node. `pnpm-lock.yaml` is committed.

### 5.2 Python — uv

- `uv` handles dependencies, virtualenvs, the interpreter, and the lockfile in one fast tool.
- A **uv workspace**: the root `pyproject.toml` declares members `services/api`, `services/worker`, `services/shared`; they share one `uv.lock`.
- `.python-version` pins the interpreter (uv installs/selects it). `uv sync` recreates `.venv` exactly; `uv run <cmd>` executes inside it — no manual activation.
- Config and secrets: `.env.example` is committed as the template; the real `.env` is gitignored; `services/shared/settings.py` (pydantic-settings) reads it.

### 5.3 Unified entry — root `justfile`

Turborepo is TS-centric and cannot manage Python dependencies, so a root `justfile` is the single surface humans and AI use; it delegates underneath.

```just
setup:  corepack enable && pnpm install && uv sync     # bring the whole repo up
up:     docker compose -f infra/docker-compose.yml up -d   # Postgres, Redis queue
dev:    # run web / mobile / api / worker in parallel
test:   pnpm turbo run test && uv run pytest
lint:   pnpm turbo run lint && uv run ruff check . && uv run mypy .
```

> Net effect: a fresh machine or a fresh session gets running with `just setup && just up && just dev`. "How do I run this?" is answered by the `justfile`, not guesswork.

---

## 6. Development conventions & session onboarding

Conventions must be both **seen** by the AI and **enforced** by machines — documentation alone drifts.

### 6.1 Seen — layered `CLAUDE.md`

Claude Code auto-loads `CLAUDE.md` at session start and loads the nearest one as work moves into a subtree.

- Root `CLAUDE.md`: repo map + the `just` commands + global rules (language split, layering, contract flow, commit conventions). It **points to `docs/`, never copies it.** Short and imperative.
- Per-subproject `CLAUDE.md`, loaded on demand as the AI works there:
  - `apps/web/CLAUDE.md`, `apps/mobile/CLAUDE.md` — component / state / `api-client` conventions.
  - `services/api/CLAUDE.md` — layer responsibilities (routers stay thin, business logic lives in the service layer), how migrations are generated.
  - `services/worker/CLAUDE.md` — pipeline stages, where prompts live, how the eval harness runs.
- Principle: `CLAUDE.md` says *how / where / which command*; product specs stay in `docs/`. No duplication, no drift.

### 6.2 Enforced — shared config + pre-commit + CI

Conventions become machine-checkable, so a run tells you whether code conforms:

- TS: `packages/config` exports shared `eslint` / `prettier` / `tsconfig` presets that every app extends.
- Python: root `pyproject.toml` (or `ruff.toml`) configures `ruff` (lint + format) and `mypy`, one set repo-wide.
- Root `.pre-commit-config.yaml`: runs ruff / prettier / eslint / mypy before each commit, covering both languages from one config.
- `.github/workflows/ci.yml`: runs `just lint && just test` to gate PRs.
- Optional: `.claude/settings.json` hooks (auto-format after edits) and `.claude/commands/` for repeatable workflows. The repo already has a `.claude/` directory to host these.

> Together: **`CLAUDE.md` = "the conventions are here," linters + CI = "the conventions are enforced," shared config = "the conventions are defined once."** All three point at the same rules, so a new session both reads them and runs against them.

---

## 7. Incremental scaffolding

The full skeleton above is stood up once, but only the parts a current subsystem needs are filled — matching the just-in-time principle of `04 §2.4` and the build order of `04 §5`.

- **Now (`S0` Foundation):** root tooling (`justfile`, pnpm + uv workspaces, lint/format/CI, root + subproject `CLAUDE.md`); `services/shared` (db, settings) + `services/api/core` (auth); empty navigable shells in `apps/web` and `apps/mobile`; `packages/api-client`, `packages/config`, `packages/ui` seeded.
- **Later, per subsystem:** `services/worker/pipeline` (with `S2`), each resource `router` and `service` (with the subsystem that owns it), `infra` topology as deployment needs grow. Empty directories hold the slot until then.

The skeleton declares the *intended* shape so neighbors agree on boundaries (`04 §6`); the fill follows the dependency-ordered build plan, not all at once.

---

*Next: scaffold `S0` against this layout, then the per-subsystem design docs (`docs/subsystems/SN-*.md`) detail each service's internals as it comes online (`04 §5–6`).*
