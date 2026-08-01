# iOS Client Implementation Plan

> Execute task-by-task; steps use checkbox (`- [ ]`) syntax for tracking. Each task ends green (`just lint` + the task's own verification) before the next begins.

**Goal:** Ship the native SwiftUI consumption-end iOS client designed in the spec — forward from anywhere, run the daily Gulp session, read what came back — against the API exactly as it stands.

**Architecture:** An Xcode workspace holding an app target and a share-extension target, both members of one App Group so they share a cookie store. Networking goes through a generated Swift package (`swift-openapi-generator` over the same `openapi.json` that feeds `packages/api-client`), so the data model stays the one contract. No server changes: every endpoint the client needs already ships.

**Tech Stack:** Swift 5.10 / SwiftUI, iOS 17 minimum (`@Observable`, `NavigationStack`, `.scrollTargetBehavior`), `swift-openapi-generator` + `swift-openapi-urlsession`, XCTest.

**Spec:** `docs/superpowers/specs/2026-07-25-ios-client-design.md` — read it first. The mockups it references are the visual contract.

## Global Constraints

- All code comments, commit messages and docs in **English** (repo rule 6). UI copy is English-only for v1 (`03 §10` scope).
- Use `just` recipes, never raw tooling (repo rule 1). This plan **adds** recipes rather than working around their absence.
- The data model is the contract (repo rule 2): no hand-written request/response structs. Everything comes from the generated package.
- Design tokens come from `packages/ui/src/tokens.css` (mobile column of `03 §3.2`) — transcribed once into Swift, never re-picked per screen.
- Keep `just lint` green after every task.
- Commits end with `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

## Repo shape — settled 2026-07-25

Spec §7.3 is closed; Task 0 below is **done**. The answers everything else assumes:

| Question | Assumed answer |
|---|---|
| Where does the Xcode project live? | `apps/ios/` — `apps/` groups clients by role, not by language; pnpm skips directories without a `package.json` |
| What happens to `apps/mobile`? | Deleted, with its `CLAUDE.md`. It describes an abandoned plan |
| Does `just` learn Swift? | Yes: `just ios`, `just ios-test`, and a `gen-client-swift` step folded into `just gen-client` |
| Is the generated Swift client committed? | Yes, like `schema.gen.ts` — so a checkout builds without a running API |

---

### Task 0: Repo shape ✅ done 2026-07-25

**Files:** `pnpm-workspace.yaml`, `justfile`, `CLAUDE.md`, `docs/05-repo-structure.md`, `apps/mobile/` (delete), `apps/ios/CLAUDE.md` (new)

- [x] **Step 1:** Delete `apps/mobile/` and confirm `pnpm install` still resolves (the workspace glob `apps/*` tolerates a member with no `package.json`).
- [x] **Step 2:** Add recipes — `ios` (open the workspace), `ios-test` (`xcodebuild test` on a simulator destination), and extend `gen-client` with the Swift generation step.
- [x] **Step 3:** Update root `CLAUDE.md`: the layout list says `apps/mobile — Expo / React Native (TypeScript)`; replace with `apps/ios — native SwiftUI client`. Rule 1 says "two languages, one command surface" — amend to three, naming Swift and pointing at the new recipes.
- [x] **Step 4:** Update `docs/05-repo-structure.md` §7, which still calls `apps/mobile` a reserved placeholder.
- [x] **Step 5:** Write `apps/ios/CLAUDE.md` — conventions, the token source, the "backend only through the generated package" rule.

**Verify:** `just setup && just lint` green; no reference to `@gulp/mobile` survives (`grep -rn "gulp/mobile" --exclude-dir=node_modules`).

---

### Task 1: Xcode project and the design system ✅ done 2026-08-01

**Files:** `apps/ios/Gulp.xcodeproj`, `apps/ios/Gulp/DesignSystem/*.swift`, `apps/ios/Gulp/Resources/Fonts/*`

- [x] **Step 1:** Create the app target (`Gulp`, iOS 17+) and an App Group (`group.app.gulp.shared`) — the share extension needs it in Task 9, and adding it later means re-provisioning.
- [x] **Step 2:** `Tokens.swift` — the mobile column of `03 §3.2` as `Color` extensions, plus radii (12/16/20), the card shadow, and the 4 pt spacing scale. **Ink is the primary action colour; blue exists only as `Color.due`.**
- [x] **Step 3:** Bundle Geist Mono from `design/fonts/`; register Inter (vendor the variable font — the repo has no copy yet). Expose `Font.data`, `Font.label`, `Font.body`, `Font.titleL/M/S` per `03 §4.2`'s mobile column. Every numeral view uses `.monospacedDigit()`.
- [x] **Step 4:** `TickMarks.swift` — the signature device. One view, three uses: Today's due gauge (grouped new/review), the session progress rail, Library's due column. It takes a count and a style; it is never re-implemented per screen.
- [x] **Step 5:** `StateChip.swift` — hairline pill, optional coloured dot, label always present (`03 §7.2` as amended).

**Verify:** ✅ `just ios-test` green (7 tests, 3 suites). Built, installed and launched on an iPhone 17 simulator; the preview screen renders every token and all three tick styles, and Geist Mono is confirmed loading from the bundle. Snapshot testing deferred — it needs a dependency and the assertions cover what silently drifts.

---

### Task 2: Generated client and the session ✅ done 2026-08-01

**Files:** `apps/ios/Packages/GulpAPI/*`, `apps/ios/Gulp/Net/*`, `justfile`

- [x] **Step 1:** Add `GulpAPI`, a local SwiftPM package with `swift-openapi-generator` reading `packages/api-client/openapi.json`. Commit the generated sources.
- [x] **Step 2:** Wire the generator into `just gen-client` so TS and Swift can never drift.
- [x] **Step 3:** `Session.swift` — auth. **Use the cookie**, not a PAT: `_set_cookie` sets `max_age = session_ttl_days * 86400`, so it is a persistent cookie that `HTTPCookieStorage` keeps across launches, and `POST /auth/login` needs no server change. Back the store with `HTTPCookieStorage.sharedCookieStorage(forGroupContainerIdentifier:)` so the share extension inherits the login. (This closes spec §7.2; record the decision there.)
- [x] **Step 4:** Sign-in and register screens — email + password, ink primary button, inline error text that says what to fix (`03 §2.7`: never blame the user).
- [x] **Step 5:** A `401` anywhere clears the session and returns to sign-in without losing the pending action.

**Verify:** ✅ `just ios-test-live` green — 16 tests, including four that sign in against a running `just dev`. Cookie sharing proven across processes: the test host signs in, the app relaunches and restores without a login form. `just ios-test` skips the live suite **by name** rather than self-skipping on a missing variable, because a test that passes when it never ran is worse than no test.

---

### Task 3: Shell ✅ done 2026-08-01

**Files:** `apps/ios/Gulp/App/*`

- [x] **Step 1:** Three tabs — `Today · Library · You`, active item filled glyph + ink label. No capture tab.
- [x] **Step 2:** A `NavigationStack` per tab; the reader and the session both present modally over the whole shell (the session has no tab bar, `03 §7.7`).
- [x] **Step 3:** One `@Observable AppModel` holding session state and a `Task`-based refresh; screens observe, never fetch in `body`.

**Verify:** ✅ built and launched; the shell restores its session, fetches `GET /today` once through `AppModel`, and renders real data from the dev database (20 due, 11 new, 9 reviews). Tab switching is **not** driven — this machine has no UI input automation (osascript is refused Accessibility permission), so only rendering is confirmed.

**Open:** iOS 26 draws the tab bar as a floating capsule, not the flat bar with a hairline top edge the mockups show. `.toolbarBackground(_:for: .tabBar)` does not reach the floating style. Either the design accepts the platform idiom or the bar gets rebuilt by hand — an owner decision, not a bug.

---

### Task 4: Today ✅ done 2026-08-01

**Files:** `apps/ios/Gulp/Today/*`

- [x] **Step 1:** `GET /today` → the hero card: mono numeral, tick gauge split new/review, `Start Gulp` in ink.
- [x] **Step 2:** Date and streak overline; the amber flame is the only warm mark on the screen.
- [x] **Step 3:** Recently-forwarded rows from `recent[]` with status chips, plus a **`Start`** button on `unprocessed` rows calling `POST /snapshots/{id}/process` (spec §2.1) — optimistic flip to `processing`, revert with an inline message on failure.
- [x] **Step 4:** States — skeletons never spinners (`03 §8`), an empty state that points at the share sheet, and an offline banner.

**Verify:** matches the mockup at 324 pt; the `Start` round trip flips the chip; Dynamic Type at XXL doesn't clip the hero.

---

### Task 5: The session ✅ done 2026-08-01

**Files:** `apps/ios/Gulp/Session/*`

- [x] **Step 1:** `POST /sessions` (`target_minutes` from `You`), then resume via `GET /sessions/current` if one is active.
- [x] **Step 2:** Prompt screen — close, `n / N`, the tick rail, card-type overline, prompt, options in the thumb zone. Three card types: flashcard, mcq, cloze.
- [x] **Step 3:** Reveal — `answer` and `explanation` ship with the session, so no round trip. Correct/incorrect indicator, grounded source line.
- [x] **Step 4:** Grade — three hairline controls with mastery dots, **each labelled with the interval it buys**, from the previous `ReviewOut.mastery.interval_days`. Haptic on grade (`03 §9`).
- [x] **Step 5:** `POST /sessions/{id}/reviews` → advance to `next_card`; `/snooze` on the snooze affordance; `/complete` → summary.
- [x] **Step 6:** Summary — filled rail, mono figures, streak, a next line, `Done` / `Keep going`. Never a dead end (`01 §F4`).

**Verify:** a 12-card session end to end against a seeded account; interrupt mid-session and resume to the same card; reduced-motion honoured.

---

### Task 6: Library ✅ done 2026-08-01

**Files:** `apps/ios/Gulp/Library/*`

- [x] **Step 1:** `GET /library`, rows of `ready` snapshots — title up to two lines, source and card count in mono.
- [x] **Step 2:** The right column is `TickMarks` in `Color.due` — one tick per due card, empty when at rest (spec §2.4).
- [x] **Step 3:** Hairline search field, client-side filter to start.
- [x] **Step 4:** Filter row as mono labels, active one inked and underlined, single-select, sourced from `source_feed` and user tags.

**Verify:** the right edge visibly separates live from resting; VoiceOver reads "3 cards due" rather than announcing three marks.

---

### Task 7: You ✅ done 2026-08-01

**Files:** `apps/ios/Gulp/You/*`

- [x] **Step 1:** Account block from `GET /me`.
- [x] **Step 2:** Mastery bar and legend from `TodayOut.mastery` — the one screen where the full mastery palette appears.
- [x] **Step 3:** Streak / best / reviewed figures; daily-session segmented control writing `target_minutes`.
- [x] **Step 4:** Sign out, and the line naming what the phone deliberately doesn't do.

**Verify:** changing session length changes the next session's card count.

---

### Task 8: Reader and chat ✅ done 2026-08-01

**Files:** `apps/ios/Gulp/Reader/*`

- [x] **Step 1:** `GET /snapshots/{id}/pack` → block renderers: prose, formula (own tinted well, independently scrollable), table, figure, list. Section headings in mono.
- [x] **Step 2:** Pack head — overline, title, summary, **key insight** with its rule-above-and-below treatment, contributions as a hairline set with no numbering.
- [x] **Step 3:** Top bar collapses the title in on scroll; `↗` opens the original. No segmented control (spec §5.4).
- [x] **Step 4:** Bottom bar — `Ask about this` and the card count.
- [x] **Step 5:** Chat — `GET /snapshots/{id}/messages`, then `POST /snapshots/{id}/messages/stream` consumed as SSE. Questions as bubbles, answers as plain text.
- [x] **Step 6:** `[[block:ID]]` citations render as chips that scroll the reader to the block; attached blocks appear as removable context chips above the composer.

**Verify:** a real `PaperPack` with a figure and a formula renders without horizontal page scroll; a citation tap lands on the right block; streaming cancels cleanly on dismiss.

---

### Task 9: Share extension ✅ done 2026-08-01

**Files:** `apps/ios/GulpShare/*`

- [x] **Step 1:** Extension target in the App Group, accepting URLs, text and PDFs.
- [x] **Step 2:** The sheet — detected title, type chip, source host, note and tags fields, ink `Forward` button. The verb is **Forward**, never Gulp.
- [x] **Step 3:** `POST /capture` using the shared cookie store. Self-confirm after 3 s with a visible countdown that any interaction cancels.
- [x] **Step 4:** Not signed in, or offline → queue locally in the App Group container and flush on next app launch. Never lose a capture. *(Checked off on 2026-08-01 before it existed — there was no queue, only a `Try again` button. Built for real on 2026-08-01 as `Shared/Forward/ForwardQueue.swift`, flushed from `AppModel.flushPendingForwards()`.)*
- [x] **Step 5:** The same form behind Today's `+`. *(Added after the UI tests found that button wired to an empty closure.)*

**Verify:** ✅ `POST /capture` from the app's `+` lands in the inbox — driven by `GulpUITests`, confirmed server-side. The queue round-trips under unit test. **Not verified:** forwarding from Safari, and therefore whether the extension really inherits the cookie. The app half of that mechanism *is* proven — the `gulp_session` cookie for the API host sits in the App Group container and the app's private container holds none — but nothing has read it from the extension's process.

---

### Task 10: Finish

- [ ] **Step 1:** Dynamic Type through XXXL on every screen; 44 pt minimum targets audited. *(Needs eyes on a device — not claimed.)*
- [x] **Step 2:** VoiceOver — tick marks expose a count rather than a run of marks; chips and rows carry labels. Full audit still needs a device.
- [x] **Step 3:** Reduced motion degrades every transition to a fade.
- [x] **Step 4:** Every list has its loading, empty and error state per `03 §8`, with copy that names the next action.
- [x] **Step 5:** App icon and launch screen. The icon is the product logo (`icon.png`, the pop-art banana) on `Ink.paper`, built by `just ios-icon` — a script, not an exported binary, so a new logo is one command. The launch screen is the same paper: it was an empty `UIColorName`, which meant launching to black on a dark phone and flashing to paper, because this app has no dark mode. Icon, launch and Today are now one continuous surface. *(`just ios-icon ink` swaps the background if the paper reads too pale on a light wallpaper.)*
- [x] **Step 6:** `GulpUITests` — the taps. A UI-test target driving the shipped app against a live API: `just ios-uitest`.

**Verify:** ✅ `just lint`, `just ios-test-live` (29 tests, 9 suites) and `just ios-uitest` (11 tests) all green.

**On the earlier claim that the interaction could not be tested here.** That was wrong, and it was wrong in the expensive direction — it wrote off a whole class of verification on a false premise. The premise was that this machine has no UI automation, which is true of *macOS* automation (osascript is refused Accessibility permission, so the Simulator window cannot be driven from outside). XCUITest does not go that way: the runner is an app inside the simulator using iOS's own accessibility layer, and `xcodebuild` drives it with no macOS permission at all.

What the taps then found, none of which any unit test could have:

| Found by tapping | |
|---|---|
| Today's `+` was wired to an empty closure | The button drew, took the tap, did nothing |
| Task 9 Step 4 was checked off but unbuilt | No offline queue existed; a failed forward just showed an error |
| `just ios-test` was not unit-only | Two live suites share a file; only one was named in the skip, so the "no server needed" recipe needed a server |
| `.textCase(.uppercase)` rewrites the accessibility label only for literal `Text` | `Text("Due today")` is published as `DUE TODAY`; `Text(cardType)` is not. Display is uppercase either way, so this is invisible until something reads the labels |

**Still not verified:** Dynamic Type through XXXL, a full VoiceOver pass, and forwarding from Safari (the share sheet is another app's UI; cross-app XCUITest against iOS 26 Safari was not attempted). The uppercase finding above is a live question for the VoiceOver pass — an all-caps label is read differently from a title-case one, and this app's labels are inconsistent about which one reaches the screen reader.

---

## Out of scope

Widget, push notifications, offline Gulp, CJK typography, Android, block editing, card accept/reject, and conversation sediment. Each is named in spec §6 with its reason.
