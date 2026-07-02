# Library width fix & per-row source badges

Date: 2026-07-02
Status: Approved (design); pending implementation
Scope: `apps/web` only — the `/library` shelf. No backend, no API contract
change, no `just gen-client`.

## Goal

Two owner-requested fixes to the Library (`/library`) shelf:

1. **Width (`比例`).** The content column is too narrow — it reads as the wrong
   proportion for a shelf.
2. **Per-row source badges.** On the catalog rows, surface each item's
   **content form** (`media_type`) and **cards generation status**
   (`cards_status`) as inline badges.

Both are client-only: every field already ships on the library item via
`@gulp/api-client`.

## Diagnosis (why the width is "wrong")

`app/library/page.module.css` sets `max-width: 720px`. But docs/03 §5.2 (line
269) defines `~720px` as the **Reader / content column** — the measure for
*reading one piece*. The Library is a **shelf/list**, which docs/03 §6.1 calls
*"compact rows, multi-column"* — a wider workbench column. Today (`/`) already
uses `920px`; Inbox is full-width. There is no shared width token, so the pages
drifted and Library inherited the reader measure.

## Decisions locked in

- **Width → 920px, in place (Approach A).** Change Library's
  `page.module.css` `max-width: 720px → 920px` to match Today. Owner chose the
  one-line fix over introducing a shared `--content-w` token, to keep the change
  off `packages/ui` (a second agent is editing the repo concurrently). A shared
  token can come later; it is explicitly out of scope here.
- **Two badges only: `media_type` + `cards_status`.** `report`/pack status is
  dropped — the pipeline persists the pack *before* flipping the snapshot to
  `ready` (`services/worker/app/pipeline/run.py:74‑75`), and the Library only
  lists `ready` items, so a pack is **always `ready`** here → no signal. Origin
  host, `kind`, and `captured_via` are out of scope this round.
- **Display only, no filtering.** Badges are trailing, per-row indicators. The
  existing content-`tags` filter chips at the top of the list are unchanged.
- **Reuse the `StateChip` pill language** (`components/ui/StateChip`): tinted
  pill + label, never color-only (accessibility invariant kept).

## The badges

Trailing badges on each `LibraryList` row, right of the title/meta block:

```
[▣]  How Transformers Work                    Article   Cards…
     arxiv.org · ml · attention

[▣]  Notes on Spaced Repetition               Note
     medium.com · learning

[▣]  Deep Dive Podcast Ep. 12                 Podcast   ⚠ Cards
     youtube.com
```

- **media_type badge** — a neutral (non-mastery-color) pill with the label:
  `Article / PDF / Video / Podcast / Note / Screenshot / Audio / Webpage`.
  Rendered only when `media_type` is non-null.
- **cards badge** — a state pill:
  - `generating` → in-progress ("Cards…"), blue accent.
  - `failed` → attention ("⚠ Cards").
  - `ready` → subtle "✓ Cards" (quiet; present but not noisy — most shelf items
    are ready).
  - `null` → nothing.

## Components & files

All under `apps/web`:

- `app/library/page.module.css` — `max-width` 720 → 920.
- `components/library/RowBadges.tsx` (new) — renders the media_type + cards
  badges for one `Snapshot`. Pure, prop-driven (`media_type`, `cards_status`).
- `components/library/RowBadges.module.css` (new) — neutral media_type pill +
  cards state variants, built on the `StateChip` sizing tokens (`--space-2`,
  `--radius-pill`, 12px/16px type).
- `components/library/LibraryList.tsx` — render `<RowBadges … />` trailing in
  each `.row`; adjust `.row` to space-between so badges sit on the right.
- `components/library/LibraryList.module.css` — row layout tweak for the
  trailing badge cluster.
- `components/library/LibraryList.test.tsx` — extend (see Testing).

## Component boundaries

- **`RowBadges`** — input: `{ media_type, cards_status }` from a `Snapshot`.
  Output: an inline badge cluster. No data fetching, no routing, no knowledge of
  the list. Testable in isolation.
- **`LibraryList`** — unchanged responsibilities (filter chips + rows); gains one
  child per row. The width fix lives entirely in CSS.

## Testing (TDD)

Extend `LibraryList.test.tsx` / add `RowBadges` coverage:

1. `media_type: "video"` → a "Video" badge renders; `media_type: null` → no
   media_type badge.
2. `cards_status: "generating"` → "Cards…" badge; `"failed"` → attention badge;
   `"ready"` → subtle "✓ Cards"; `null` → no cards badge.
3. Existing LibraryList behavior (tag filter chips, empty state, row links) still
   passes.

## Out of scope

- Any backend / schema / `api-client` change.
- A shared `--content-w` token or touching Today/Inbox widths.
- `report`/pack, host, `kind`, `captured_via` badges; badge-based filtering.
