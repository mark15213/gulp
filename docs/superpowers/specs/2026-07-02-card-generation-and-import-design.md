# Card Generation & Import — dual-supply card drafting

Date: 2026-07-02
Status: Approved (design); pending implementation plan
Scope: Card supply and per-source card review across `services/shared`,
`services/worker`, `services/api`, `packages/api-client`, and `apps/web`.

## Goal

Give every source a **card pool with two supplies and one contract**:

1. **Inline generation** — the card turn the S2 design deferred
   (`docs/subsystems/S2-processing-design.md` §2.5 C8, §9 Plan 3): an LLM drafts
   cards *from the knowledge pack*, run as an independent, manually triggered
   worker job.
2. **External import** — cards produced outside Gulp for the same source (e.g.
   NotebookLM flashcards, or any tool whose output is reshaped into our JSON
   contract) upload directly onto the source.

Both land as `Card` rows (`status = draft`) on the source, reviewed in a new
**Cards view** on the snapshot page: accept / reject / edit per card. Accepted
cards are the pool S4 (Gulp mode) will practice.

This is the first slice toward S3 (`docs/04 §4 S3`), **re-scoped** by the IA
convergence below: the card accept gate is built; the snapshot-level review
gate, KnowledgeBase entity, and Concept materialization are explicitly parked.

## Decisions locked in

- **Single contract, dual supply.** A `CardsPayload` Pydantic contract in
  `services/shared` is both the structured-output schema of the generation turn
  and the validation schema of the import endpoint. External tools' output is
  reshaped (outside Gulp, e.g. with Claude/ChatGPT) to match `cards.json`; no
  free-text or CSV normalization path in v1.
- **Independent trigger, worker-async.** Card generation is its own arq job,
  never chained to ▶ Start: it reads the *current* pack (including manual
  edits), never re-runs digest, never destroys pack edits or block chats.
  Failure visibility comes from a lightweight `cards_status` column, polled the
  same way pack processing already is.
- **Grounding = pack only.** The generation prompt receives the report
  (`title` / `key_insight` / `core_contributions` / sections / references) and
  nothing else. Cards test the digested understanding — which the report,
  already faithful to the source and possibly hand-edited, embodies. The raw
  `content_body` is not attached.
- **Cards attach at source level only.** `Card.source_id` (already present);
  no block/section FK. Both supplies are symmetric, and re-running digest
  (which rebuilds all block ids) cannot orphan cards.
- **Bare JSON import.** `POST /snapshots/{id}/cards/import` takes the
  `cards.json` body directly (paste or file). The export-tar packaging
  (`job_kind: "cards"`) is deferred; the contract is the same either way.
- **Consumption = per-source Cards view with accept/reject.** The snapshot
  page gains a third reader view (Report · Original · Cards). Cross-source card
  browsing (Library chips) is a later slice.
- **IA convergence (owner-approved, 2026-07-02):** the card accept gate is the
  **only** review gate in v1. See "Spec amendments" below.

## ① The contract — `CardsPayload`

New module `services/shared/gulp_shared/contracts/cards.py` (shared so the
worker validates generation output and the API validates imports — same
precedent as the relocated LLM layer):

```
CardDraft {
  card_type: short_answer | mcq | cloze | explain | apply | recall
  prompt: str                # non-empty
  answer: str | None
  explanation: str | None    # source-grounded reveal explanation
  options: list[str] | None  # mcq only
}
CardsPayload { cards: CardDraft[] }   # min 1, max 100
```

Validation rules (Pydantic validators, enforced on both supplies):

- `mcq` → `options` required, 3–6 entries, and `answer` must equal one of them.
- non-`mcq` → `options` must be null/absent.
- `cloze` → `prompt` must contain a `____` blank.
- `short_answer` → `answer` required.
- `explain` / `apply` / `recall` → `answer` optional (it serves as a grading
  rubric, per `02 §4.5`).

`CardsPayload.model_json_schema()` is written into the existing export tar as
`schema/cards.schema.json` (alongside `pack.schema.json`) so the contract is
always at hand when producing cards externally.

## ② Data model (one migration)

- `CardOrigin` gains **`imported`** (existing: `pack · conversation · user`).
  Inline-generated cards are `pack`; imported ones `imported`. The origin is
  load-bearing: it scopes regeneration's replace semantics and renders as the
  provenance badge.
