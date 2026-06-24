# apps/web — Next.js web client

Web surface for Gulp. App Router. Implements the web side of `docs/01` (sidebar nav, deep curation) and `docs/03`.

## Conventions

- Routes in `app/`; page-level components in `components/`; data/state in `lib/`.
- Talk to the backend **only** through `@gulp/api-client` — never hand-write fetch types.
- Visual primitives come from `@gulp/ui`; don't redefine tokens or base components locally.
- Extends shared config: `tsconfig` from `@gulp/config/tsconfig.base.json`, eslint/prettier likewise.

## Commands

- `just web` (or `pnpm --filter @gulp/web dev`) — dev server
- Web and mobile share the design language via `@gulp/ui`; keep parity, don't fork components.
