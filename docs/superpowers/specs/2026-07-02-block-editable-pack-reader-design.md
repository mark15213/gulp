# Block-Editable Pack Reader — Notion/Jupyter-style redesign

Date: 2026-07-02
Status: Draft (design); pending user review → implementation plan
Scope: The knowledge-pack reading experience across `apps/web`,
`packages/api-client`, `services/api`, `services/shared`, and `services/worker`.

## Goal

Redesign how a knowledge pack is viewed from the inbox. Today the pack reader
(`apps/web/components/snapshot/PackReport.tsx`) is a **read-only, single-column**
render that the owner finds visually flat. Turn it into a **block-wise,
editable document** — closer in feel to Notion / a Jupyter notebook — where the
owner can:

1. **Read** a visually refined, systematic report (the current render, redone to
   the `docs/03` web register).
2. **Edit** each block in place with a type-appropriate editor.
3. **Add / delete / reorder** blocks.
4. **Chat per block:** open a right-side panel to ask grounded questions about a
   specific block, with the conversation persisted.

This realizes capability the S2 design (`docs/subsystems/S2-processing-design.md`
§3.3 "living document", §3.5 "report prose … editable in web deep-curation",
§3.4 "pop chat at a hard spot", §5.2 "right panel") anticipated but deferred.

The pack stays a **structured, schema-validated contract** (`docs/04 §2.5`) — the
blocks remain typed structured data (`prose | formula | table | figure | list`),
not a rich-text document.

## Decisions locked in

- **One design, three implementation phases.** This spec covers the whole
  experience; the implementation plans are sequenced Phase 1 → 2 → 3 and can stop
  between phases. Phase 1 = visual redesign + block scaffolding; Phase 2 =
  editing + add/delete/reorder; Phase 3 = per-block chat.
- **Editing model: lightweight per-type editors** (not a rich-text block-editor
  framework). Each block enters an edit mode with an editor matched to its type.
  Keeps the existing structured contract; no heavy new dependency (BlockNote /
  TipTap / Lexical are explicitly **not** adopted).
- **Layout: docked right-panel workbench** (`docs/03 §5.2`). Center reader +
  a dismissible right panel (360–420px) for the per-block chat. Responsive: at
  `<1280px` the panel becomes a slide-over overlay (`docs/03 §5.2` breakpoints).
- **Add block: `+` hover insert** between blocks with a small type picker;
  **delete / reorder** live on a per-block hover toolbar (`⋯` menu +
  drag handle).
- **Frontend state: client island, no new state library** (Decision A1). The
  pack reader becomes a client component holding pack state; mutations call REST
  endpoints and update local state optimistically (rollback + toast on failure).
  Server components keep doing the initial fetch. No React Query / SWR / server
  actions added.
- **Chat: API-layer synchronous LLM call** (Decision B1). The provider-agnostic
  LLM layer moves from `services/worker/app/llm/` to `services/shared` so both
  the API and the worker use it; a chat request calls the LLM synchronously and
  returns the full answer (loading state in the UI; SSE streaming is a later
  enhancement). Chat is a "user is waiting" interaction, distinct from capture,
  so `docs/CLAUDE.md` rule 4 (capture must not block on AI) does not apply.
- **Chat scope: grounded Q&A + persisted history.** Answers are grounded on the
  block + its section + the pack's `key_insight` + the source's original content.
  Conversations are persisted per block. Explicitly **out**: inserting an answer
  as a new block, and AI-rewriting a block (both were declined).
- **Add-block is manual** (choose a type, insert an empty block, edit it). Chat
  does not create blocks.

## Contract changes (Python is the source of truth — `docs/04 §2.5`)

### Phase 1 — expose stable ids

`services/api/app/schemas/pack.py` + `services/api/app/services/pack.py`:

- Add `id: uuid.UUID` to `PackSectionOut` and to every block variant in the
  `BlockOut` union. The DB rows (`PackSection`, `PackBlock`) already have ids
  (`TimestampedBase`/`Base` PK); the serializer currently drops them. Emit them:
  block becomes `{id, type, **data}`, section `{id, heading, blocks}`.
- No DB migration; no worker change. Regenerate `packages/api-client` (`just
  gen-client`). The web reader keys blocks by `id` instead of array index.

### Phase 2 — mutation endpoints

New write endpoints on the pack (routers thin, logic in
`services/api/app/services/pack.py`, persistence in `services/shared` — `docs/04
§2.5` / CLAUDE.md rule 3). All scoped to the authenticated owner of the snapshot.

