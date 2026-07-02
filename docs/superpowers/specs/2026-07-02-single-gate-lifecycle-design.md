# Single-Gate Lifecycle & Minimal Library — applying the IA convergence

Date: 2026-07-02
Status: Approved (design); pending implementation
Scope: Snapshot lifecycle, Inbox/Library split, web navigation, and the
product-doc fold-back across `services/shared`, `services/api`, `apps/web`,
`packages/api-client`, and `docs/01·02·04`.

## Goal

Make the owner-approved IA convergence (recorded in
[`2026-07-02-card-generation-and-import-design.md`](2026-07-02-card-generation-and-import-design.md)
§Spec amendments) real in code, UI, and the product docs — instead of a note.

The core model after this slice:

> **Inbox is the conveyor belt, Library is the shelf, Today is the gym.**
> Snapshots move `unprocessed → processing → ready`; hitting `ready` *is*
> entering the library (no confirmation act). The **only** review gate in the
> system is per-card accept/reject. The full journey:

| Stage | Status | Surface | User act |
|---|---|---|---|
| Capture | `unprocessed` | Inbox | ⊕/⌘K, optional tags |
| Digest | `processing` / `exported` (`needs_attention` on failure) | Inbox | ▶ Start or ⤓ Export→Upload; retry on failure |
| Ready | `ready` | **moves to Library** | nothing — reading is the review |
| Read | `ready` | Library → snapshot page (Pack) | read / edit blocks / discuss |
| Cards | `ready` | snapshot page (Cards) | generate / import → **accept/reject (the gate)** |
| Practice | — | Today (S4, future) | gulp accepted cards |

## Decisions locked in

- **Drop `awaiting_review` and `in_library`** from `SnapshotStatus`. Lifecycle
  becomes: `queued · unprocessed · processing · ready · exported ·
  needs_attention`. No DB rows hold the dropped values (verified), so the
  migration is risk-free.
- **Inbox = to-do, Library = shelf, both derived queries.** Inbox lists
  `queued/unprocessed/processing/exported/needs_attention`; a new **Library**
  view lists `ready`. No stored membership, no user action between them.
- **Minimal `/library` page** so `ready` snapshots keep an entry point once
  Inbox stops showing them: list (reusing the Inbox list pattern) + client-side
  **tag filter chips** (tags already exist end-to-end). No KB entity.
- **Navigation: `Today · Inbox · Library`, Today stays the first tab**
  (owner-confirmed). The inert `Feeds` and `Knowledge bases` sidebar rows are
  removed — Feeds returns when S7 is built; KB is parked (tags cover grouping).
- **Delete the `ConfirmCard` placeholder** on Today (its premise was the
  snapshot-level batch review, which no longer exists).
- **Docs fold-back is inline amendment**, following the S2 manual-trigger
  precedent: targeted edits to `01`/`02`/`04` with pointers to this spec — not
  rewrites.
- Re-introducing a pre-library gate stays a **recorded future option** (if
  `auto_process` or S7 feeds create unvetted inflow): one enum value + one
  Inbox filter clause + a confirm surface. Cheap because both views are
  derived.

## ① Status machine (shared + migration)

- `services/shared/gulp_shared/models/source.py`: remove the two enum members.
- New Alembic migration (after `e5f6a7b8c9d0`): rebuild the `snapshot_status`
  PG enum without the two values (rename old type → create new → `ALTER COLUMN
  ... USING status::text::snapshot_status` → drop old). Downgrade restores the
  old type. A guard `UPDATE`/assert is unnecessary — no code path ever wrote
  the dropped values.

## ② Derived views (api)

- `services/api/app/services/inbox.py`: filter becomes
  `status IN (queued, unprocessed, processing, exported, needs_attention)`
  (equivalently `status != ready` — write the IN-set for intent).
- New `GET /library` → `LibraryOut { items: SnapshotOut[], count }`, mirroring
  the inbox router/service pair: owner-scoped, `kind = snapshot`,
  `status = ready`, not deleted, newest first. (Tag filtering stays
  client-side in v1 — the library is small; a `?tag=` param is a later add.)
- Regenerate `packages/api-client` (`just gen-client`); add `getLibrary()`.

## ③ Web