- `Source` gains nullable **`cards_status`**: `enum{generating · ready ·
  failed}`, null = generation never triggered. Tracks the inline generation job
  only; imports never touch it. (Snapshot-only column, same single-table
  pattern as `media_type`.)
- No other model changes. `Card` already carries `source_id`, `card_type`,
  `prompt`, `answer`, `explanation`, `options` (JSON), `origin`, `status`.

## ③ Supply 1 — worker generation job

- New arq task `generate_cards(ctx, snapshot_id)` mirroring `process_snapshot`;
  stage logic in `services/worker/app/pipeline/cards.py`, prompt in
  `services/worker/app/prompts/cards.py`, LLM call through the shared
  provider-agnostic layer with `CardsPayload` as the structured-output schema.
- Prompt budget: **~6–12 cards per source**, card type chosen by content
  affinity (definitional → cloze/short_answer; claims → short_answer/explain;
  clear facts with plausible distractors → mcq). Every card carries a short
  source-grounded `explanation`.
- **Replace semantics:** on success, delete this source's cards where
  `origin = pack AND status = draft`, then insert the new batch as drafts.
  Accepted/rejected cards and imported cards are never touched. Idempotent;
  re-triggering is safe and expected.
- **Status machine:** trigger sets `cards_status = generating`; success →
  `ready`; failure after arq retries (≤2, backoff) → `failed`. The UI shows
  failed with a retry affordance.
- Guard: requires an existing pack with `status = ready`.

## ④ Supply 2 — bare JSON import

- `POST /snapshots/{id}/cards/import`, body = `CardsPayload` JSON. Strict
  validation; 422 with field-level errors on mismatch.
- All cards land `origin = imported`, `status = draft`, **appended** (no
  replace, no dedupe in v1 — bad batches are cleaned up with delete).
- **A pack is not required**: a source that never ran digest can still take
  NotebookLM cards.
- Ownership guard identical to the existing snapshot endpoints.

## ⑤ Consumption — API

Routers stay thin (`services/api/app/routers/cards.py`); logic in
`services/api/app/services/cards.py`.

| Method + path | Effect |
|---|---|
| `POST /snapshots/{id}/cards/generate` | Set `generating`, enqueue job; 400 if no ready pack; 409 if already generating. Returns `SnapshotOut` (202). |
| `POST /snapshots/{id}/cards/import` | Validate + append (§④). Returns created `CardOut[]`. |
| `GET /snapshots/{id}/cards` | All cards for the source, `created_at` order. |
| `PATCH /snapshots/{id}/cards/{cid}` | Status transitions (`draft`/`accepted`/`rejected`, freely — nothing downstream consumes them until S5) and/or content edits, re-validated per card type. |
| `DELETE /snapshots/{id}/cards/{cid}` | Delete (cleanup of bad batches); soft-delete per repo convention. |

`SnapshotOut` gains `cards_status`. Regenerate `packages/api-client`
(`just gen-client`).

## ⑥ Web UI (`apps/web`)

