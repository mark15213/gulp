# Inbox — one intake surface, two-stage triage

Date: 2026-08-01
Status: Approved (design); pending implementation
Scope: `services/shared` (one column + migration), `services/api` (feeds ·
inbox · processing), `apps/web` (Feeds workspace + Inbox merge into one
surface), plus doc amendments to `docs/01·02·03`.

## Goal

Fold **Feeds** into **Inbox** and make the triage semantics explicit. Today
there are two "what's new" surfaces with incompatible rules, and neither can
express "seen it, don't want it". After this spec there is one intake surface
and one sentence that explains it:

> Things flow in → you decide whether to keep → what you keep, you decide
> whether to digest → what's digested lands in the Library.

**Merging the surfaces is not merging the data model.** `FeedEntry` stays a
lightweight, prunable row; only an explicit Forward creates an owned
`Source(kind=snapshot)`. The 2026-07-09 decision — "the library is never
flooded by a noisy feed" — is about data and is preserved intact.

## The defects being fixed (observed 2026-08-01)

1. **"Forward" means two different things.** From the Capture sheet it creates
   an `unprocessed` snapshot (`services/api/app/services/capture.py`). From the
   Feeds reader it creates the snapshot *and* calls `start_processing`
   (`services/api/app/services/feeds.py`). The high-volume, low-deliberation
   path spends AI automatically while the deliberate path asks for a second
   click — backwards, and it quietly voids the manual-trigger cost control of
   `01 §F1 step 5`.
2. **Two inboxes.** The sidebar offers `Feeds` and `Inbox` as separate places
   to check for new things, with different unread semantics (per-entry dots vs
   a badge count). `01 §11` already flags this as an open question.
3. **Inbox means "not ready yet", not "your move".** `_TODO` includes `queued`
   and `processing` (`services/api/app/services/inbox.py`) — states in which
   the user can do nothing — so the badge over-counts, and feed-forwarded
   items flash through it on the way to the Library.
4. **Feeds has no *skip*.** The only way to clear an entry is `read`, set
   automatically the instant the entry is opened (`FeedsWorkspace.tsx`).
   Anything glanced at leaves the queue whether or not a decision was made;
   `read` carries both "I opened this" and "I dealt with this".
5. **The decision lives in the third pane.** `Forward` exists only in
   `EntryReader`; rows have no inline action and there is no keyboard path.
6. **Downstream status is mirrored three times** — the Feeds ✓ marker with its
   3 s poll loop, the Inbox row, and Today's `CapturePeek`.

## Decisions (owner-approved 2026-08-01)

1. **One verb, one commitment: Forward = *take it in*, never *digest it*.**
   The feed promotion stops auto-starting processing. Both intake paths land a
   snapshot in `unprocessed`. Processing is authorized in exactly one place.
2. **Feeds folds into Inbox.** One surface at `/inbox`, organized **by stage,
   not by time**. Sidebar becomes `Today · Inbox · Library` (+ Settings).
3. **Subscription management stays in the left pane** of that surface (add ·
   mute · unsubscribe · Discover), doubling as the source filter.
4. **Feeds triage becomes explicit.** A `FeedEntry` is `pending` ·
   `forwarded` · `skipped`. `read` narrows to "seen" and drives row dimming
   only — opening an entry no longer removes it from the queue.
5. **The row title is the way into the reader, and the belt finishes on
   screen.** Clicking any row's title opens `/snapshots/{id}` at whatever
   status it holds; a snapshot started from **Kept** stays on the surface as
   `Ready · Read →` when it lands, instead of vanishing into the Library
   (§4.6).

## 1. The journey, restated

| Stage | Where | Question | Actions | Cost |
|---|---|---|---|---|
| 1 — keep? | Inbox ▸ **New** | "is this worth my attention?" | Forward · Skip · leave pending | none |
| 2 — digest? | Inbox ▸ **Kept** | "how should this be read, and is it worth the AI?" | ▶ Start · ⤓ Export to agent · delete | authorizes LLM spend |
| 3 — practice? | Snapshot ▸ Cards | "does this enter my rotation?" | accept / reject per card | the single gate (`01 §F2`) |