| Method + path | Body | Effect |
|---|---|---|
| `PATCH /snapshots/{sid}/blocks/{bid}` | `{data}` and/or `{position}` | Update a block's typed `data` (validated against the block type's schema) and/or its `position` within its section. |
| `POST /snapshots/{sid}/sections/{secid}/blocks` | `{type, data, position}` | Insert a new block of `type` at `position`; sibling positions shift. |
| `DELETE /snapshots/{sid}/blocks/{bid}` | — | Remove a block (follow the repo's delete convention — soft-delete if `TimestampedBase` provides `deleted_at`, else row delete). |
| `PATCH /snapshots/{sid}/sections/{secid}` | `{heading}` | Rename a section heading (optional / stretch). |

- Reorder = a `PATCH block` with a new `position` (v1: reorder **within** a
  section only; cross-section moves deferred).
- New request schemas in `services/api/app/schemas/pack.py`
  (`BlockUpdate`, `BlockCreate`, per-type `data` validation reusing the same
  five variant shapes). Responses return the updated/created `BlockOut`.
- Position semantics: order is derived by sorting blocks on `position` within a
  section. The service layer owns normalization — the client sends intent
  (`insert at index N`, `move to index N`) and the service assigns/renumbers
  `position` values (0-based) so ordering stays consistent.
- No schema migration required (structure already supports it). Regenerate
  `packages/api-client`.

### Phase 3 — chat model + endpoints

- **Move the LLM layer to shared.** Relocate `services/worker/app/llm/` →
  `services/shared/gulp_shared/llm/` (provider-agnostic, config-driven per
  `docs/subsystems/S2-processing-design.md` §2.6). Update worker imports; behavior
  unchanged. This lets the API call `complete()` / `complete_structured()`
  directly.
- **New model** `services/shared/gulp_shared/models/` — `PackBlockMessage`
  (`TimestampedBase, Base`): `block_id` (FK → `pack_blocks.id`, `ondelete
  CASCADE`, indexed), `role` (enum `user | assistant`), `content` (Text).
  Ordered by `created_at`. New Alembic migration.
- **Endpoints:**

  | Method + path | Body | Effect |
  |---|---|---|
  | `GET /snapshots/{sid}/blocks/{bid}/messages` | — | List the block's messages, oldest first. |
  | `POST /snapshots/{sid}/blocks/{bid}/messages` | `{content}` | Persist the user message; build grounding context; call the LLM; persist + return the assistant message. |

- **Grounding context** (assembled in `services/api/app/services/`): the target
  block's rendered content + its section heading + sibling block summaries + the
  pack `title` / `key_insight` + the source's original text (`Source.content_body`,
  or the persisted `NormDoc` if available), truncated to a token budget (prefer
  the block's own section). The system prompt instructs the model to answer from
  the provided source and say so when the source doesn't cover it.
- Regenerate `packages/api-client`.

## Frontend architecture (`apps/web`)

### Layout (Phase 1)

`app/snapshots/[id]/page.tsx` moves from a centered single column to a workbench:
center reading column (comfortable ~720px measure) + a right panel region
(360–420px) that is empty until Phase 3. `<1280px`: right panel is a slide-over
overlay; sidebar behavior unchanged. Built with CSS Modules + `@gulp/ui` tokens
(no Tailwind — matches the codebase).

### Components

- **`BlockCell`** — wraps the existing per-type `BlockView` render. Owns:
  selection state, hover affordances, and (Phase 2) edit-mode toggle. This is the
  "cell" unit (Jupyter-like).
- **`BlockToolbar`** (Phase 2/3) — appears on hover/selection: `⋯` menu
  (delete, move up/down), drag handle (reorder), and `💬` (Phase 3, opens the
  chat panel for this block).
- **`AddBlockMenu`** (Phase 2) — the `+` affordance between blocks; opens a small
  type picker (`prose / formula / table / figure / list`) and inserts an empty
  block of that type in edit mode.
- **Per-type editors** (Phase 2): `ProseEditor` (markdown textarea + live KaTeX
  preview), `FormulaEditor` (`latex` + `explanation`), `TableEditor` (editable
  grid over `headers`/`rows`, add/remove row/col), `ListEditor` (line-per-item +
  `ordered` toggle), `FigureEditor` (`label` + `explanation`).
- **`ChatPanel`** (Phase 3) — right rail; shows the selected block's message
  history + an input; posts to the messages endpoint; loading state while the
  LLM responds; follows the currently-selected block.

### State (Decision A1)

The pack reader becomes a client island seeded by the server fetch. It holds the
pack blocks in React state. Edits/inserts/deletes/reorders update local state
optimistically and fire the REST call; on failure, roll back and show a toast
(copy never blames the user — `docs/03 §2.7`). No global store; state is local to
the reader subtree. Chat panel state (open block, draft input) is local too.

## Visual redesign (Phase 1 — land the `docs/03` web register)

The current render reads flat because the type/spacing system isn't applied.
Redo it systematically per `docs/03`:

- **Type roles:** Inter for body/UI; Geist Mono for section overlines, metadata,
  and numerals (tabular); Instrument Serif rationed to the pack title / a single
  hero line. Apply the §4.2 scale (web column).
- **Structure by type, not boxes:** hairline (`--border`) separators, 4px
  spacing base for rhythm, generous whitespace; near-grayscale slate with the one
  functional blue accent (`--blue-600`) reserved for the primary affordance.
- **Distinct roles** for `core_contributions` (skim list), `key_insight`
  (highlighted lead), section headings + mono overlines, and `references`
  (compact list).
- **Block typography polish:** KaTeX display/inline math spacing, real table
  styling with mono captions, tuned list/quote/`code` treatment.
- **Micro-interactions:** block hover reveals the toolbar/`+` at 120–180ms
  (`docs/03 §2.8`); functional, no bounce.
- **States** (`docs/03 §8`): skeletons (not spinners) while a pack is
  `generating`; optimistic-edit failure toast; chat "thinking" state.

## Error handling / edge cases

- **Re-processing replaces the pack.** Re-running Start regenerates the pack
  wholesale (existing delete-orphan behavior), discarding manual edits and block
  chats. Phase 2 adds a confirm prompt on the re-run entry point warning that
  edits will be lost. (A merge/preserve strategy is out of scope.)
- **Grounding token budget:** long sources are truncated; prefer the target
  block's section. The model is told when the source is thin.
- **Optimistic failure:** roll back local state + toast; the server stays the
  source of truth.
- **Ownership:** every mutation and chat endpoint authorizes the snapshot owner,
  mirroring the existing `GET .../pack` guard.
- **Empty pack / no blocks:** the `+` insert still works on an empty section;
  a section with no blocks renders its `AddBlockMenu` placeholder.

## Testing

- **Backend (pytest):** each mutation endpoint (type validation, position
  semantics, ownership, idempotency where relevant); the messages endpoints with
  a `FakeProvider` LLM (no real API in tests); the LLM-layer relocation keeps
  worker tests green.
- **Frontend:** component tests in the existing `PackReport.test.tsx` style for
  `BlockCell`, each per-type editor (edit → save → optimistic update), the
  `AddBlockMenu` insert, delete/reorder, and `ChatPanel` (history load + post +
  loading/rollback). Keep `lib/pack.ts` helper tests.
- Contract: after each phase, `just gen-client` + `just lint` + `just test`.

## Out of scope

- Rich-text block-editor framework (BlockNote/TipTap/Lexical).
- Inserting chat answers as blocks; AI-rewriting a block; auto figure generation.
- Cross-section block moves; block-level version history / edit tracking.
- Merging manual edits across a re-process (re-run replaces the pack).
- SSE/token streaming for chat (plain request/response in v1; streaming later).
- Vector store / RAG (single-source grounding feeds the source text directly).
- Mobile client (`apps/mobile` stays deferred per CLAUDE.md).

## File-change inventory (by phase)

| Phase | Layer | File | Change |
|---|---|---|---|
| 1 | API schema | `services/api/app/schemas/pack.py` | Add `id` to `PackSectionOut` + block union. |
| 1 | API service | `services/api/app/services/pack.py` | Emit section/block `id`s. |
| 1 | Client | `packages/api-client/*` | Regenerate (`just gen-client`). |
| 1 | Web | `apps/web/app/snapshots/[id]/page.tsx` | Workbench layout (center + right panel region). |
| 1 | Web | `apps/web/components/snapshot/PackReport.tsx` | Extract `BlockCell`; apply `docs/03` visual system. |
| 1 | Web | `apps/web/components/snapshot/*.module.css`, `apps/web/app/globals.css` | Typography/spacing/hairline redesign. |
| 1 | Web | `apps/web/components/snapshot/BlockCell.tsx` (new) | Cell wrapper. |
| 2 | API | `services/api/app/routers/pack.py` | Add PATCH/POST/DELETE mutation routes. |
| 2 | API | `services/api/app/schemas/pack.py` | `BlockUpdate` / `BlockCreate` + per-type validation. |
| 2 | API | `services/api/app/services/pack.py` | Mutation logic + position semantics. |
| 2 | Client | `packages/api-client/*` | Regenerate + typed mutation helpers. |
| 2 | Web | `apps/web/components/snapshot/PackReport.tsx` | Client island holding pack state. |
| 2 | Web | `apps/web/components/snapshot/BlockToolbar.tsx`, `AddBlockMenu.tsx`, `editors/*` (new) | Toolbar, insert menu, per-type editors. |
| 3 | Shared | `services/shared/gulp_shared/llm/` (moved from worker) | Relocate provider-agnostic LLM layer. |
| 3 | Worker | `services/worker/app/**` | Update LLM imports. |
| 3 | Shared | `services/shared/gulp_shared/models/pack_block_message.py` (new) | `PackBlockMessage` model. |
| 3 | Migration | `services/api/alembic/versions/*` | New revision (chat messages table). |
| 3 | API | `services/api/app/routers/pack.py` (or new `chat.py`) | GET/POST messages routes. |
| 3 | API | `services/api/app/schemas/`, `services/api/app/services/` | Message DTOs + grounding + LLM call. |
| 3 | Client | `packages/api-client/*` | Regenerate. |
| 3 | Web | `apps/web/components/snapshot/ChatPanel.tsx` (new) | Right-rail per-block chat. |
| 1–3 | Tests | (per Testing) | Backend + component tests per phase. |