- `ReaderToggle` gains a third segment: **Report · Original · Cards**
  (realizing `01 §F2`'s Read · Pack · Cards shape on web).
- **CardsView**: header actions [⚡ Generate] [⤓ Import] + status; rows show
  type chip, prompt/answer/explanation, provenance badge (AI / imported /
  hand-written), accept/reject controls, inline edit.
- **Two display shapes, six types**: mcq (options editor, answer must remain
  one of the options) and free-text (all other types — same fields, different
  type chip). No per-type UI beyond that.
- **Generate flow**: POST → poll `SnapshotOut.cards_status` (reuse the
  `ProcessingPoller` pattern) until it leaves `generating`, then refetch the
  list; `failed` → error banner + retry. Copy never blames the user
  (`docs/03 §2.7`).
- **Import flow**: dialog with file picker + paste textarea; server validation
  errors surfaced per entry.
- Optimistic updates with rollback + toast, same as the Phase 2 editing model.
- CSS Modules + `@gulp/ui` tokens; skeletons over spinners (`docs/03 §8`).

## Spec amendments (flow back into `01`/`02`, per `04 §6`)

The IA convergence — owner-approved 2026-07-02, same mechanism as S2's
manual-trigger relaxation:

1. **The card accept gate is the only review gate in v1.** The snapshot-level
   commit gate (`ready → awaiting_review → in_library`, batch confirm,
   auto-approve) is **parked, pending re-evaluation**: with manual-trigger
   processing the owner has already read/edited the pack by the time it is
   ready, so a second confirmation confirms nothing. Revisit only if
   auto-process + feed volume (S7) create unvetted inflow. The enum values
   remain but stay unwired; Inbox = "not yet processed", Library = everything
   else, both derived, no user action between them. (No Inbox behavior change
   in this slice — until the Library view exists, Inbox keeps listing processed
   snapshots so they stay reachable.)
2. **KnowledgeBase is parked; tags cover grouping.** `SourceTag` already
   exists and KB membership is source-level many-to-many — a named tag.
   KB graduates back only when tags prove insufficient (description, per-KB
   digest).
3. **Concept materialization stays frozen** (no supply since the paper-report
   contract dropped facets; no consumer built). Unfreezing requires its own
   design.
4. **Six card types collapse to two display shapes in UI** (mcq vs free-text);
   the type enum stays as data.

## Error handling / edge cases

- Generate with no ready pack → 400 with actionable message.
- Concurrent generate → 409 (button disabled while `generating`).
- Generation failure → `cards_status = failed`, banner + retry; worker logs
  carry the cause.
- Import of a structurally valid but wrong-source batch: no guard possible —
  cleanup is select-and-delete (hard delete endpoint).
- Re-running ▶ Start (digest) does **not** touch cards (source-level
  attachment); the existing "edits will be lost" warning stays scoped to the
  pack.
- Import cap 100 cards per request; oversized → 422.

## Testing

- **shared:** contract validators (mcq/cloze/short_answer rules, caps,
  golden `cards.json` fixture round-trip).
- **worker:** `pipeline/cards.py` with `FakeProvider`; replace semantics
  (drafts replaced, accepted/imported preserved); `cards_status` transitions
  including the failure path; task wiring.
- **api:** all five endpoints — ownership (404), validation (422), state
  guards (400/409), append semantics, PATCH per-type re-validation.
- **web:** CardsView list render (both shapes), accept/reject optimistic
  update + rollback, import dialog error display, generate poll flow.
- Contract regen + gates per layer: `just gen-client` · `just lint` ·
  `just test`.

## Out of scope / deferred

- Cards export job (`job_kind: "cards"` tar for Claude Code) — same contract,
  different packaging.
- `auto_cards` toggle (auto-run generation after digest).
- Concept extraction / linking; Library, KB, and Concept pages; cross-source
  card browsing (Library "Cards" chip) — the S3 proper slices.
- Batch review gate + auto-approve (parked, see Spec amendments).
- Dedupe/merge across supplies.
- Scheduling/mastery fields and consumption of `accepted` (S5).
- Block-level card linkage ("cards from this block").
- Mobile client (deferred per CLAUDE.md).

## File-change inventory

| Layer | File | Change |
|---|---|---|
| Shared | `services/shared/gulp_shared/contracts/cards.py` (new) | `CardDraft` / `CardsPayload` + validators. |
| Shared | `services/shared/gulp_shared/models/card.py` | `CardOrigin.imported`. |
| Shared | `services/shared/gulp_shared/models/source.py` | `cards_status` column. |
| Migration | `services/api/alembic/versions/*` (new) | Enum value + column. |
| Worker | `services/worker/app/pipeline/cards.py` (new) | Generation stage. |
| Worker | `services/worker/app/prompts/cards.py` (new) | Card-drafting prompt. |
| Worker | `services/worker/app/tasks.py` | Register `generate_cards`. |
| Worker | `services/worker/app/export/templates.py` | Emit `schema/cards.schema.json`. |
| API | `services/api/app/routers/cards.py` (new) | Five routes. |
| API | `services/api/app/services/cards.py` (new) | Generation trigger, import, list, patch, delete. |
| API | `services/api/app/schemas/cards.py` (new) | `CardOut`, patch/import DTOs. |
| API | `services/api/app/schemas/capture.py` | `cards_status` on `SnapshotOut`. |
| Client | `packages/api-client/*` | Regenerate + typed helpers. |
| Web | `apps/web/components/snapshot/ReaderToggle.tsx` | Third segment. |
| Web | `apps/web/components/cards/*` (new) | CardsView, CardRow, ImportDialog. |
| Tests | (per Testing) | Per layer. |
