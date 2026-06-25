# S2 Web Reading Slice — design

*Gulp · feature design · 2026-06-24 build · brainstorm output*

> The user-visible surface for S2: expose the generated **Knowledge Pack** over the API and let the web client **read** it and **trigger** processing. Builds on the merged S2 backend (Plans 1–3) and the manual-trigger model (`docs/subsystems/S2-processing-design.md` §2.4/§3). Reading-UI is otherwise 03/S3 territory; this is the minimal slice that makes a captured snapshot's report visible.

## 1. Scope

- **In:** (A) a pack API endpoint + regenerated `@gulp/api-client`; (B) a web snapshot-detail page that renders the re-authored report + facets with `processing`/`ready`/`needs_attention` states; (C) a **▶ Start** control (Inbox row + detail) so `unprocessed`/`needs_attention` captures get processed, and Inbox rows link to the detail page.
- **Out (deferred):** card UI (cards aren't generated yet); per-block citation chips / "open original to a region" (anchors are null in v1); on-demand figures and anchored chat (S6); rich reading polish / page-through animations; mobile parity; editing/curation of pack elements (S3 deep curation). The richer reading experience the owner described earlier lands later.

## 2. Architecture

Two plans, **API-first** (the web depends on the pack being exposed).

### Plan A — API: expose the pack
- `services/api/app/services/pack.py` — `pack_out(db, snapshot_id) -> PackOut | None`: load the snapshot's `KnowledgePack`; if absent, return `None`. Serialize: `status`, `summary`, `background`, `confidence`, ordered `sections` (`PackSection` by `position`) each with ordered `blocks` (`PackBlock` by `position`: `type`, `content`, `anchor_id`), and `facets` (`PackElement`: `element_type`, `text`).
- `services/api/app/schemas/pack.py` — `PackOut`, `PackSectionOut`, `PackBlockOut`, `PackFacetOut` (Pydantic; become the OpenAPI contract).
- `services/api/app/routers/pack.py` — `GET /snapshots/{snapshot_id}/pack` → `PackOut`; **404** when the snapshot is missing / foreign-owned / soft-deleted, or has no pack yet (`unprocessed`/`processing`/`needs_attention`). Owner-scoped like the other snapshot routes. Registered in `app/main.py`.
- `just gen-client` regenerates `packages/api-client` (`schema.gen.ts`); add a `getPack(id)` helper that returns `null` on 404 (the detail page gates on `snapshot.status == ready` before calling it, so 404 is the normal "not ready" path).

### Plan B — Web: the reader + Start control (layout **A**, report-first)
- `apps/web/app/snapshots/[id]/page.tsx` (RSC) — fetch `getSnapshot(id)` (owner-scoped; 404 → Next `notFound()`), branch on `status`:
  - `unprocessed` → title + source line + **▶ Start**.
  - `processing` → report **skeleton** + `ProcessingPoller`.
  - `ready` → fetch `getPack(id)`; render the **report as the main column** + a **facet rail** + a **Pack ⇄ Original** toggle.
  - `needs_attention` → "Couldn't fully read this" banner + **▶ Retry** + Open original.
- Components (`apps/web/components/snapshot/`):
  - `PackReport` — renders `sections → blocks` (heading + prose/callout/quote) as the reading column.
  - `FacetRail` — facets grouped by `element_type` (Key terms · People/orgs · Claims · Counter-views · Connections); `key_term`/`person_org` shown as chips, claims/counter-views/connections as short lines.
  - `ReaderToggle` (client) — Pack ⇄ Original; Original renders `snapshot.content_body`.
  - `StartButton` (client) — `POST /snapshots/{id}/process` via a new `startProcessing(id)` client helper; optimistic → "Processing", then `router.refresh()`.
  - `ProcessingPoller` (client) — while `processing`, poll `getSnapshot(id)` every ~3s; on flip to a terminal status (`ready`/`needs_attention`) call `router.refresh()` so the RSC re-renders. Bounded: stop after ~2 min or on terminal status.
- `InboxRow` — link the title to `/snapshots/[id]`; add a one-click **▶ Start** for `unprocessed`/`needs_attention` rows (client island; the rest of the row stays server-rendered).
- Reuse `@gulp/ui` primitives (`StateChip` for status, `Button`) and CSS modules; no new tokens (`apps/web/CLAUDE.md`). Talk to the backend only through `@gulp/api-client`.

## 3. Data flow (the async gap)

```
capture → unprocessed → [▶ Start] → POST /process → processing
   detail page: skeleton + ProcessingPoller (poll getSnapshot ~3s)
   worker finishes → status ready → poller router.refresh() → RSC fetches getPack → report renders
   (failure → needs_attention → banner + ▶ Retry)
```

Light client polling (chosen over manual refresh) so captures auto-appear when ready.

## 4. Error / empty states

- Snapshot not found / not owned → 404 page (`notFound()`).
- `GET /pack` 404 while `ready` (race: pack deleted) → treat as "no pack" / show a soft empty state, don't crash.
- `needs_attention` → non-destructive amber banner + Retry (re-Start) + Open original (`origin_url`), mirroring `docs/03 §8`.
- Start on a non-startable status (e.g. already `processing`) → the API returns 409; the button surfaces a quiet "already processing" and refreshes.

## 5. Testing

- **API (pytest):** `GET /snapshots/{id}/pack` returns `PackOut` for a `ready` snapshot with a pack (sections/blocks ordered, facets present); **404** when no pack; **404** for unknown/foreign id (owner scope).
- **Web (vitest + Testing Library):** `PackReport` renders sections/blocks from a mock `PackOut`; `FacetRail` groups facets by type; `ReaderToggle` switches Pack/Original. `StartButton`/`ProcessingPoller` get light interaction tests (mock the client helpers). Repo already has vitest + jsdom configured.
- Gate: `uv run pytest` (api) green; `pnpm --filter @gulp/web test` + `tsc` green. (Repo-wide ruff/mypy/eslint carry accepted pre-existing debt.)

## 6. Decomposition (the plans)

1. **Plan A — Pack API + client:** `PackOut` schemas, `pack_out` serializer, `GET /snapshots/{id}/pack`, register router, regenerate `@gulp/api-client`, add `getPack`/`startProcessing` helpers. Independently testable (pytest + the generated client compiles).
2. **Plan B — Web reading detail + Start:** the `[id]` page, `PackReport`/`FacetRail`/`ReaderToggle`/`StartButton`/`ProcessingPoller`, Inbox row link + Start. Depends on A.

## 7. Open / deferred

- Cards section in the reader (when card generation lands).
- Per-block citation chips + region "open original" (when anchors are populated; S3/S6 consumers).
- Deep curation (keep/dismiss facets, edit blocks) — S3.
- Mobile parity (`Read · Pack · Cards` segmented) — later per the web-first sequencing.
