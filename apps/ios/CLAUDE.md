# apps/ios — native SwiftUI client

> **Designed, not started.** Read [`docs/superpowers/specs/2026-07-25-ios-client-design.md`](../../docs/superpowers/specs/2026-07-25-ios-client-design.md) before writing anything here — it is the visual and behavioural contract. The build order is [`docs/superpowers/plans/2026-07-25-ios-client.md`](../../docs/superpowers/plans/2026-07-25-ios-client.md).

The **consumption end** (`docs/01 §3`): forward from anywhere, run the daily Gulp session, read what came back, find something again. Deep curation, tag management, feeds and AI settings stay on web — if a feature would need a second panel to explain, it belongs on web.

## Layout

- `Gulp/` — app target. One folder per screen (`Today/`, `Session/`, `Library/`, `You/`, `Reader/`), plus `App/` and `Net/`.
- `Shared/` — compiled into **both** the app and the extension: `DesignSystem/`, `Net/`, `Forward/`. Anything both targets need lives here; nothing else does.
- `GulpShare/` — share-extension target. Same App Group as the app, which is how it inherits the login.
- `GulpTests/` / `GulpUITests/` — unit and UI tests.
- `Packages/GulpAPI/` — the generated Swift client. **Generated, committed, never hand-edited.**

## Conventions

- **Backend access only through `GulpAPI`.** It is generated from the same `openapi.json` as `packages/api-client` (repo rule 2). Never hand-write a request or response type. Regenerate with `just gen-client`, which refreshes TS and Swift together.
- **Tokens come from `DesignSystem/Tokens.swift`**, transcribed once from the mobile column of `docs/03 §3.2`. Never pick a colour, radius or spacing value at a call site.
- **Ink is the primary action; blue means `Due` and nothing else.** If you are reaching for blue and it is not a due count, it is the wrong colour (`spec §5.2`).
- **Two type families.** Inter for words, Geist Mono for every number, count, interval and uppercase label — always `.monospacedDigit()`. There is no serif (`spec §5.1`).
- **One tick, one card.** `TickMarks` is a single view used by Today's gauge, the session rail and Library's due column. Do not re-draw it per screen — the mark meaning the same thing everywhere is the point.
- **Views don't fetch.** Screens observe an `@Observable` model; network work lives in the model, never in `body`.
- iOS 17 minimum. English-only UI copy in v1 (`docs/03 §10`).

## Commands

- `just ios` — open the Xcode project
- `just ios-test` — unit tests, no server needed
- `just ios-test-live` — adds the suites that sign in against a running `just dev`
- `just ios-uitest` — drives the real app: taps, sessions, forwarding. Needs `just dev`. **It writes** — one review (graded `Missed`) and one capture per run.
- `just gen-client` — regenerate both clients from the API schema

## Testing

Anything reachable only by tapping goes in `GulpUITests`, not in a comment saying it was checked by hand. XCUITest runs inside the simulator through iOS's accessibility layer, so it needs no macOS Accessibility permission and works headless — there is no excuse for an untested tap.

Two traps that cost a cycle each, both invisible until something reads the accessibility tree:

- **Uppercase labels.** `gulpLabel()` applies `.textCase(.uppercase)`, which rewrites the *accessibility* label for `Text("a literal")` but not for `Text(aVariable)`. So `Due today` is published as `DUE TODAY` while a card type is published as-is. Match case-insensitively (`AppDriver`'s `gulpLabel(_:)` does).
- **Environment variables.** A UI-test runner is a separate process; only scheme variables prefixed `TEST_RUNNER_` reach it, with the prefix stripped. The scheme sets both forms of `GULP_TEST_API` for that reason.
