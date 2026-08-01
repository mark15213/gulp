# Feeds & Inbox — two-stage triage

Date: 2026-08-01
Status: Approved (design); pending implementation
Scope: `services/shared` (one column + migration), `services/api` (feeds ·
inbox · processing), `apps/web` (Feeds workspace · Inbox), plus doc amendments
to `docs/01·02`.

## Goal

Repair the interaction logic between **Feeds** and **Inbox**. Today the two
surfaces disagree about what an intake action commits the user to, and the
Feeds surface has no way to express "seen it, don't want it" — the two defects
compound into a triage loop that silently loses decisions.

This spec makes the funnel explicit: **Feeds decides *whether*, Inbox decides
*how*.** Nothing spends AI without a deliberate click, on either path.

## The defects being fixed (observed 2026-08-01)

1. **"Forward" means two different things.** From the Capture sheet it creates
   an `unprocessed` snapshot (`services/api/app/services/capture.py`). From the
   Feeds reader it creates the snapshot *and* immediately calls
   `start_processing` (`services/api/app/services/feeds.py`). The high-volume,
   low-deliberation path spends AI automatically while the deliberate path
   asks for a second click — backwards, and it quietly voids the manual-trigger
   cost control of `01 §F1 step 5`.
2. **Inbox means "not ready yet", not "your move".** `_TODO` includes `queued`
   and `processing` (`services/api/app/services/inbox.py`), states in which the
   user can do nothing. The sidebar badge therefore over-counts, and a
   feed-forwarded item flashes through the badge on its way to the Library.
3. **Feeds has no *skip*.** The only way to clear an entry is `read`, and
   `read` is set automatically the instant the entry is opened
   (`FeedsWorkspace.tsx`). Anything glanced at disappears from the queue
   whether or not a decision was made; `read` carries both "I opened this" and
   "I dealt with this".
4. **The decision lives in the third pane.** `Forward` exists only in
   `EntryReader`; entry rows have no inline action and there is no keyboard
   path, so scan→keep costs three interactions per item on feeds that produce
   dozens a day.
5. **Downstream status is mirrored in three places** — the Feeds ✓ marker with
   its 3 s poll loop, the Inbox row, and Today's `CapturePeek` (which reads
   `list_inbox` directly).

## Decisions (owner-approved 2026-08-01)

1. **One verb, one commitment: Forward = *take it in*, never *digest it*.**
   The Feeds `gulp` stops auto-starting processing. Both intake paths land a
   snapshot in `unprocessed`. Processing is authorized in exactly one place —
   the Inbox.
2. **Inbox is the second triage stage, and it keeps its nav slot.** It is
   where the user picks the *processing mode* (▶ Start · ⤓ Export to agent ·
   delete). Because feed volume now flows through it, it gains sections,
   provenance, and batch actions. The **badge counts only actionable items**;
   in-flight rows stay visible but uncounted.
3. **Feeds triage becomes explicit.** A `FeedEntry` is `pending` ·
   `forwarded` · `skipped`. `read` narrows to "seen" and drives row dimming
   only — opening an entry no longer removes it from the queue. Forward and
   Skip are available inline on the row, with keyboard shortcuts.

## 1. The journey, restated

| Stage | Surface | Question | Actions | Cost |
|---|---|---|---|---|
| 1 — keep? | Feeds | "is this worth my attention?" | Forward · Skip · leave pending | none |
| 2 — digest? | Inbox | "how should this be read, and is it worth the AI?" | ▶ Start · ⤓ Export to agent · delete | authorizes LLM spend |
| 3 — practice? | Snapshot ▸ Cards | "does this enter my rotation?" | accept / reject per card | the single gate (`01 §F2`) |

Ad-hoc capture (`⌘K`, share sheet, iOS Forward) skips stage 1 and lands
directly in stage 2 — the two paths now converge at the same state
(`unprocessed`) with the same next action.

## 2. Data model (`services/shared`)

`FeedEntry` gains one nullable column:

| Field | Type | Notes |
|---|---|---|
| `skipped_at` | `timestamp?` | explicit dismissal; null = not skipped |

Triage state is **derived, not stored** (consistent with subscription health,
spec 2026-07-09 decision 6):

- `forwarded` — `promoted_source_id is not null`
- `skipped` — `skipped_at is not null` (and not forwarded)
- `pending` — neither

`read_at` keeps its column and its auto-set-on-open behaviour, but its only
consumer becomes row dimming. It no longer feeds any count or filter.

One Alembic migration (add column, nullable, no backfill — existing read
entries stay `pending` and can be cleared with Skip all).

## 3. API (`services/api`)

### 3.1 Feeds

| Endpoint | Change |
|---|---|
| `POST /feed-entries/{id}/gulp` | **Drop `start_processing`.** The snapshot lands `unprocessed`. Keep the `resolve_metadata` enqueue (network-only title resolution, no LLM) so the Inbox row shows a real title rather than a host. Idempotency and the `emitted_by` back-link are unchanged. |
| `POST /feed-entries/{id}/skip` | set `skipped_at` (and `read_at` if null) |
| `POST /feed-entries/{id}/unskip` | clear `skipped_at` — returns the entry to `pending` |
| `POST /subscriptions/{id}/skip-all` | replaces `read-all`: skips every `pending` entry of the subscription |
| `GET /feed-entries`, `GET /subscriptions/{id}/entries` | `unread_only` → **`pending_only`** (default `true` — the queue is the point) |

