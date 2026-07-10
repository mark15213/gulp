# Immersive reader redesign — design

- **Date**: 2026-07-10
- **Status**: approved (brainstorm), pending spec review
- **Scope**: `apps/web` (reader) + `services/api` (chat) + `services/shared` (models) + `packages/api-client`. **Web-first**, no mobile.
- **Sequence**: spec 2 of 2. Spec 1 (the Library redesign) is shipped ([`2026-07-10-library-redesign-source-tags-design.md`](2026-07-10-library-redesign-source-tags-design.md)). This doc covers the reader you land on from a library item.

## Context

The reader is `apps/web/app/snapshots/[id]/page.tsx` (server) → `components/snapshot/ReaderToggle.tsx`, a three-tab toggle (**Pack** / **Original** / **Cards**) inside the global app shell (`components/shell/FullBleedGate.tsx` — `/snapshots` is *not* full-bleed, so it gets the 240px left nav + a capture row). The reading column is a single ~720px centered block.

Three problems motivate the redesign:

1. **No immersion.** The reader is boxed inside the fixed 240px app nav; there's no way to collapse chrome for distraction-free reading, and the column doesn't adapt to available width.
2. **The "Original" tab is dead weight.** It dumps `content_body` as `white-space: pre-wrap` plain text (`ReaderToggle.tsx` line 51-53). Meanwhile `origin_url` is never linked from the reading view.
3. **Chat is per-block and siloed.** `components/snapshot/ChatPanel.tsx` is a fixed 380px slide-over keyed by `blockId`, backed by `PackBlockMessage` (FK to block) and `GET`/`POST /snapshots/{id}/blocks/{block_id}/messages` (`routers/pack.py`, service `app/services/chat.py`). Each block is an isolated thread — there is no way to converse about the article as a whole, and no way to pull a specific paragraph into a broader conversation.

The chat is already backed by a **real LLM** (`gulp_shared.llm.complete_structured`; provider/model from `settings`), grounded on pack title + key insight + section heading + the one block's text + a 6000-char source excerpt (`chat.py:_grounding_system`). Answers are synchronous request/response.

## Goals

- An **adaptive three-zone reader**: a collapsible left nav and a collapsible right chat panel, with the reading column fluidly re-centering and staying at a comfortable measure whatever is open. Both closed = full immersive reading.
- Replace the **Original tab** with a **↗ origin-link icon** (opens `origin_url` in a new tab).
- **One article-scoped chat** with **structured block attachments** — "add to chat" from a block, per-paragraph Q&A, and whole-article conversation all in a single thread. Replaces per-block threads.

## Non-goals (out of scope this spec)

- Streaming responses (keep synchronous "Thinking…", as today).
- A document outline / table-of-contents panel (can be added later behind the same collapse machinery).
- Editing/re-ordering attachments beyond add/remove; multi-select attach gestures.
- Any change to card generation, the Cards view, or the pack-editing model.
- Mobile.

## Design

### A. Adaptive three-zone layout

```
[ left nav ]  [ ——— reading column ——— ]  [ chat panel ]
 collapsible       adapts / re-centers        collapsible

both open:   [nav][── reading ──][chat]
nav closed:  [── reading ──────][chat]
chat closed: [nav][──── reading ────]
both closed: [────── reading (immersive) ──────]
```

- The reader route becomes **full-bleed** (added to `FULL_BLEED_PREFIXES` in `components/shell/FullBleedGate.tsx`) and owns its own chrome via a new client `ReaderLayout`. This is the clean seam for a bespoke adaptive layout — the shell's fixed nav + capture row don't fit a collapsible reading surface. `ReaderLayout` receives the existing `<Sidebar/>` as a prop (same server-element-into-client-component pattern the shell already uses) so the app nav is **reused, not forked**. `ReaderLayout` wraps **every** snapshot state (it renders the collapsible nav + top bar around whatever the page renders as center — the reader when `ready`, or the start/retry/processing UI otherwise); the **chat toggle and attachments are only active when a pack is `ready`**.
- `ReaderLayout` holds two booleans — `navOpen`, `chatOpen` — persisted to `localStorage` (reading is a repeated activity; the last immersive state should stick). Each zone has its own toggle in the reader top bar.
- The **reading column** is clamped to `var(--measure)` and centered in the space left by whichever panels are open (CSS grid with a fluid center track); it never goes edge-to-edge or cramped.
- **Top bar** (reader-local): `← back · title · GenreSelect · [↗ origin] · [⇤ nav toggle] · [💬 chat toggle]`. Replaces the header currently in `page.tsx`.
- **Content tabs** collapse to **Pack / Cards** (`ReaderToggle.tsx`) — the **Original tab and its `original` plumbing are removed**; `origin_url` is surfaced as the `↗` icon (hidden when null).

