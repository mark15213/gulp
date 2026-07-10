# Library redesign + source tags — design

- **Date**: 2026-07-10
- **Status**: approved (brainstorm), pending spec review
- **Scope**: `apps/web` (Library page) + `services/api` contract + `packages/api-client`. **Web-first**, no mobile.
- **Sequence**: spec 1 of 2. Spec 2 (deferred) = immersive reader redesign (collapsible sidebar, original-link, article-level chat, block "add to chat"). This doc covers **only** the Library + tagging redesign.

## Context

The Library (`apps/web/app/library/page.tsx` → `components/library/LibraryList.tsx`) is a single-column list of `ready` snapshots with a single-select row of tag filter chips derived from each item's `tags: string[]`. Tags are `SourceTag` join rows (free strings, union-under-sync — `services/shared/gulp_shared/models/source_tag.py`), and today **only user-entered capture tags exist**.

Three gaps motivate the redesign:

1. **Feed-forwarded items carry no source.** When a `FeedEntry` is promoted (`gulp_entry` in `services/api/app/services/feeds.py`), the resulting snapshot gets its `Source.emitted_by` FK set to the subscription that produced it, but the subscription's title (e.g. "HuggingFace Paper Daily") is **never exposed on the snapshot contract**, so the Library can't show or group by it.
2. **No way to categorize.** The flat single-row chip filter doesn't scale as tags/sources multiply, and there's no organizing structure.
3. **AI topic tags are wanted but unbuilt.** The owner wants future AI-assigned topic tags (e.g. "pretrain", "social news") but not built now — the UI/vocabulary should reserve space without dead AI code.

Reference specs: `2026-07-02-library-width-and-source-badges-design.md` (RowBadges precedent), `2026-07-02-single-gate-lifecycle-design.md` (`ready` == in library), `2026-07-09-subscription-system-design.md` (`emitted_by`, FeedEntry, promotion).

## Goals

- Feed-forwarded library items automatically surface their **source feed** as a first-class, filterable facet.
- Replace the flat chip row with a **left tag sidebar** grouping facets by kind: **Sources**, **Mine**, **Topics**.
- Let the user **add/remove their own tags** on a library item.
- **Reserve** UI + vocabulary space for future AI topic tags with **no** model code, **no** schema migration this round.

## Non-goals (out of scope this spec)

- AI tagging logic / worker step / the tag-`origin` column (arrives with the future AI-tagging spec).
- Multi-select / boolean (AND/OR) filtering — **single-select** only this round.
- Grouped-section list view (facets are a *filter*, not a re-layout).
- All reader/reading-page changes (spec 2).
- Knowledge Bases / Concept browsing (parked).

## Design

### A. Facet model — two backed by data, one reserved

Three sidebar facets. Because AI topics are **placeholder-only**, we deliberately do **not** add a general tag-`origin` column now. Source vs. user tags are distinguished by *where the data already lives*:

| Facet | Source of truth | Editable? | This spec |
|---|---|---|---|
| **Sources** | derived from `Source.emitted_by → subscription Source.title` | read-only (auto) | ✅ live |
| **Mine** | existing `SourceTag` rows (`tags: string[]`) | user add/remove | ✅ live |
| **Topics** | — (future AI `SourceTag` rows behind an `origin` column) | — | ⛔ placeholder ("coming soon", disabled) |

Deriving **Sources** from the already-existing `emitted_by` link means: no new table, no column, no backfill, and the source label **stays in sync** if the feed is renamed. Manual captures (no `emitted_by`) have no source and simply don't appear under Sources.

### B. Backend (additive — no DB migration)

1. **Expose the source feed on the contract.** `SnapshotOut` (Pydantic in `services/api/app/schemas/capture.py`; generated mirror in `packages/api-client/src/schema.gen.ts`) gains:

   ```
   source_feed: { id: UUID, title: str } | None
   ```

   Populated in `to_out()` (`services/api/app/services/snapshots.py`) by resolving `source.emitted_by` → the subscription `Source.title`. Null when `emitted_by` is null. Batch the lookup in `list_library` to avoid N+1 (one `IN (...)` query keyed by the set of `emitted_by` ids).

2. **User-tag add/remove endpoints** (extend the existing snapshots router):
   - `POST /snapshots/{id}/tags` body `{ tag: string }` → create (or un-soft-delete) a `SourceTag(source_id, tag)`; idempotent; returns the item's updated `tags`.
   - `DELETE /snapshots/{id}/tags?tag=<value>` → soft-delete the matching `SourceTag` (set `deleted_at`). Query param (not path) to avoid URL-encoding tags with slashes/special chars.

   Service helpers live beside `_tags_for` in `services/api/app/services/snapshots.py`. Both enforce owner scoping. These are **user** tags only; source/topic tags are not user-writable.

3. **Regenerate the client** with `just gen-client` after the contract change (adds `source_feed` + the two calls to `packages/api-client`). New api-client functions: `addSnapshotTag(id, tag)`, `removeSnapshotTag(id, tag)`.

