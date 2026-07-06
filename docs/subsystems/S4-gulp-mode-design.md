# S4 — Gulp Mode · subsystem design

*Gulp · subsystem design doc · v1 · 2026-07-06*

> The per-subsystem design doc spun out of [`04-development-plan.md §6`](../04-development-plan.md), resolving the **`S4` charter as amended 2026-07-06** (`04 §4 S4`) — the replan that **folded Mastery & Scheduling (ex-`S5`) into Gulp Mode**, so this one subsystem owns *both* halves of the daily loop: the **session** (present → grade) and the **engine** (grades → schedule). It sits below the four product docs ([`01`](../01-interaction-spec.md) flows §F4/§F7, [`02`](../02-data-model.md) objects §5, [`03`](../03-ui-system.md) look §7.7) and the [`05`](../05-repo-structure.md) layout.
>
> **Altitude:** one capability, end to end. It resolves the charter's open questions (the v1 interval formula & constants, the ladder-advance rules, the at-risk threshold, session pacing) and fixes the data/API/UI touchpoints. It stops above the FSRS algorithm (fields reserved, swap deferred) and above real auth/sync (stubbed, owned elsewhere).
>
> **Locked scope (decided with the product owner in this brainstorm):** the **full engine** — persisted *resumable* sessions, the 7-rung ladder with advance rules, at-risk detection, and daily-load capping. **`daily` scope only** is wired. **Parked:** KB/concept-scoped sessions (blocked on S3 entities), inline AI feedback on free responses, "Explain more" → Conversation (S6 was dropped), the FSRS swap, and mastery visualization beyond the 3-state view + tallies. See §2.

---

## 1. Scope & reading guide

- **Covers:** the daily Gulp session (`01 §F4`) and the mastery/scheduling engine behind it (`01 §F7`, `02 §5`) — full stack: `gulp_shared` (append-only `ReviewEvent`, the scheduling/mastery fold on `Card`, `GulpSession`) → `services/api` (the `/gulp` namespace) → `packages/api-client` → `apps/web` (the full-bleed `/gulp` route, the Today entry point, Library mastery badges).
- **The cut follows the (amended) charter.** S4 owns "run the daily session — present one prompt at a time, capture the response and self-grade — and turn that grade stream into a tracked, evolving mastery that surfaces the right item at the right time" (`04 §4 S4`). Everything the grade stream feeds is internal to S4; the AI drafting that *makes* cards stays S2, the review gate that *accepts* them stays S3.
- **Out of scope (handed off / parked, §9):** KB/concept-scoped sessions (S3's entities don't exist — the scopes are modeled but return 400); inline AI feedback on free responses (its own quality bar; the grounded `explanation` already covers reveal); "Explain more" → `Conversation` (S6 dropped); the FSRS swap (`stability`/`difficulty` reserved); mastery viz beyond the 3-state badge + tallies (Concept pages parked in S3); mobile; real auth; real offline/sync (S8).
- **How to read it:** §2 is the decisions (skim first); §3 is the **engine** (the scheduler + the ladder — the hardest part); §4 is the **session** (composition, resume, retests); §5 is the data layer; §6 the API; §7 the web client; §8 cross-cutting states; §9 validation + handoffs.
- **What prior slices left as floor:** the `Card` model exists (`card_type` flashcard/mcq/cloze, `prompt`, `answer?`, `explanation?`, `options?`, `origin`, `status` draft/accepted/rejected) with its scheduling/mastery fields **explicitly stubbed** — `card.py` carries `# Deferred: scheduling / mastery value objects — added by S5`. The `/today` endpoint counts accepted cards; `StartGulpCard` renders with its button **disabled** ("Practice mode is coming soon"). S4 grows exactly these stubs into the engine.

---

## 2. Resolved decisions

Each resolves an open question from the S4 charter (`04 §4 S4`) or a fork this slice forces. **Reversible** = changeable later without reshaping consumers.