### B. Chat data model — unified article thread

- **New `PackMessage`** (`services/shared/gulp_shared/models/pack_message.py`): `snapshot_id → sources.id` (CASCADE) · `role: ChatRole` · `content: Text` · `block_refs: JSON` (list of block-id strings attached to a user turn; empty for assistant/plain turns) · timestamps + soft-delete. Reuses the existing `ChatRole` enum.
- **Endpoints** (in `routers/pack.py`, replacing the block-scoped pair): `GET /snapshots/{id}/messages` → `list[MessageOut]`; `POST /snapshots/{id}/messages` `{ content, block_refs?: string[] }` → the assistant `MessageOut`. `MessageOut` gains `block_refs: string[]`.
- **Grounding** (`app/services/chat.py` reworked to snapshot scope): system prompt = pack title + key insight + summary + source excerpt (whole article); when `block_refs` are present, each referenced block's text is injected and emphasized ("the reader is asking specifically about these blocks…"). No refs → general article chat. Ownership is validated at the snapshot level (a new `load_pack_scoped`, mirroring `load_block_scoped`).
- **Replaces per-block chat:** `PackBlockMessage`, the `/blocks/{id}/messages` endpoints, `list_messages`/`answer_question`'s block signature, and the per-block `ChatPanel` are removed. An **Alembic migration drops `pack_block_messages`** and creates `pack_messages` (low personal data; no content migration).

### C. Block "add to chat" + per-paragraph Q&A

- Hovering a block reveals an **"add to chat"** control (replacing the block's current `💬` "Discuss" button in `BlockToolbar.tsx`). Clicking attaches that block as a removable **context chip** in the chat composer and opens the panel if closed.
- The composer renders attachment chips above the input; sending posts `{ content, block_refs }`. Per-paragraph Q&A is exactly this: attach the paragraph, ask — no separate affordance.
- Chat stays **optimistic + synchronous** (mirror today's `ChatPanel.send()`), now snapshot-scoped.

### D. Component decomposition (`apps/web/components/snapshot/`)

- **`ReaderLayout.tsx`** (new, client): owns `navOpen`/`chatOpen` + attachment state; renders top bar, the reused `<Sidebar/>`, the center (`ReaderToggle`), and `ChatPanel`; provides an `addToChat(blockId)` via context so blocks can attach without prop-drilling.
- **`ReaderTopBar.tsx`** (new): back · title · genre · origin `↗` · nav/chat toggles.
- **`ChatPanel.tsx`** (reworked): snapshot-scoped; attachment chips; uses new `getPackMessages`/`postPackMessage`.
- **`ReaderToggle.tsx`** (trimmed): Pack / Cards only.
- **`BlockToolbar.tsx`** (adjusted): `💬` → "add to chat" calling the context `addToChat`.
- **api-client**: `getPackMessages(id)`, `postPackMessage(id, { content, block_refs })`; remove `getBlockMessages`/`postBlockMessage`.

## Docs to amend

- `docs/01-interaction-spec.md` — reader/curation flow: immersive collapse of nav + chat; article-scoped chat with block attachments (supersedes per-block).
- `docs/03-ui-system.md` — reader layout (adaptive three-zone), chat panel + attachment chips, origin `↗` icon replacing the Original tab.
- `docs/02-data-model.md` — replace `PackBlockMessage` with `PackMessage` (snapshot-scoped + `block_refs`); note the migration.

## Testing

- **API** (pytest per-package): `chat` grounding builds the system prompt with and without `block_refs` (attached block text present/emphasized); `list`/`post` message endpoints; snapshot-level ownership (`load_pack_scoped` 404s foreign/other-snapshot). Reuse the existing `test_block_chat.py` fixtures, retargeted to the pack endpoints.
- **Web** (vitest, classic-JSX → `import React`): `ReaderLayout` nav/chat toggles + center adaptation classes; `ChatPanel` attachment chips add/remove + optimistic send; "add to chat" from a block opens the panel with the chip; `ReaderToggle` shows Pack/Cards only; origin `↗` hidden when null.
- **Gate**: `just lint` green; `just gen-client` after the contract change (ignore the 2 pre-existing `schema.gen.ts` dup warnings); `just migrate` for the model change.

## Rollout / migration

One Alembic migration: drop `pack_block_messages`, create `pack_messages`. Contract changes (new message endpoints, `MessageOut.block_refs`, removed block-message endpoints) regenerate the client. The reader route flips to full-bleed. No data migration (chat history is transient and low-volume).
