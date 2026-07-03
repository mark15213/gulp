# S1 — Capture & Inbox · subsystem design

*Gulp · subsystem design doc · v1 · 2026-06-24*

> **⚠️ SUPERSEDED IN PART (2026-07-03).** Lifecycle references to `awaiting_review` / `in_library` here predate the **single-gate** convergence — `ready` = in the library, and the only review gate is per-card accept/reject (`02 §6`, `01 §F2`). The capture mechanics (one-gesture intake, `Snapshot` creation, the derived Inbox view) still stand.

> The first per-subsystem design doc spun out of [`04-development-plan.md §6`](../04-development-plan.md). It sits **below** the four product docs ([`01`](../01-interaction-spec.md) flows, [`02`](../02-data-model.md) objects, [`03`](../03-ui-system.md) look) and the [`05`](../05-repo-structure.md) layout, and **resolves the `S1` charter** (`04 §4 S1`) into buildable detail: flows, interfaces, screens, the physical-schema slice, and the API contract that `02 §10` deferred.
>
> **Altitude:** one capability, end to end. This doc cuts S1 down to what gets built and how it connects — it resolves the charter's three open questions, fixes the data/API touchpoints, and names the seams S2/S3/S7/S8 plug into. It stops above S2's internals (no fetch/parse/prompt design) and above real auth/sync (stubbed here, owned elsewhere).
>
> **Locked scope (decided with the product owner before this doc):** capture targets = **links + notes only** (web); owner/auth = **single seeded dev user** (no real sign-in). See §2.

---

## 1. Scope & reading guide