| # | Decision | Rationale | Reversible? |
|---|---|---|---|
| **C1** | **Build the full engine now** — persisted *resumable* `GulpSession`, the 7-rung ladder with advance rules, at-risk detection, daily-load cap + backlog spread — not a thin practice UI. | The owner's goal is to *close the user journey* (capture→pack→practice→resurface). The scheduling engine is what makes practice "real spaced learning" rather than a flat quiz; deferring it would leave the loop hollow (`04` connection points). | Partly — the engine is additive over the card model; individual pieces (§C7 pacing, §C4 ladder) are tunable. |
| **C2** | **`ReviewEvent` is the append-only source of truth; `Card.scheduling` + `Card.mastery` are a *fold* over it, persisted as columns on `cards`.** `next_review_at` is indexed (drives the due-query); `daily`/`due`/`at_risk` are **derived on read**, never stored. | `02 §4.10`/`§9` invariant: history is the log, the schedule is a recompute over it — which is exactly what keeps the FSRS swap a pure-algorithm change. Persisting the fold (vs. recomputing per request) is what makes "which cards are due?" an indexed query instead of a scan. | Yes — the fold is derivable; the FSRS swap recomputes the same columns from the same events. |
| **C3** | **v1 scheduler = SM-2-lite** (§3.2): three grades drive an ease-scaled interval. `got_it` lengthens (`1d → 3d → round(interval×ease)`), `fuzzy` barely grows (`×1.2`, ease −0.05), `missed` resets (`→1d`, ease −0.20, `lapses+1`) **and** re-queues the card as an in-session retest. Ease starts `2.3` (floor `1.3`, cap `2.6`). | Resolves the charter's "v1 interval formula & its constants." Uses exactly the `02 §5.2` reserved fields (`interval_days`, `ease`, `reps`, `lapses`), so FSRS drops in without touching the interaction (`01 §11`). Constants are house-tuned SM-2 territory. | Yes — pure function in `domain/scheduling.py`; constants are data, the algorithm is swappable. |
| **C4** | **The 7-rung ladder is stored and practice-advanced.** A card enters at **`read`** on accept (the pack *was* read to produce it); grades advance it `can_recall → can_distinguish → can_apply → mastered` by interval/type bands (§3.3); a `missed` drops it **one rung** (floor `read`). `unread`/`summarized` are **reserved** for future reading subsystems (S3) — S4 never assigns them. | `02 §5.1` makes `ladder` "the only stored source of truth" (`daily` derives from it). Per-card, the upper rungs (`distinguish`/`apply`) are cognitive levels that truly belong to a **Concept** rolled up across its cards — but Concepts are parked (S3), so S4 approximates them per-card via retention bands. Honest and additive. | Yes — the rung function is `domain/mastery.py`; when Concept rollups land (S3) they supersede the per-card approximation for the upper rungs. |
| **C5** | **`daily` scope only is wired.** `scope_type ∈ {knowledge_base·concept}` stays in the enum (`02 §4.10`) but returns **400** (no S3 entities to scope by). The empty-state fallback wires **`at_risk`** then **`free_explore`** so a session is never a dead end (`01 §F4`). | The charter parks scoped sessions until S3; the enum stays faithful to `02` so the later wiring is additive, not a migration. `at_risk`/`free_explore` are computable from the engine alone. | Yes — S3 lifts the 400s; the enum and `scope_ref` are already modeled. |
| **C6** | **Composition is frozen at start (`planned_card_ids`, ordered JSON) for resume; misses are re-queued *live*.** Leaving mid-session → `status=abandoned` (resumable). On resume the live queue = planned cards with no passing event this session + any missed-not-yet-recovered. `complete` when the queue drains (or the user ends early). | `02 §4.10` wants a resumable session ("continue where you left off"); freezing the plan makes resume deterministic while live re-queue delivers the charter's "retests of recent misses" *within* the session. JSON (vs. a join table) tolerates a card deleted mid-session by simply skipping it; per-card outcomes already live in `review_events`. | Yes — a `gulp_session_cards` join table is a drop-in if referential integrity is later wanted. |
| **C7** | **Pacing = `target_minutes × cards_per_minute` (default `cards_per_minute = 3` → a 5-min session ≈ 15 cards); the composed count *is* the daily-load cap.** Overflow due cards **stay due** (surface next day — never lost); a **±1-day jitter** on `next_review_at` de-synchronizes an import spike so it doesn't cluster on one future day. | Resolves "session-length adaptation" + "caps daily load and spreads the backlog" (`01 §F4`/`§F7`). `target_minutes` comes from `User.gulp_session_minutes` (default 5, `02 §4.1`), overridable per session. | Yes — `cards_per_minute` and the jitter window are constants. |
| **C8** | **Inline AI feedback on free responses is parked.** Reveal shows the canonical `answer` + the source-grounded `explanation` (already grounded by S2); the user's free `response` is still captured to the `ReviewEvent`. | Keeps the session snappy (no mid-session LLM round-trip) and defers a distinct quality bar the charter flags as open. Additive later: the reveal panel gains an AI-critique region fed by the stored `response`. | Yes — purely additive to reveal; nothing depends on its absence. |
| **C9** | **`/gulp` is a full-bleed focus route** (sidebar hidden). Self-grade = three controls **`Got it`/`Fuzzy`/`Missed`** (emerald/amber/red, `03 §7.7`) with **keyboard shortcuts** (space = reveal, `1`/`2`/`3` = grade — web-first). In-session affordances: **"Why am I seeing this?"** (the scheduling reason) and **"Snooze"** (= push `next_review_at` to tomorrow, drop from today's queue, **no** `ReviewEvent`). | "Strict one-thing-per-screen" (`04 §4 S4`, `01 §F4`). Keyboard grading is the web client's speed advantage. Snooze-without-a-grade keeps the log honest — a snooze is a scheduling nudge, not a review. | Yes — UI-local; the snooze reschedule is a one-line scheduling write. |

---

## 3. The engine — scheduler + ladder

The core the whole subsystem hangs off: an append-only log, a deterministic fold to a schedule, and a fold to a mastery rung. Both folds are **pure functions over a card's `ReviewEvent`s + card type** (`domain/scheduling.py`, `domain/mastery.py`) — no I/O, table-testable over simulated time.

### 3.1 The log & the fold (`02 §9` invariant)

Every graded prompt appends one `ReviewEvent` (`grade`, optional `response`, `at`). On write, the service recomputes the card's `scheduling` + `mastery` **from the latest state** (an incremental fold — equivalent to replaying all events, asserted by test §9) and persists them as columns. The event log is never mutated; the columns are a cache of the fold that keeps `next_review_at` indexable.

### 3.2 Scheduler (SM-2-lite, C3)

`apply_review(scheduling, grade, card_type) -> scheduling`. A brand-new accepted card starts `interval_days=0, ease=2.3, reps=0, lapses=0, next_review_at=now` (so it is immediately a "new" due item). Then per grade:

| grade | `reps` | `ease` | `interval_days` → | `lapses` | in-session |
|---|---|---|---|---|---|
| **got_it** | +1 | +0 (cap 2.6) | `reps==1 → 1` · `reps==2 → 3` · `reps≥3 → round(interval × ease)` | — | advance |
| **fuzzy** | +1 | −0.05 (floor 1.3) | `max(1, interval × 1.2)` | — | advance |
| **missed** | → 0 | −0.20 (floor 1.3) | **→ 1** (reset) | +1 | **retest** — re-queued live (§4.3) |

`next_review_at = now + interval_days` (± a small jitter, C7). `last_reviewed_at = now`. The reserved `stability`/`difficulty` stay null in v1.

### 3.3 Mastery ladder (C4)

`advance_ladder(current, scheduling, grade, card_type) -> ladder`. Enters at **`read`** on accept. Then, after the scheduler runs:

- **`missed`** → drop one rung (`… → can_recall → read`, floor `read`).
- **`got_it`/`fuzzy`** → the *highest* rung whose bar is met:
  - **`can_recall`** — `reps ≥ 1`
  - **`can_distinguish`** — a `got_it` on an **`mcq`** card, **or** `interval_days ≥ 7`
  - **`can_apply`** — `interval_days ≥ 21` and `reps ≥ 3`
  - **`mastered`** — `interval_days ≥ 60`, `reps ≥ 4`, no lapse in the last 2 events

**Derived views** (never stored, computed on read):

| Derived | Rule |
|---|---|
| `daily` | fixed map (`02 §5.1`): `unread`/`read → new` · `summarized`/`can_recall`/`can_distinguish → learning` · `can_apply`/`mastered → known` *(S4 only ever produces `read`+; `unread`/`summarized` are S3's)* |
| `due` | `next_review_at ≤ now` |
| `at_risk` | overdue by **≥ 1× its own interval** — `now ≥ next_review_at + interval_days` ("approaching forgetting") |

---

## 4. Session & composition

### 4.1 `GulpSession` lifecycle

`building` (composing) → `active` (started, being gulped) → `complete` (queue drained / ended) · or `abandoned` (left mid-session; resumable). One live (`active`/`abandoned`) session per user at a time — `GET /gulp/sessions/current` returns it for resume.

### 4.2 Composition (`POST /gulp/sessions`, then frozen — C6/C7)

Built for the owner across **all** sources (a card's schedule is global, not per-snapshot):

1. **Size** the session: `cap = target_minutes × cards_per_minute` (default → ~15).
2. **Pool & priority**, filled to `cap` in order: ① **due & at-risk** (most-overdue first) → ② other **due** (`next_review_at ≤ now`) → ③ **new** (`status=accepted`, `reps=0`) → ④ **retests** of recent misses.
3. **Interleave** so no two consecutive cards share a source, and new/due/retest are mixed rather than blocked.
4. **Cap & spread:** anything past `cap` **stays due** for a later day; apply the ±1-day `next_review_at` jitter to avoid a synchronized future spike (C7).
5. **Empty state** (nothing due + nothing new): compose an **`at_risk`** session, else **`free_explore`** (a random reinforcement sample of `known` cards) — never a dead end (C5).

`planned_card_ids` freezes the ordered result; `status → active`, `started_at = now`.

### 4.3 Reviewing & retests

Each `POST …/reviews` appends a `ReviewEvent`, runs both folds (§3), and returns the updated mastery + the **next** card. A `missed` card is **re-queued live** — appended a few positions on so it recurs *this* session (spaced within-session), independent of its persisted `next_review_at` (which is now 1 day out for future days). The session is `complete` when the live queue drains; `POST …/complete` (or ending early) stamps `completed_at` and returns the summary.

### 4.4 Summary (`GET …/summary`)

`reviewed_count` · `newly_mastered` (cards that reached `mastered` this session) · `still_fuzzy` (ended on `fuzzy`/`missed`) · `streak_days` (**derived**: consecutive days with ≥1 `complete` session, from `completed_at` history — no stored field) · `next_up` ("what to gulp next" — remaining due count / inbox count).

---

## 5. Data layer — `services/shared/gulp_shared`

The physical-schema slice (`02 §10` bridge). One Alembic revision: extend `cards` + `users`, create `review_events` + `gulp_sessions`.

**`models/card.py`** — grow the stubbed fold (the `# Deferred … added by S5` block). All nullable until `status=accepted`; set on accept (§3.2/§3.3 initial state):

| Column | Type | Notes |
|---|---|---|
| `interval_days` | float | default `0` |
| `ease` | float | default `2.3` — v1 difficulty multiplier |
| `next_review_at` | timestamptz? | **indexed** — drives `due` + composition |
| `last_reviewed_at` | timestamptz? | |
| `reps` | int | default `0` — successful reviews (`0` = new) |
| `lapses` | int | default `0` — total misses |
| `stability` | float? | reserved for FSRS; unused in v1 (`02 §5.2`) |
| `difficulty` | float? | reserved for FSRS; unused in v1 |
| `ladder` | enum `{unread·read·summarized·can_recall·can_distinguish·can_apply·mastered}`? | stored rung; `read` on accept |
| `mastery_updated_at` | timestamptz? | |

> `daily` / `due` / `at_risk` are **not** columns — derived on read (§3.3), per the `02 §9` "no stored derived state" invariant.

**`models/review_event.py`** — new, append-only (never updated, never soft-deleted):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | via `TimestampedBase` |
| `owner_id` | FK `users.id` | |
| `session_id` | FK `gulp_sessions.id` | |
| `card_id` | FK `cards.id` | |
| `grade` | enum `{got_it·fuzzy·missed}` | |
| `response` | text? | free response when captured (C8) |
| `at` | timestamptz | the event time (= `created_at`) |

**`models/gulp_session.py`** — new:

| Column | Type | Notes |
|---|---|---|
| *(+ implicit mixin fields)* | | `id`, `created_at`, `updated_at`, `deleted_at` |
| `owner_id` | FK `users.id` | |
| `scope_type` | enum `{daily·knowledge_base·concept·free_explore·at_risk}` | v1 writes `daily`/`at_risk`/`free_explore` (C5) |
| `scope_ref` | UUID? | null for `daily`; the KB/Concept id when scoped (parked) |
| `target_minutes` | int | from `User.gulp_session_minutes`, overridable |
| `planned_card_ids` | JSON `list[UUID]` | frozen ordered composition (C6) |
| `status` | enum `{building·active·complete·abandoned}` | |
| `started_at` / `completed_at` | timestamptz? | |

**`models/user.py`** — add `gulp_session_minutes: int` default `5` (`02 §4.1`; S1 deferred it, §5 note there). 

**`domain/scheduling.py`** & **`domain/mastery.py`** — the two pure folds (§3.2/§3.3), plus `compose_session(...)` helper primitives (`domain/session.py`) for the priority/interleave rules (§4.2), all table-testable.

**Migration:** `just migrate "s4 gulp mode engine"` → `just migrate-up`.

---

## 6. API layer — `services/api`

Conventional layering (`05 D4`): thin routers → `services/gulp.py` holds logic → persistence in `gulp_shared`.

**`schemas/gulp.py` (→ OpenAPI → api-client):**

| Schema | Shape |
|---|---|
| `SessionCardOut` | `id` · `card_type` · `prompt` · `options?` · `answer?` · `explanation?` · `source_title?` · `reason: enum{new·due·retest·at_risk}` · `daily: enum{new·learning·known}` — *the full card travels up front (one round-trip); the client hides `answer`/`explanation` until reveal (§7)* |
| `SessionOut` | `id` · `scope_type` · `target_minutes` · `status` · `started_at?` · `cards: SessionCardOut[]` (ordered) |
| `ReviewIn` | `card_id` · `grade: enum{got_it·fuzzy·missed}` · `response?` |
| `ReviewOut` | `mastery: {ladder, daily, next_review_at, interval_days}` · `next_card: SessionCardOut?` · `done: bool` |
| `SnoozeIn` | `card_id` |
| `SummaryOut` | `reviewed_count` · `newly_mastered` · `still_fuzzy` · `streak_days` · `next_up: {due_count, inbox_count}` |
| `TodayOut` *(extend)* | + `due_count` · `new_count` · `mastery: {new, learning, known, at_risk}` |

**`routers/gulp.py`:**

| Endpoint | Returns |
|---|---|
| `POST /gulp/sessions` | compose + start (body: `scope_type=daily`, `target_minutes?`) → `SessionOut`; `knowledge_base`/`concept` → **400** (C5) |
| `GET /gulp/sessions/current` | the resumable `active`/`abandoned` session → `SessionOut?` |
| `GET /gulp/sessions/{id}` | fetch for resume → `SessionOut` |
| `POST /gulp/sessions/{id}/reviews` | append event + fold → `ReviewOut` |
| `POST /gulp/sessions/{id}/snooze` | reschedule + drop → `ReviewOut` (next card; no event, C9) |
| `POST /gulp/sessions/{id}/complete` | stamp `completed_at` → `SummaryOut` |
| `GET /gulp/sessions/{id}/summary` | → `SummaryOut` |

**`services/gulp.py`** — `compose_session` (§4.2, over the owner's accepted cards), `record_review` (append `ReviewEvent`, run both folds, persist, pick next incl. live retest), `snooze`, `summarize`, `current_session`. **`services/today.py`** — extend `today_summary` with the due/new counts + mastery tally.

Registered in `main.py`. After schema changes: **`just gen-client`**.

---

## 7. Web client — `apps/web`

**`app/gulp/page.tsx`** — the full-bleed focus route (C9), sidebar hidden. A client island (the session is interactive): on mount, resume `GET /gulp/sessions/current` else `POST /gulp/sessions`, then run the queue.

**`components/gulp/`:**
- `SessionRunner` — the queue state machine (present → reveal → grade → next; handles live retest, snooze, end-early, resume).
- `CardPrompt` — per `card_type`: **flashcard** (prompt → *Show answer*), **mcq** (tappable `options`, marks correct on reveal), **cloze** (type the `____` fill).
- `Reveal` — `answer` + grounded `explanation` (C8: no AI critique yet).
- `GradeBar` — `Got it`/`Fuzzy`/`Missed` (emerald/amber/red) + the `1`/`2`/`3` & space key handlers.
- `WhyChip` (renders `reason`) · `SnoozeButton` · `SessionSummary` (§4.4, deep-links to due/inbox).

**Today (`app/page.tsx` / `components/today/`):** enable `StartGulpCard` — show `due_count`/`new_count`, **Start Gulp** (or **Resume** when `current` exists) → `/gulp`; add a compact `MasteryTally` (`known`/`learning`/`new` + `at_risk`) — the "mastery stats surface."

**Library (`components/cards/CardRow.tsx`):** add the 3-state `daily` badge (new/learning/known) + a `due` dot. (No Concept page — parked in S3.)

**Contract:** new `@gulp/api-client` wrappers (`startGulpSession`, `getCurrentGulpSession`, `getGulpSession`, `reviewCard`, `snoozeCard`, `completeGulpSession`, `getGulpSummary`) over a regenerated `schema.gen.ts` — never hand-written types (`apps/web/CLAUDE.md`, rule 2).

---

## 8. Cross-cutting states (`01 §7`)

| State | Behavior in S4 |
|---|---|
| **Loading** | the session composes server-side in one call; the runner shows a single skeleton card, never a blank spinner. |
| **Empty** | nothing due + nothing new → an `at_risk` then `free_explore` session (C5); if even those are empty, an "all caught up" summary with a free-explore offer — never a dead end. |
| **Grade in flight** | grading is optimistic locally (advance immediately) while the `POST …/reviews` is in flight; the grade controls are disabled until it resolves, so a grade posts **once**. A failed write surfaces an explicit retry on that card (not an auto-retry) — no double-append. |
| **Resume** | leaving `/gulp` mid-session → `abandoned`; Today and `/gulp` offer **Resume** (`GET current`). |
| **Offline** | v1 `/gulp` requires connectivity (the session is server-composed) — a graceful "reconnect to gulp" prompt. Real offline gulp on cached due items is **S8**. |

---

## 9. Validation & handoffs

**Acceptance — S4's own success criteria (`04 §2.2` — validate the capability, not the whole loop):**
- A `daily` session composes from accepted **due + new** cards across sources, interleaved, capped near `target_minutes`; the pool priority holds (§4.2).
- Every grade appends **one** `ReviewEvent`; the persisted `scheduling`/`mastery` **equals a full replay** of the log (the fold invariant, asserted).
- Intervals behave: `got_it` lengthens, `fuzzy` barely grows, `missed` resets **and** retests in-session (§3.2).
- The ladder advances `read → … → mastered` per the bands and drops on a miss; `daily`/`due`/`at_risk` derive correctly (§3.3).
- A backlog spike is **capped** (overflow stays due next day, nothing lost) and de-synchronized by jitter (§4.2).
- A session **resumes** after abandon with the right remaining queue (§4.3).
- The summary reports reviewed / newly-mastered / still-fuzzy / streak; the empty state never dead-ends.
- *Tests:* pytest table-driven over `domain/scheduling.py` + `domain/mastery.py` (grade sequences × simulated time), `compose_session` priority/interleave/cap, and the fold-equals-replay invariant; a web smoke of a full session (present → grade → summary → resume).

**Handoffs (the seams this slice leaves):**
- **S3 (the circle-back, `04 §5`):** lift the `knowledge_base`/`concept` **400**s once those entities exist; `Concept.mastery` becomes a **rollup of its cards' ladders** (this doc's per-card upper-rung approximation, C4, is superseded by the rollup for `distinguish`/`apply`); Concept pages surface the full ladder + at-risk lists.
- **FSRS (`01 §11`):** swap `domain/scheduling.py` to recompute `stability`/`difficulty` from the **same** `ReviewEvent`s — no schema change, no interaction change (the reserved fields + the fold guarantee it, C2/C3).
- **X2 Notifications:** the daily reminder and the "at risk" nudge read this engine's `due`/`at_risk` derivations (`04 §4 X2`).
- **S8:** offline gulp on cached due items + cross-device session resume replace §8's online-only stance and §4.1's single-live-session assumption.
- *(Dropped in the replan: S6's "Explain more" mini-Conversation off the reveal; S7's weekly-review at-risk digest — both would have consumed this engine.)*

---

> **Implemented 2026-07-07** (branch `feat/s4-gulp-mode`, plan [`../superpowers/plans/2026-07-06-s4-gulp-mode.md`](../superpowers/plans/2026-07-06-s4-gulp-mode.md)): the full engine ships — `ReviewEvent` log + the scheduling/mastery fold on `Card`, SM-2-lite scheduler, the 7-rung ladder, persisted resumable `GulpSession`, the `/gulp` API, and the full-bleed `/gulp` web session (all three card types, keyboard grading, client-driven retests, snooze, summary) + Today Start/Resume + mastery surfaces. Parked as designed: KB/concept scopes (400), inline AI feedback, FSRS swap.

*Next per-subsystem work in build order (`04 §5`): the **circle-back to `S3`** — the KB / Concept slice — which consumes S4's stored `ladder` for Concept mastery rollups and lifts the scope-`400`s this doc leaves behind.*