Ad-hoc capture (`⌘K`, share sheet, iOS Forward) skips stage 1 and lands
directly in **Kept** — the two paths converge on one state (`unprocessed`)
with one next action. Pressing `⌘K` *is* the answer to stage 1's question, so
there is no separate section for self-captured items; they sit among the
feed-forwards they are indistinguishable from, and the **Captured** source
bucket (§4.1) is the one-click "what did I send myself from my phone?" view.
Splitting **Kept** by origin would re-cut the surface by *source* immediately
after merging it by *stage* — the rail owns source, the sections own stage.

**Forward moves a row down one section.** A pending entry leaves **New** (it
is no longer pending) and its snapshot appears in **Kept**. No row is rendered
twice, and no cross-surface status mirroring is needed — which is why
`promoted_status` and the poll loop are deleted (§3.1, §4.4).

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
consumer becomes row dimming ("seen"). It no longer feeds any count or filter.

One Alembic migration (add column, nullable, no backfill — existing read
entries stay `pending` and can be cleared with **Skip all**).

## 3. API (`services/api`)

### 3.1 Feeds

| Endpoint | Change |
|---|---|
| `POST /feed-entries/{id}/gulp` | **Drop `start_processing`.** The snapshot lands `unprocessed`. Keep the `resolve_metadata` enqueue (network-only title resolution, no LLM) so the Kept row shows a real title rather than a host. Idempotency and the `emitted_by` back-link are unchanged. |
| `POST /feed-entries/{id}/skip` | set `skipped_at` (and `read_at` if null) |
| `POST /feed-entries/{id}/unskip` | clear `skipped_at` — returns the entry to `pending` |
| `POST /subscriptions/{id}/skip-all` | replaces `read-all`: skips every `pending` entry of the subscription |
| `GET /feed-entries`, `GET /subscriptions/{id}/entries` | `unread_only` → **`pending_only`** (default `true` — the queue is the point) |

Schema changes:

- `SubscriptionOut.unread_count` → **`pending_count`** (entries neither
  forwarded nor skipped).
- `FeedEntryOut`: add `skipped: bool`; keep `read: bool`; **drop
  `promoted_status`**.
- `GulpEntryResponse.status` stays; it is now always `unprocessed` for a fresh
  forward.

`POST /feed-entries/{id}/read` / `…/unread` stay (manual seen toggle).

### 3.2 Inbox & processing

- `GET /inbox` gains optional filters mirroring the left pane:
  `emitted_by: uuid?` (snapshots forwarded from that subscription) and
  `ad_hoc_only: bool` (`emitted_by is null` — the **Captured** bucket). They
  are mutually exclusive; sending both is a 422.
- `InboxOut` gains **`actionable_count`** = `unprocessed` + `exported` +
  `needs_attention`, computed **unfiltered** (the badge must not change when
  the user filters by source). `count` keeps its current meaning.
- New `POST /snapshots/process-batch`, body `{ids: [uuid]}`, returning
  `{started: [uuid], skipped: [{id, reason}]}` — a 409 on one id must not fail
  the batch. Thin router; logic in `app/services/processing.py`.

Run `just gen-client` after (TS + Swift).

## 4. The merged surface (`apps/web/app/inbox`)

Three panes. `/feeds` and `/feeds/discover` become permanent redirects to
`/inbox` and `/inbox/discover`.

```
Inbox
├ left    Sources: All · <subscription> … · Captured      (+ Add · Discover)
├ middle  four stage sections (below)
└ right   decision preview
```

### 4.1 Left pane — sources

The existing `SubscriptionList`, plus a **Captured** row for ad-hoc intake.
Each subscription row keeps health dot, mute, unsubscribe, refresh, and shows
**`pending_count`** in a subdued mono numeral (not the sidebar badge — §4.5).
`Add` and `Discover` stay here. Selecting a source filters **every** section:
`New` by `subscription_id`, the snapshot sections by `emitted_by` (or
`ad_hoc_only` for **Captured**, which hides `New` — ad-hoc intake has no
stage-1 rows).

### 4.2 Middle pane — four stage sections

