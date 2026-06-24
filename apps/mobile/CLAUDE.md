# apps/mobile — Expo / React Native client

> **DEFERRED — web-first.** Don't build mobile features yet. `apps/mobile` is a reserved placeholder until the web client is established (`docs/04 §5`). When mobile work begins, scaffold the real Expo app here.

Mobile surface for Gulp (the China-first capture wedge, `docs/00`). Expo Router. Implements the mobile side of `docs/01` (tab bar, batch-confirm) and `docs/03`.

## Conventions

- Routes in `app/` (Expo Router); components in `components/`; data/state in `lib/`.
- Backend access **only** through `@gulp/api-client`.
- Visual primitives from `@gulp/ui` — keep parity with web, don't fork the design system.
- Extends shared config from `@gulp/config`.

## Commands

- `just mobile` (or `pnpm --filter @gulp/mobile start`) — Expo dev server