> Note: `gulp_entry` is intentionally **not** changed to write a source `SourceTag` — the source facet is derived, not materialized. (Feed-forwarded items still reach the Library only at `status=ready`, per the single-gate lifecycle; the intake verb is "Forward", the internal action stays `gulp_entry`.)

### C. Web UI

**Layout** — the Library page becomes a two-pane surface inside the main content area; the global nav rail (`components/shell/Sidebar.tsx`) is unchanged:

```
[ global nav ] │ [ tag sidebar ~200px ]        │ [ list — max-width var(--measure) ]
  Today          Sources                          > Attention Is All You Need
  Inbox           HF Paper Daily  (12)               arxiv.org · «HF Paper Daily» · to-read ×  +
  Library ◀       Hacker News     (5)             > The Bitter Lesson
  Feeds          Mine                                incompleteideas.net · fav ×  +
                  to-read         (4)             > FlashAttention
                  fav             (2)                arxiv.org · «HF Paper Daily»
                 Topics · coming soon
                  ─ disabled ─
```

- `apps/web/app/library/page.module.css` `.page` changes from a 920px single column to a horizontal flex: a sticky `aside` (tag sidebar) + a `section` (the list, capped at `var(--measure)` ≈ 720px). Container max-width bumped (~1040px) to fit both.
- **Sidebar** groups render per-entry **counts computed client-side** from the fetched items (same approach as today's chips — no new aggregation endpoint). **Single-select**: an `activeFilter: { kind: "source" | "tag", value: string } | null`; clicking a Source or Mine entry sets it, "All" (top) or re-clicking clears. The **Topics** group renders but is disabled with a "coming soon" affordance.
- **Rows** keep glyph · title · meta · `RowBadges` (media/cards, unchanged) · delete. The meta area gains:
  - a **source chip** (read-only; clicking filters to that feed) when `source_feed` is set;
  - **removable user-tag chips** (`×` → `removeSnapshotTag`) and a subtle **`+`** control (→ `addSnapshotTag`), with optimistic local update + rollback on failure (mirrors the reader's optimistic block edits).
- **Empty states**: no items → existing copy; a filter with zero matches → "Nothing under {name}."
- **Responsive**: below ~720px the sidebar collapses to a togglable drawer / top control (finalized in the plan).

**Component decomposition** (keep files focused):
- `components/library/LibraryTagSidebar.tsx` (+ `.module.css`, `.test.tsx`) — presentational: `{ groups, activeFilter, onSelect }`.
- `components/library/RowTags.tsx` (+ `.module.css`) — source chip + user-tag chips + add control for one row.
- `LibraryList.tsx` — owns `activeFilter` state, derives facet groups (extract a `useLibraryFacets(items)` helper), composes sidebar + rows. `RowBadges.tsx` unchanged.

**Data flow**: `library/page.tsx` (server) still fetches once via `getLibrary()`; `LibraryList` (client) computes facets + filters in memory; tag mutations call the api-client and update local item state optimistically.

### D. AI-topic seam (reserved, not built)

The sidebar already renders heterogeneous facet groups and rows already render a mixed chip list, so topic tags slot in without structural change. The **future** AI spec will: add the `origin` column to `SourceTag` (or a topic-tag mechanism), add a worker `tag_snapshot` step, extend the contract to carry per-tag origin, and flip the **Topics** group from placeholder to live. This spec ships none of that — only the disabled group and the layout that will host it.

## Docs to amend (owner works docs-first)

- `docs/01-interaction-spec.md §F3` — Library browse: by **source** + tag; left tag sidebar; AI-topic reserved.
- `docs/03-ui-system.md §7.3` — sidebar facets (Sources/Mine/Topics) supersede/augment the single chip row; source chip on the object card meta row.
- `docs/02-data-model.md §4.3` — note the **Sources** facet is *derived* from `emitted_by` (no materialized source tag, no `origin` column yet).

## Testing

- **Web** (vitest, classic-JSX → `import React` in JSX files): `LibraryTagSidebar` grouping + counts + single-select; `RowTags` add/remove (optimistic + rollback); `LibraryList` filter-by-source and filter-by-tag; existing `LibraryList.test.tsx` / `RowBadges.test.tsx` updated.
- **API** (pytest per-package — `cd services/api && uv run pytest`): `to_out` populates `source_feed` from `emitted_by` (and null when absent); `list_library` batches the lookup (no N+1); add/remove tag endpoints (idempotent add, soft-delete, owner scoping, updated `tags`).
- **Gate**: `just lint` green before commit; regenerate client with `just gen-client` (ignore the 2 pre-existing `schema.gen.ts` dup-identifier `tsc` warnings).

## Rollout

Purely additive: new nullable contract field + two new endpoints + web changes. No migration, no backfill. Existing captures render unchanged (no source chip, existing user tags editable).