| Section | Source | Rows | Actions |
|---|---|---|---|
| **New** | `GET /feed-entries?pending_only` | pending feed entries | Forward · Skip |
| **Kept** | `GET /inbox` → `unprocessed` | snapshots awaiting digest | ▶ Start · ⤓ Export job · delete; multi-select + sticky **`Start N`** |
| **Needs you** | `GET /inbox` → `needs_attention`, `exported` | failures and export-awaiting-upload | retry · open original · ⤓ upload result |
| **In flight** | `GET /inbox` → `queued`, `processing` | work the machine owns | none (read-only, muted) — except the session-scoped `Ready · Read →` last frame, §4.6 |

**No new contract shape is required** — two existing endpoints, four rendered
groups. Sections are collapsible and their collapsed state persists locally,
so a "process only, don't scan today" visit is one click away.

Rows carry provenance: `source_feed.title` when present, otherwise the origin
host (`SnapshotOut.source_feed` already ships it).

Ordering within a section is newest-first, as today. **New** keeps the
existing entry pagination; the snapshot sections stay unpaginated at v1 scale.

### 4.3 Row states & keyboard

Entry rows (New): `pending` = full-contrast title + leading dot;
`skipped` = dimmed, dot removed, `Undo` replaces the actions;
`forwarded` entries are absent from New and reviewable under the **All**
filter (§4.4).

Keyboard on the middle pane: `j`/`k` move the cursor, `enter` opens the row in
the preview pane, `o` opens it properly (the reader for a snapshot, the
original for an entry), `f` forwards, `s` skips, `u` undoes a skip. `f`/`s`/`u`
are inert on snapshot rows — those decisions belong to stage 1.

*(Settled during implementation: `enter` and `o` are separate. Folding "open
the reader" into `enter` would make the cheapest key the one that navigates
away from the list, which is backwards for a scan-and-keep loop.)*

### 4.4 Right pane — decision preview, not a reader

For an **entry**: the feed's `content_html` plus `Open original ↗`. For a
**snapshot**: title, origin, note, tags, and — for `needs_attention` — the
failure reason. Full reading always happens in the snapshot reader at
`/snapshots/{id}`; this pane exists to answer "keep or not / digest or not" in
about ten seconds.

**Removed:** the 3 s `getSnapshot` poll loop, the `Processing…` /
`In library` / `Needs attention` markers, and the `In Inbox →` link — the
forwarded item is now visibly one section below, so nothing needs mirroring.

A per-subscription filter toggle offers **Pending** (default) / **All**; under
`All`, skipped and forwarded entries are visible for review. `Mark all read`
becomes **`Skip all`**, confirmed.

### 4.5 Badge

The sidebar badge shows `actionable_count` — **Kept + Needs you**. It never
counts `In flight` (nothing to do) and never counts pending feed entries
(which would make it a three-digit number by the second week and mean
nothing). Stage-1 volume is legible where it belongs: per-source counts in the
left pane.

Today's `CapturePeek` is unchanged in scope; it now reads as "waiting to be
digested" rather than "processing", from the same query.

### 4.6 Handing off to the reader

Deep reading and the article conversation live where they already do —
`/snapshots/{id}` (`ReaderLayout` · `PackReport` · `ChatPanel`, spec
2026-07-10: collapsible chat, `[[block:ID]]` citations, per-block *add to
chat*). This surface must never grow a second reader.

**The row title is the link.** Clicking a **snapshot** row's title — in any
section, at any status — opens the reader. An **entry** has no snapshot yet, so
its title opens the decision preview instead; the rule is "the title takes you
to the fullest view this thing has". That works because the reader page is already
status-complete: `unprocessed` shows Start, `queued`/`processing` shows the
skeleton plus `ProcessingPoller`, `needs_attention` shows the banner, `ready`
shows the pack. So "open it and watch the pack fill in, then start reading and
chatting" is one continuous path that never returns to the list. The buttons
on a row are the shortcut for *staying* in the list — what you want when
processing ten at once.

**The belt finishes on screen.** A snapshot the user started in this session
stays in **In flight** when it reaches `ready`: the row turns full-contrast,
its chip reads `ready`, and its single action is **`Read →`**. Without this
the item the user just asked for silently disappears and has to be hunted for
in the Library.

- **Session-scoped**, deliberately. The client remembers only the ids it
  started on this mount; a reload drops them and the items live in the Library
  like anything else. It never becomes a fifth backlog.