- **Covers:** the web capture path (`01 §F1`) for **links and notes**, the `Snapshot` it produces (`02 §4.3`), the derived **Inbox** view (`02 D3`), and the **enqueue hand-off** to the worker — full stack: `gulp_shared` (DB floor + model) → `services/api` → `packages/api-client` → `apps/web`.
- **The cut follows the charter.** S1 owns "get anything in, land it as a `Snapshot` in Inbox, never block on processing" and "Snapshot creation and its status up to the `processing` hand-off" (`04 §4 S1`). Everything past the hand-off belongs to a neighbor.
- **Out of scope (handed off, §10):** pack generation / fetch / parse (S2); review, "Add to library", deep curation (S3); feed-emitted snapshots (S7); file/PDF upload, email-in, OS share sheet, WeChat (later capture targets); mobile; real authentication; real offline reconciliation and cross-device merge (S8).
- **How to read it:** §2 is the decisions (skim first), §3–4 are the flow and the Inbox, §5–8 are the four layers bottom-up (data → API → worker seam → web), §9 is cross-cutting states, §10 is acceptance + handoffs.
- **What S0 left as floor:** an empty navigable web shell on `lib/mock.ts` static data; `services/api`/`worker`/`shared` scaffolded but with `gulp_shared.db` **empty** (`deps.py` already imports a not-yet-existing `SessionLocal`); arq worker a placeholder `print`; `packages/api-client` a stub. S1 fills the persistence floor it needs as it goes (`05 §7`: fill only the current subsystem's slice).

---

## 2. Resolved decisions

Each resolves an open question from the S1 charter (`04 §4 S1`) or a fork this slice forces. **Reversible** = changeable later without reshaping consumers.

| # | Decision | Rationale | Reversible? |
|---|---|---|---|
| **C1** | **Capture targets first = web paste (`⌘K`) + in-app `⊕ Capture`, media types `webpage` and `note` only.** | Web-first (`04 §5`); links and notes need no blob store or inbound-mail infra, so they are the smallest path that still proves one-gesture capture across two content shapes. File/PDF/screenshot (needs `content_ref` blob storage), email-in (needs inbound-mail infra), and the mobile/headless targets defer with their enabling infra. | Yes — each further target is additive: a new `captured_via` + (for files) a blob path. |
| **C2** | **Dedupe by normalized `origin_url`.** On capture, normalize the URL (lowercase host, strip fragment + tracking params + trailing slash) and look up a live (`deleted_at IS NULL`) snapshot for the same owner. On a hit, return the **existing** snapshot flagged `duplicate=true` — the UI offers "open existing" instead of re-capturing (`01 §10.1`). | Resolves the charter's dedupe question for the link case. Notes have no URL → never deduped. Content-hash dedupe for files defers with file capture (C1). | Yes — normalization rules and the hash path are additive. |
| **C3** | **Offline capture = a thin client-side queue.** Capture inserts optimistically and `POST`s; if offline or the request fails on the network, the payload persists to a local (localStorage) buffer as `queued` and flushes on the `online` event, reconciling each item against the server snapshot it returns. | Resolves the charter's "offline-capture queue shape" at S1's altitude. The charter explicitly parks **real reconciliation (dedup-on-flush, cross-device merge, conflict resolution) for S8** — S1 only needs the local buffer + flush so a capture made offline is not lost (`01 §10.4`). | Yes — S8 replaces the flush with the real sync engine; the client buffer shape is internal. |
| **C4** | **Inbox = uncommitted, unfiled snapshots** — `kind=snapshot AND deleted_at IS NULL AND status ≠ in_library AND no KBMembership`. | `02 D3` defines Inbox narrowly as `status = awaiting_review`, but `01 §F1` shows **processing** items in Inbox the instant they land. This generalizes D3 to the whole pre-library funnel so both hold; D3's `awaiting_review` set is just the steady-state subset. It stays a **derived view, never an entity** (`02 D3`, invariant `02 §9.4`). In S1 — no S2/S3 — the predicate reduces to "all non-deleted captures." | Yes — purely a read query; the UI may present it any way (`02 D3`). |
| **C5** | **The S1↔S2 boundary is the enqueue.** `POST /capture` persists the snapshot at `status=processing`, enqueues an arq `process_snapshot(snapshot_id)` job, and returns — never running heavy work inline (`04 §4 S1` rule, `services/api/CLAUDE.md`). S1 ships a **no-op `process_snapshot` placeholder** in the worker; the snapshot rests at `processing`. | Honors "capture never blocks on AI" and "up to the processing hand-off" exactly, exercises Redis/arq end-to-end, and leaves the precise function S2 fills. S1 does **not** fake `ready`/a pack — in S1 a capture honestly shows "Processing". | Yes — S2 replaces the placeholder body; nothing else changes. |
| **C6** | **Owner = a single seeded dev user; auth is a stub dependency.** `get_current_user` returns a fixed-UUID user seeded by the first migration. | Real minimal sign-in is S0's remaining work; S1 needs only a valid `owner` so the model and queries are correct now. One seam (`core/auth.py`) swaps to real auth later. | Yes — replace the dependency; `owner_id` is already modeled correctly. |
| **C7** | **`tags` is a join table (`source_tags`), not an array column.** | `02 §2.3` forbids storing a collection as a single clobberable scalar (an array is last-write-wins under sync); membership must union. Establishing the join now avoids an S8 refactor, and tags are captured in S1 (the confirm sheet). | Yes — a join is the most general shape; nothing downstream assumes otherwise. |

---

## 3. Capture flow (`01 §F1`, web)

**Goal:** from intent to "saved" in one gesture; never wait on processing.

**Triggers (S1):** `⌘K` (paste a link) · `⊕ Capture` button (Link or Note). *(Share sheet, WeChat, email-in defer — C1.)*

**Steps:**
1. User invokes capture (`⌘K`, or `⊕`). The **Capture-confirm sheet** opens with a `Link | Note` toggle.
   - **Link:** URL field (the user pastes the link), editable **title defaulting to the URL's host** (no page fetch — that is S2; capture must not block, `01 §2.2`), optional one-line **note** (annotation), optional **tags**. Target knowledge base shows **Inbox** (fixed in S1 — KBs are S3).
   - **Note:** a **body** text field (the note's content), optional title (defaults to the first line), optional tags.
2. User confirms (primary action). The sheet closes immediately.
3. The item is inserted **optimistically** into the Inbox list and the Today "recently captured" peek, and a **"Saved"** toast shows. A `POST /capture` fires in the background.
4. Server persists a `Snapshot` (`status=processing`), enqueues `process_snapshot` (C5), and returns the snapshot (or, on a duplicate URL, the existing one with `duplicate=true`).
5. The optimistic row reconciles to the server snapshot. On `duplicate=true`, the toast becomes **"Already saved — open existing"** and no new row remains.

**Key screens:** Capture-confirm sheet · Inbox list · Today recent-captures peek.

**States (this slice):** `queued` (offline, client-side, C3) → `processing` (persisted, enqueued). `ready`/`awaiting_review`/`in_library`/`needs_attention` are reachable only once S2/S3 exist — modeled now (§5), produced later (§10).

**Edge cases:**
- **Duplicate URL** → "open existing" (C2).
- **Offline** → row shows `Queued`; flushes on reconnect (C3).
- **Empty/invalid input** → confirm disabled until a URL or note body is present; malformed URL flagged inline.
- *(Paywalled/blocked extraction and unsupported types are S2 concerns — S1 stores the snapshot regardless and never inspects content.)*

---

## 4. Inbox (derived view, `02 D3` / C4)

- **Definition:** the query in C4 — uncommitted, unfiled snapshots for the current user, newest first. Never stored (invariant `02 §9.4`).
- **What it shows (S1):** one row per snapshot — type glyph (`ObjectGlyph`), title, source meta (host / "Note"), relative time, and a **status tag** (the `processing` shimmer / `Ready` / `Needs attention` pattern already in `CapturePeek`). The Sidebar **Inbox** count and the Today peek read the **same** set (`02 D3`'s point: one underlying set, many surfaces).
- **What it does *not* do in S1:** no approve/commit/"Add to library", no pack panel, no deep curation — those are **S3**. S1's Inbox is a read surface plus two affordances: **open original** (`origin_url`) and **open existing** (dedupe target). It is the "awaiting / unfiled" view the charter names, nothing more.
- **Sidebar wiring:** the nav row currently renders an inert `count: 3` placeholder; S1 wires it to the live Inbox count and routes it to `/inbox`.

---

## 5. Data layer — `services/shared/gulp_shared`

The physical-schema slice S1 needs (`02 §10` bridge). SQLAlchemy 2.0, **sync** engine on psycopg3 / Postgres 17 (the driver S0 already chose in `settings.py` and `pyproject`).

**`db/`** — fill the floor `deps.py` imports:
- `Base` (declarative), `engine` (from `settings.database_url`), `SessionLocal` (sync `sessionmaker`).
- A **`TimestampedBase`/mixin** carrying the `02 §2.2` implicit fields on every entity: `id` (UUID PK), `created_at`, `updated_at` (drives LWW), `deleted_at` (soft-delete; nothing is hard-deleted — invariant `02 §9.5`).

**`models/user.py`** — minimal `User` (S0 leftover otherwise):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | the `owner` target |
| `display_name` | text? | |
| `locale` | enum `{zh·en}` | default `en` (`02 §4.1`) |

> The rest of `02 §4.1` (`auto_approve_default`, `gulp_session_minutes`, `daily_reminder_at`, `notification_prefs`) lands with settings/auth (S0/S3) — not needed by capture.

**`models/source.py`** — **one `sources` table, `kind` discriminator** (`02 D1`). S1 writes only `kind='snapshot'`; form-specific columns are nullable when not applicable.

| Column | Type | Notes |
|---|---|---|
| *(+ implicit fields via the mixin)* | | `id`, `owner_id` (FK `users.id`), `created_at`, `updated_at`, `deleted_at` |
| `kind` | enum `{snapshot·conversation·subscription}` | discriminator |
| `title` | text | host-default or user-set (§3) |
| `note` | text? | one-line annotation from capture (`02 §4.3`) |
| `status` | enum `{queued·processing·ready·awaiting_review·in_library·needs_attention}` | full snapshot lifecycle modeled; S1 writes `queued`/`processing` |
| `media_type` | enum `{article·pdf·video·podcast·note·screenshot·audio·webpage}` | S1 writes `webpage` (link) / `note` |
| `origin_url` | text? | the link (null for notes) |
| `content_body` | text? | **note body** for `media_type=note`; **null for links** until S2 fetches |
| `content_ref` | text? | null in S1 (no blobs) |
| `captured_via` | enum `{share_sheet·wechat·email·in_app·paste·manual·screenshot·audio_memo}` | S1 writes `paste` (`⌘K`) / `in_app` (link via `⊕`) / `manual` (note) |

> **Deferred columns (target tables don't exist yet):** `emitted_by` (→`Source`, the subscription that produced it — **S7**) and `pack_id` (→`KnowledgePack` — **S2**). Added with their owning subsystem so the migration history stays honest (`05 §7`).

**`models/source_tag.py`** — `tags` as a join (C7):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `source_id` | FK `sources.id` | |
| `tag` | text | one row per tag → union under sync (`02 §2.3`) |

**`domain/urls.py`** — `normalize_url(raw) -> str` (pure; C2's normalization), reused by the capture service for dedupe.

**Migration & seed:** one Alembic revision creating `users`, `sources`, `source_tags`, and **inserting the fixed-UUID dev user** (C6) so the auth stub has a real owner. `just migrate "s1 capture & inbox"` → `just migrate-up`.

---

## 6. API layer — `services/api`

Conventional layering (`05 D4`, `services/api/CLAUDE.md`): routers thin → services hold logic → persistence in `gulp_shared`.

**`core/auth.py`** — `get_current_user` dependency returning the seeded dev user (C6). The single seam real auth replaces.

**`core/queue.py`** — `enqueue(job_name, *args)` pushing to arq's Redis pool (the API is sync; this bridges to arq's async pool). The capture router's only outbound dependency besides the DB.

**`schemas/` (→ OpenAPI → api-client):**

| Schema | Shape |
|---|---|
| `CaptureRequest` | `url: str?` · `text: str?` (note body) · `note: str?` (annotation) · `title: str?` · `tags: str[]` · `captured_via: enum{paste·in_app·manual}` — **exactly one of `url` / `text`** (validator) |
| `SnapshotOut` | `id` · `kind` · `title` · `note?` · `status` · `media_type` · `origin_url?` · `content_body?` · `captured_via` · `tags: str[]` · `created_at` · `updated_at` |
| `CaptureResponse` | `snapshot: SnapshotOut` · `duplicate: bool` |
| `InboxOut` | `items: SnapshotOut[]` · `count: int` |

**`services/capture.py`** — the logic:
- `text` → `media_type=note`, body → `content_body`. `url` → normalize (C2), look up a live duplicate for the owner; on hit return it with `duplicate=true` and **enqueue nothing**; else create `media_type=webpage`, `status=processing`, attach tags, **enqueue `process_snapshot`**.
- Title default: host (link) / first line (note) when `title` omitted.

**`services/inbox.py`** — the C4 query, newest first.

**`routers/capture.py`** — `POST /capture` → `CaptureResponse` (returns before any worker work — the instant-confirm guarantee). `GET /snapshots/{id}` → `SnapshotOut` (for "open existing"/detail).
**`routers/inbox.py`** — `GET /inbox` → `InboxOut`.

Routers are registered on the FastAPI app in `main.py`. After schema changes: **`just gen-client`**.

---

## 7. Worker seam — `services/worker`

C5 in code, and nothing more:
- **`app/tasks/__init__.py`** — register `async def process_snapshot(ctx, snapshot_id)` that **logs `"TODO(S2): process snapshot {id}"` and returns** (no status change, no pack). Define `WorkerSettings` (functions `[process_snapshot]`, `redis_settings` from `settings.redis_url`).
- **`app/tasks/__main__.py`** — boot the arq worker on `WorkerSettings` (replacing the placeholder `print`), so `just worker` / `just dev` run a real consumer.

This is the exact function S2 grows into (fetch → parse → chunk → pack → draft cards → link concepts, per `services/worker/CLAUDE.md`); S1 leaves it empty on purpose.

---

## 8. Web client — `apps/web`

Server components fetch; capture is the one interactive island (the §0 fork B1: no client data library in S1; React Query/SWR is the natural S8/realtime upgrade).

**Contract:** `lib/api.ts` constructs the typed `@gulp/api-client` (over the generated `schema.gen.ts`) against `API_URL` (added to `.env.example`). The app never hand-writes fetch types (`apps/web/CLAUDE.md`).

**Capture island (`components/capture/`):**
- `CaptureProvider` (client) — mounted in `Shell`; holds modal open-state, registers the global **`⌘K`** key handler, renders the sheet.
- `CaptureSheet` — the §3 confirm sheet (`Link | Note` toggle, fields, primary "Save"); reuses `Button`. On submit: optimistic insert + toast, `POST /capture` via `captureQueue`, then `router.refresh()` to re-pull the server Inbox.
- `CaptureButton` (`⊕`) — opens the sheet; placed in the shell. The Sidebar's static `⌘K` field becomes a real trigger for the same sheet (its search/jump role is a later command-bar concern — S3+).
- `lib/captureQueue.ts` — C3: optimistic + localStorage buffer + flush on `online`.

**Inbox (`app/inbox/page.tsx` + `components/inbox/`):**
- Server component fetches `GET /inbox`; `InboxList`/`InboxRow` render rows reusing `ObjectGlyph` + the `CapturePeek` status-tag pattern; **open original** / **open existing** affordances. Read-only (commit is S3).
- Wire the Sidebar **Inbox** row (live count + route) and the Today **recently-captured** peek to this real data, replacing that slice of `lib/mock.ts`. The Today digest / Start-Gulp cards stay on mock (S7/S4).

---

## 9. Cross-cutting states (`01 §7`, for capture + Inbox)

| State | Behavior in S1 |
|---|---|
| **Loading** | Inbox renders skeleton rows, never a blank spinner; the list stays interactive as it streams. |
| **Empty** | Inbox empty state points to the next action — "Capture your first thing" (an X1 onboarding stub, `04 §X1`). |
| **Processing** | every S1 capture rests here (C5) — the `processing` shimmer tag; the row is visible and openable. |
| **Error / failed extraction** | the UI keeps the `needs_attention` affordance (banner + open-original) **ready**, but **no S1 capture reaches it** — extraction is S2. |
| **Offline** | capture queues locally with a subtle offline indicator; reads serve the last server list; flush on reconnect (C3). |

---

## 10. Validation & handoffs

**Acceptance — S1's own success criteria (`04 §2.2`, validate the capability, not the whole loop):**
- Capture succeeds for both content shapes (link, note) and the snapshot is persisted with the right `media_type`/`captured_via`/`status`.
- **"Saved" confirms instantly:** `POST /capture` returns before any worker work runs (asserted — enqueue, not execute).
- The item **reliably appears in Inbox** (Sidebar count, `/inbox`, and Today peek all reflect it from the same query).
- **Duplicate URL** returns the existing snapshot (`duplicate=true`) and the UI offers "open existing".
- **Offline** capture queues and flushes on reconnect with no loss.
- *Tests:* pytest over `capture` service (creation, note vs link, dedupe, enqueue-called) and the `inbox` query; a web smoke check of the capture→Inbox round-trip.

**Handoffs (the seams this slice leaves):**
- **S2** fills `process_snapshot`: fetch/parse, set precise `media_type`, populate `content_body` for links, build the `KnowledgePack` + `pack_id`, and drive `processing → ready → awaiting_review` (and `needs_attention` on failure).
- **S3** adds the review/commit path: "Add to library" → `in_library` + `KBMembership`, the deep-curation Inbox, and the `awaiting_review` triage subset of C4.
- **S7** sets `emitted_by` for feed-emitted snapshots and reuses `POST`-equivalent creation from the subscription pipeline.
- **S8** replaces the C3 client flush with the real sync engine: dedup-on-flush, cross-device merge, conflict resolution (`02 §2.3`).
- **S0 (remaining)** swaps the `core/auth.py` stub for real sign-in; the `owner` model is already correct.

---

*Next per-subsystem doc in build order (`04 §5`): `S2-processing-design.md` — the engine that grows the `process_snapshot` placeholder this doc leaves behind.*
