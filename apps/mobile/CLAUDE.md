# apps/mobile — Expo / React Native client

Mobile surface for Gulp (the China-first capture wedge, `docs/00`). Expo Router. Implements the mobile side of `docs/01` (tab bar, batch-confirm) and `docs/03`.

## Conventions

- Routes in `app/` (Expo Router); components in `components/`; data/state in `lib/`.
- Backend access **only** through `@gulp/api-client`.
- Visual primitives from `@gulp/ui` — keep parity with web, don't fork the design system.
- Extends shared config from `@gulp/config`.

## Commands

- `just mobile` (or `pnpm --filter @gulp/mobile start`) — Expo dev server