- **It costs one poll.** While the started-id set is non-empty the client
  polls `GET /snapshots/{id}` for those ids (the existing endpoint, the same
  approach `ProcessingPoller` already takes) and stops when each reaches a
  terminal status. This is the one thing this spec *adds* after deleting the
  Feeds poll loop (§4.4), and the distinction is the point: **the surface that
  owns a state polls it; no surface mirrors another's.**

**"Packs I haven't read yet" is a Library concern, not a fifth section.** An
unread-pack queue in Inbox would rebuild the second unread queue this spec
exists to remove, and would return the Library to being a graveyard. A pack
the user hasn't read is `New` on the mastery ladder (`01 §F7`), so it belongs
behind a Library filter chip when mastery chips ship with S5.

## 5. Explicitly unchanged

- The single-gate lifecycle (`ready` = in the Library) and per-card
  accept/reject as the only real gate.
- `FeedEntry` stays lightweight and prunable (90-day cron); only Forward
  creates an owned Source.
- Internal naming: the promotion service stays `gulp_entry`, the endpoint
  stays `/feed-entries/{id}/gulp`; the user-facing verb stays **Forward**.
- Library, tags, the agent-job export channel, subscription health, the fetch
  pipeline, Discover's catalog search.
- **The reader and its chat** (`/snapshots/{id}`) — untouched by this spec.
  Only the ways *in* to it are stated (§4.6); nothing about the pack, the
  block editing, or the conversation changes.

## 6. Testing

- **api**: gulp no longer transitions to `processing`; skip/unskip round-trip;
  `pending_only` excludes skipped *and* forwarded; `skip-all` leaves forwarded
  entries alone; `pending_count` derivation; `actionable_count` excludes
  `queued`/`processing` **and ignores the source filter**; `emitted_by` /
  `ad_hoc_only` mutual exclusion; `process-batch` partial success.
- **web** (vitest, classic JSX transform — JSX files need `import React`):
  section assignment by status, row actions per triage state, keyboard
  handlers, source filter driving all sections (including Captured hiding
  New), collapsed-section persistence, badge reads `actionable_count`, row
  titles link to `/snapshots/{id}` in every section, and the §4.6 last frame —
  a started id flips to `Ready · Read →` in place, is not counted by the
  badge, and is forgotten on remount.
- **worker**: untouched.

## 7. Doc amendments (fold-back)

- `01 §F1` — both intake paths land `unprocessed`; the manual trigger is
  universal, not capture-only.
- `01 §F6` — replace "only an explicit **Gulp** promotes one into the
  pipeline" with the two-stage model; Feeds is no longer a surface, it is the
  `New` section and the source pane of Inbox.
- `01 §F2` — note that the Snapshot detail reader is reachable from any Inbox
  row at any status (§4.6), and that reading + chat never happen on the intake
  surface.
- `01 §4.3` — web nav becomes `Today · Inbox · Library · Settings`; Inbox
  described as the whole intake surface with an actionable badge.
- `01 §6` — screen inventory: merge the `Feeds` row into `Inbox`.
- `01 §11` — the open question ("keep Inbox, or fold it into Library?") is
  **answered in the other direction**: Feeds folds into Inbox; Library stays a
  clean shelf of `ready`.
- `02` — `feed_entries` gains `skipped_at`; note the derived triage state.
- `03 §5.2` / `§7.11` / `§7.12` — sidebar list drops `Feeds`; §7.11 is rewritten
  as the Inbox surface (sources pane · stage sections · decision preview) and
  keeps the digest half deferred.

## 8. Out of scope

- `auto_process` (still parked) and per-subscription auto-forward rules. If
  Kept turns out to be a chore at real feed volume, the follow-up is
  **genre-based auto-start** (article/note already run a zero-LLM pipeline, so
  only papers truly need the click) — deliberately not in this slice.
- The AI-ranked Daily digest (`01 §F6` steps 3–4).
- A processing budget/quota: with decision 1 nothing runs unattended, so the
  valve is the Start click.
- Undo-forward from the New section — delete the snapshot from Kept instead.
- **An unread-packs queue in the Inbox** (§4.6) — it belongs behind a Library
  mastery filter, and building it here would undo the merge.
- A separate section for self-captured items (§1) — the **Captured** source
  bucket covers finding them.
- iOS: the client is unbuilt and stays consumption-only; it inherits this
  model when it reaches Forward (spec 2026-07-25 §4).