- **Sidebar** (`components/shell/Sidebar.tsx`): NAV = Today (`/`, first) ·
  Inbox (`/inbox`, keeps the to-do count badge — now a true to-do count) ·
  Library (`/library`). Feeds/KB rows deleted.
- **New `/library` page**: server component fetching `getLibrary()`;
  `LibraryList` renders rows (reuse the `InboxRow` visual pattern) plus a tag
  chip strip — chips derived from the fetched items' tags, filtering
  client-side; an "All" chip resets. Empty state: "Nothing here yet — capture
  something and run it."
- **Snapshot page**: the reader condition collapses to `snap.status === "ready"`.
- **Today** (`app/page.tsx` + `components/today/`): remove `ConfirmCard`
  usage and delete the component + CSS. The capture-peek keeps reading Inbox;
  a freshly-`ready` snapshot leaves the peek (it is done — it now lives in
  Library).

## ④ Docs fold-back (inline amendments, each pointing here)

- **`01 §F2`** — Review model: replace the required-review/batch/auto-approve
  block with: *reading (and editing) the pack is the review; the only commit
  gate is per-card accept/reject; the snapshot-level gate is parked until
  auto-process/feeds create unvetted inflow.* Key screens/states updated
  (`awaiting review → in library` dropped).
- **`01 §F3`** — Library: entries are `ready` snapshots; grouping/scoping via
  **tags** (KB parked); filter chips = tag/type in v1 (mastery/due arrive with
  S5).
- **`01 §4.3`** — web sidebar: `Today · Inbox · Library` (+ Settings); Feeds
  returns with S7; KB row parked.
- **`02 §4.3` + `§6`** — `Snapshot.status` domain and transitions lose
  `awaiting_review`/`in_library`; note the parked gate and where it would
  re-enter.
- **`02 §4.9`** — `KnowledgeBase`/`KBMembership` marked **parked** (tags via
  `SourceTag` cover v1 grouping).
- **`04 §4 S3`** — charter annotated: v1 scope realized as library-list +
  tags + card gate (this spec + the cards spec); KB/Concept/graph remain the
  deferred remainder.

## Testing

- **shared**: enum no longer exposes dropped members (pinning).
- **migration**: upgrade + downgrade round-trip on the dev DB.
- **api**: inbox filter test rewritten (`ready` excluded, to-do set included);
  new library endpoint tests (only `ready`, ownership, ordering);
  `test_committed_snapshot_is_not_startable` switches its non-startable
  status to `exported`.
- **web**: LibraryList (renders items, tag chip filters, empty state);
  sidebar renders three links with Today first; Today page renders without
  ConfirmCard; existing suites stay green.
- Gates: `just gen-client` · per-package pytest · vitest.

## Out of scope

- The gate's future re-introduction design (with `auto_process` / S7).
- KB entity, Concept pages/graph, search, `?tag=` server-side filtering,
  batch operations on library rows, mastery/due chips (S5).
- Mobile (`apps/mobile` stays deferred).

## File-change inventory

| Layer | File | Change |
|---|---|---|
| Shared | `gulp_shared/models/source.py` | Drop two `SnapshotStatus` members. |
| Migration | `services/api/alembic/versions/*` (new) | Rebuild `snapshot_status` enum. |
| API | `app/services/inbox.py` | To-do IN-set filter. |
| API | `app/services/library.py` + `app/routers/library.py` (new) | `GET /library`. |
| API | `app/main.py` | Register library router. |
| API tests | `tests/test_inbox.py`, `tests/test_processing.py`, `tests/test_library.py` (new) | Per Testing. |
| Client | `packages/api-client/*` | Regenerate; `getLibrary()`. |
| Web | `components/shell/Sidebar.tsx` | Nav = Today · Inbox · Library. |
| Web | `app/library/page.tsx`, `components/library/LibraryList.tsx` (new) | Library page + tag chips. |
| Web | `app/snapshots/[id]/page.tsx` | Condition → `ready` only. |
| Web | `app/page.tsx`; `components/today/ConfirmCard.*` | Remove usage; delete files. |
| Docs | `docs/01-interaction-spec.md`, `docs/02-data-model.md`, `docs/04-development-plan.md` | §④ amendments. |