Schema changes:

- `SubscriptionOut.unread_count` → **`pending_count`** (entries that are
  neither forwarded nor skipped).
- `FeedEntryOut`: add `skipped: bool`; keep `read: bool`; **drop
  `promoted_status`** — Feeds no longer tracks downstream state (§4).
- `GulpEntryResponse.status` stays; it is now always `unprocessed` for a fresh
  forward.

`POST /feed-entries/{id}/read` / `…/unread` stay as-is (manual seen toggle).

### 3.2 Inbox & processing

- `InboxOut` gains **`actionable_count`** = items in `unprocessed`,
  `exported`, `needs_attention`. `count` keeps its current meaning (everything
  not `ready`) and drives the "in flight" section.
- New `POST /snapshots/process-batch`, body `{ids: [uuid]}`, returning
  `{started: [uuid], skipped: [{id, reason}]}` — a 409 on one id must not fail
  the batch. Thin router, logic in `app/services/processing.py`.

Run `just gen-client` after (both TS and Swift).

## 4. Feeds UI (`apps/web/components/feeds`)

**Entry rows carry the decision.** Each row shows, on hover/focus:
`Forward` · `Skip`. Row states:

- `pending` — full-contrast title, leading dot
- `skipped` — dimmed, dot removed; an `Undo` action replaces Forward/Skip
- `forwarded` — ✓ and the title links to `/snapshots/{id}`

**Keyboard** (the list is the primary surface): `j`/`k` move, `f` forward,
`s` skip, `u` undo, `enter` opens in the reader pane.

**Filter** — the header toggle becomes `Pending` (default on) / `All`; skipped
and forwarded entries are visible under `All` for review. `Mark all read`
becomes `Skip all`, confirmed.

**Reader pane is a decision preview, not a reading surface.** It keeps
`content_html` and `Open original ↗`. After forwarding, the marker reads
**`In Inbox →`** linking to the snapshot — a single truthful statement instead
of a live status. **The 3 s `getSnapshot` poll loop and the
Processing…/In library/Needs attention markers are removed**; downstream
status belongs to Inbox and Today. Full reading happens in the snapshot
reader, which is the only reading surface.

## 5. Inbox UI (`apps/web/app/inbox`)

Three sections, in this order:

1. **Needs you** — `needs_attention` (retry · open original) and `exported`
   (⤓ upload result).
2. **To digest** — `unprocessed`. Row actions: ▶ Start · ⤓ Export job ·
   delete. Multi-select checkboxes with a sticky **`Start N`** bar calling
   `process-batch`.
3. **In flight** — `queued`, `processing`. Read-only, muted, no actions.

Rows show provenance: `source_feed.title` when the snapshot came from a
subscription (`SnapshotOut.source_feed` already carries it), otherwise the
origin host. The sidebar badge switches to `actionable_count`, so it means
"N things waiting on you" and never counts work the machine is doing.

Today's `CapturePeek` is unchanged in scope but now reads as "waiting to be
digested" rather than "processing" — acceptable, and it is the same query.

## 6. Explicitly unchanged

- The single-gate lifecycle (`ready` = in the Library) and per-card
  accept/reject as the only real gate.
- Internal naming: the promotion service stays `gulp_entry`, the endpoint
  stays `/feed-entries/{id}/gulp`; the user-facing verb stays **Forward**
  (`intake-verb` convention).
- Library, tags, the snapshot reader, the agent-job export channel.
- Subscription health, fetch pipeline, Discover.

## 7. Testing

- **api**: gulp no longer transitions to `processing`; skip/unskip round-trip;
  `pending_only` excludes skipped *and* forwarded; `skip-all` leaves forwarded
  entries alone; `pending_count` derivation; `actionable_count` excludes
  `queued`/`processing`; `process-batch` partial success.
- **web** (vitest, classic JSX transform — JSX files need `import React`):
  row action visibility per triage state, keyboard handlers, `Pending`/`All`
  filter, reader marker text after forward, Inbox sectioning and badge source.
- **worker**: untouched.

## 8. Doc amendments (fold-back)

- `01 §F1` — states: both intake paths land `unprocessed`; the manual trigger
  is universal, not capture-only.
- `01 §F6` — replace "only an explicit **Gulp** promotes one into the
  pipeline" with the two-stage model; note Forward does not start processing.
- `01 §4.3` / `§6` — Inbox described as the *processing-mode* decision with an
  actionable badge; note the open question of §11 (fold Inbox into Library)
  stays open but is now less pressing.
- `02` — `feed_entries` gains `skipped_at`; note the derived triage state.

## 9. Out of scope

- `auto_process` (still parked) and any per-subscription auto-forward rule.
- The AI-ranked Daily digest (`01 §F6` steps 3–4).
- A processing budget / quota. With decision 1 nothing runs unattended, so the
  valve is the Inbox click; a quota is only needed if `auto_process` returns.
- Undo-forward (deleting the promoted snapshot from Feeds) — delete from the
  Inbox instead.
- iOS: the client is unbuilt; it inherits this model when it reaches Forward
  (spec 2026-07-25 §4).
