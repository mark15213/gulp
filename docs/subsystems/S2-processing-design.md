# S2 — Processing & Knowledge Pack · subsystem design

*Gulp · subsystem design doc · v0.9 **draft (brainstorm closed out)** · 2026-06-24*

> **⚠️ SUPERSEDED IN PART (2026-07-03).** Later owner decisions override parts of this doc; the pipeline mechanics (adapt→digest→cards, `NormDoc`, the job-spec ↔ executor seam incl. the `export`-to-Claude-Code path, manual trigger, provider-agnostic LLM layer) still stand. What changed:
> - **Pack model** — `KnowledgePack` is now a **thin abstract type + per-`pack_type` implementations** (`02 §4.4`); the paper report is the `PaperPack` implementation. The **facet-annotation layer (`PackElement`; C2 / C12 / C15, §3.2 / §3.5) is dropped** — there are no facets; cards are generated from the pack's rendered content.
> - **Card types** are now **`flashcard · mcq · cloze`** (`02 §4.5`), not the six referenced in §4 / C15.
> - **Lifecycle** — references to `awaiting_review` / `in_library` are superseded by the **single-gate** model (`ready` = in the library; `02 §6`).
> - **Genre-aware dispatch (2026-07-09, implemented — `02` D8).** The pipeline gained a **classify** stage and a **strategy registry**: `fetch → adapt (NormDoc) → classify (Source.genre, pure heuristics: arxiv/openreview or pdf → paper; no URL → note; else article) → strategy(genre) → persist`. `genre=paper` keeps the LLM digest of §3 (`PaperPack`); **every other genre — article, note, unknown — takes the zero-LLM preserve strategy** (`ArticlePack`): the NormDoc markdown deterministically re-shaped into the shared section/block substrate (headings → sections; fenced code → `code` blocks; pipe tables, standalone images with remote `url`, `$$` math, lists; the rest verbatim prose; `summary` from meta description or first paragraph). The genre is user-correctable (PATCH + re-run) — that is the escape hatch for a blog you *want* deep-read, or a non-paper PDF. **The `export`-to-Claude-Code digest job applies to `genre ∈ {paper, null}` only** — non-paper genres digest locally at zero AI cost, so there is nothing to outsource. §2.1's "one type-agnostic path" for B (Digest) is superseded by this dispatch; C (Cards) stays type-agnostic via the rendered pack.
>
> Kept as the S2 build record; it will be re-authored when the pack pipeline is rebuilt to the thin-pack model.

> Spins out of [`04-development-plan.md §6`](../04-development-plan.md) and resolves the **S2 charter** (`04 §4 S2`) into buildable detail. Sits below the four product docs (`01` flows / `02` objects / `03` look) and the `05` layout, and grows the `process_snapshot` placeholder that [`S1`](S1-capture-inbox-design.md) left behind.
>
> **Altitude:** one capability, end to end — turn a `Snapshot` into a human-readable **Knowledge Pack** (+ draft `Card`s + concept links). Stops *above* S3's review/commit gate, S5's scheduling, and S6's conversation engine (it only leaves hooks for them).
>
> **STATUS — brainstorm closed out, pending final owner review + fold-back into `01`/`02`.** All design forks are resolved in the C-series (§10); what remains (§8) is implementation-tuning, not design. The §3/§7 changes are *proposed amendments* to `02 §4.4`, and §2.4 a deliberate *relaxation of `01`'s auto-processing principle* — both flow back into `01`/`02` once this doc is approved (`04 §6`). Both owner items (§2.4 manual trigger, §3.6 report language) are **signed off (2026-06-24)**.

---

## 1. Scope & reading guide

- **Covers:** the worker pipeline behind `process_snapshot` — fetch/parse, the **Knowledge Pack as a re-authored readable report**, draft-card generation, concept linking, `confidence`/degradation, the **job-spec / executor seam** (run inline · export · user-authored), and a **provider-agnostic LLM service layer**.
- **The cut follows the charter** (`04 §4 S2`): *"content fetch / parse / extract; chunking for long content; pack-element generation; draft-card generation; `Concept` normalization & linking; the `confidence` signal."*
- **Out of scope (handed off):** review/commit gate + curation UI (S3); the reading-UI *implementation* (03/S3 — S2 only fixes the data structure that makes it buildable); scheduling (S5); the chat engine + sediment (S6 — S2 only leaves the anchor hook); the depth of the eval harness (its own doc).
- **What S1 left as floor:** a `Source` row, `content_body` null for links, `pack_id` not yet a column, and the stable seam `process_snapshot(ctx, snapshot_id)`. **NOTE — §2.4 changes one S1 behavior:** capture no longer auto-enqueues processing (see §2.4 + §7.4).

---

## 2. The pipeline architecture (the spine)

### 2.1 Three layers, two unification seams **[decided]**

```
   extract (mechanical, no LLM)      understand (LLM)
┌──────────────────┐ ←seam→ ┌──────────────────────────────┐
│ A. Adapt          │        │ B. Digest          C. Project │
│   →  NormDoc      │   →    │   →  Knowledge Pack   →  Cards│
└──────────────────┘        └──────────────────────────────┘
   one adapter per input type        one type-agnostic path
```

- **A — Adapt → `NormDoc`:** the only place input-type-specific code lives. Deterministic for text inputs (no LLM); ASR/OCR for audio/video/image (a model, but not the LLM — stays on the extraction side).
- **B — Digest → Knowledge Pack:** the heaviest LLM stage — the "understanding."
- **C — Project → Cards:** the LLM projects the pack into testable cards.

**The real AI boundary is `extract (mechanical)` vs `understand (LLM)`, not "NormDoc vs Card."** `NormDoc` is the seam — cheap, deterministic, cacheable plumbing cleanly separated from expensive, evaluable, fallible LLM work.

### 2.2 `NormDoc` — the unified intermediate representation **[decided]**

```
NormDoc {
  title, lang, media_type,
  blocks: [ { text, section_label?, anchor } ]   // ordered; anchor = a coordinate back to the source
}
```

`anchor` is load-bearing: char-range for text, page for PDF, timestamp for video. It lets every downstream pack block / card point **back into the source** — grounding, "open original," citation chips. `NormDoc` is **persisted** (with anchors) — it grounds the report, and it is the payload of the `export` job spec (§2.4).

| media_type | parse → blocks | anchor |
|---|---|---|
| webpage / article | readability extract → split by heading | char range |
| note | whole body = one block (trivial) | — |
| pdf *(deferred w/ blob)* | per-page text → split by page/heading | page |
| video / podcast *(deferred)* | transcript → split by segment/turn | timestamp |
| screenshot *(deferred)* | OCR → split by layout | — |

**Adding a new input type = one new A-layer adapter; B and C don't change.**

### 2.3 Unification = type-aware single digest path **[decided — C7]**

One digest path (one prompt set to maintain + eval), receiving a lightweight **type hint** (e.g. "video transcript, timestamps available — cite them"). Unified, without discarding type signal.

### 2.4 Job-spec ↔ executor seam + **manual trigger** **[decided — C4/C11]**

`process_snapshot` does **not** call any LLM API directly. It **assembles a portable, declarative job spec** (`NormDoc` + which digest workflow + the expected output schema + model config) and hands it to a **pluggable executor**:

| executor | who runs it | status |
|---|---|---|
| `inline` | the worker calls the LLM service layer (§2.6) | **v1** |
| `export` | export job as a `tar` → user's **Claude Code / Codex** runs it → import result `tar` | **[deferred]** — saves metered-API cost |
| `custom` | a **user-authored skill / workflow** over `NormDoc` | **[deferred]** |

**Manual-trigger UX (the v1 model):** a captured snapshot lands **not-started** (its job spec prepared but no LLM run kicked off). The user then chooses:
- **▶ Start** → runs the `inline` pipeline (`not-started → processing → ready`).
- **⤓ Upload** → the result was produced outside (`export`); import & parse the result tar directly (`not-started → ready`), no API call.

**`export` tar shape (sketch):** `job/`(`norm_doc.json` + prompts + `output.schema.json` + manifest with `snapshot_id` + spec version) → `result/`(`pack.json` + `cards.json` + `figures/`). Import **strictly validates against the schema**, is **idempotent**, and handles a snapshot deleted/changed since export.

> **Divergence from `01`/`02` — owner-approved (2026-06-24).** `01` promises processing is *automatic & invisible-until-ready*; manual-trigger relaxes that, deliberately, for cost control. **v1 is manual-only:** every snapshot waits at *not-started* for ▶ Start / ⤓ Upload. An `auto_process` setting (auto-call Start on capture, mirroring `auto_approve`) is a **trivial future toggle** (§9), not built in v1. This relaxation flows back as a note to `01` (§7.2).

### 2.5 Two LLM turns: pack, then cards **[decided — C8]**

`digest → pack`, then `(pack + NormDoc) → cards`. Each prompt focused + separately evaluable + can use a different model/provider; cards ground on a finalized pack; the pack flips to `ready` first (incremental readiness), cards arrive after. Both turns run within one `process_snapshot` execution (§7.4).

### 2.6 Provider-agnostic LLM service layer **[decided — C10]**

`services/worker/app/llm/` exposes **one provider-agnostic interface** — roughly `complete(messages, *, schema, model_config) -> validated object` — behind which sit per-provider adapters: **Anthropic** (v1 default; key already wired), **OpenAI**, **Qwen**, … . Provider + model + params are **chosen by config** (`settings` / job spec), **per stage** (digest, cards, and figures may each use a different model/provider).

- **Structured output is normalized across providers** (Anthropic tool-use · OpenAI JSON/function-calling · Qwen's equivalent) so callers always get a schema-validated object. The layer designs to the **lowest common denominator** (JSON-schema prompting + validation + bounded retry), with tool-use as a fast path where available.
- The `output.schema.json` in the `export` job spec is the same schema the inline path validates against — one contract, three executors.
- Model identity stays **in config, not code**, so the owner configures models later without touching the pipeline.

---

## 3. The Knowledge Pack as a readable report **[decided — major shift from `02 §4.4`]**

### 3.1 What the pack *is*

The materialized **understanding** of a source — "what I actually understood after reading this." **Reading-first**: a document broken apart, summarized, **rewritten**, and supplemented with background into a **complete, paginated report** read in app/web. Explicitly *not* a summary (`00`) and not a flat list of facets. It is the core "digestion" deliverable; cards and concepts flow *out of* it.

| part | flows to | meaning it serves |
|---|---|---|
| the rewritten report (sections/blocks) | **read** | the digestion deliverable |
| key terms / people-orgs | → `Concept` | wires into the graph |
| connections | → `ConceptEdge` | wires into the graph |
| claims / counter-views | read + promotable to `Card` | read now, test later |

### 3.2 Data structure — report as spine, facets as annotations

```
KnowledgePack { summary, confidence, status, sections: PackSection[] }
PackSection   { heading, blocks: PackBlock[] }
PackBlock     { type: prose | figure | callout | quote,
                content,            // prose text, or a figure ref (mermaid source / blob ptr)
                source_anchor,      // back into NormDoc — grounding + "open original"
                anchor_id }         // stable id: chat / annotations / cards attach here
```

The **facets don't disappear** — `PackElement` (terms/claims/counter-views/connections) still exists for the graph + cards — but is **re-roled from "the body" to annotations** referencing a `PackBlock.anchor_id`.

> **Rewriting raises the grounding stakes.** A re-authored report can drift (hallucination), so every block *must* anchor back to `NormDoc`. The `anchor` is the load-bearing wall — it powers "open original," citation chips, and card/chat grounding.

### 3.3 The pack is a *living* document **[decided — C6]**

Generation produces v1, but the report **grows**: user-triggered figures (§3.4) and accepted chat sediment (S6) append new blocks at their anchors. Not frozen after generation.

### 3.4 Figures — on-demand, user-triggered, anchored **[decided — C5; raster deferred]**

No blanket auto-illustration. While reading, the user pops chat at a hard spot and asks (button or text) for a figure; the AI generates one, saved back as a `PackBlock(type=figure)` at that anchor. Demand-driven ⇒ cost paid only at real comprehension barriers.

- **mermaid / diagram-as-code:** text-only, no blob — **ships early.**
- **raster / AI-drawn images:** need blob storage — **deferred with the blob layer.**
- Crosses subsystems: chat entry = S6, figure-as-block = S2, reading UI = 03/S3 (§9).

### 3.5 Review granularity **[decided — C12]**

Keep/dismiss operates on the **facet-annotations** (terms/claims/counter-views/connections) and **draft cards** (accept/reject) — the things that flow into the graph + scheduling. The **report prose (sections/blocks) is not keep/dismiss'd**: it is read, and *editable* in web deep-curation. Mobile batch-confirm = "approve all facets + cards."

### 3.6 Report language **[decided — C14]**

The rewritten report is authored in **English** in v1, regardless of source language (a `zh` source is digested *into* English). Fixed, not per-user-configurable, for v1 — a config knob is a later add. (`02 §10` fixes UI `locale ∈ {zh·en}`; this is a pack-authoring choice, independent of UI locale.)

---

## 4. Generation details

- **Chunking = content-length tiering [decided — C13]:** tiers by `NormDoc` token count (config-tunable defaults): **short ≤ ~6k** → whole report in one digest pass; **long ~6k–30k** → per-section digest (map-reduce) with `section_label` + anchor keying cards to their section; **very long > ~30k** → per-section, eager for the first sections and **lazy/on-demand** for the rest. The map-reduce **reduce** step takes the per-section summaries + facet lists and writes the pack-level `summary`/`background` and a **deduped** concept/connection set.
- **Model choice [decided to defer — C10]:** selected by config via the LLM service layer; owner configures later. v1 default = Anthropic.
- **Card drafting [decided — C15]:** the **card turn** (§2.5) drafts cards from the facet-annotations — `claim`/`counter_view` are the primary seeds (testable assertions), `key_term`/`person_org` seed definitional cards. Type by affinity: term→`cloze`/`recall`/`short_answer`; claim→`short_answer`/`explain`/`apply`; counter_view→`explain`; a clear fact with good distractors→`mcq` (distractors generated in the same turn, plausible-but-wrong, grounded); `connection`→relation card (lower priority). Count is **budgeted by content tier** (short ≈ 3–6; long → 2–4 per section, total capped ≈ 20), config-tunable. Each card stores `answer` + a short **source-grounded explanation** (new `Card.explanation`, §7.2) and links to its seeding `PackBlock.anchor_id` + `Concept` (powers "Why am I seeing this?" + reveal). summary/background/connections are not auto-carded.
- **Cost/latency budget [config defaults — owner may tune]:** initial config ceilings (placeholders): short ≈ a few cents / <~30s; long scales with section count. manual-trigger (§2.4) + tiering are the cost levers. Owner sets real targets later.
- **Eval / card-quality rubric [decided — scoped]:** ship a **rubric** (card: testable? grounded? unambiguous? answer correct? · pack: faithful? non-hallucinated?) + a **~10–15 snapshot seed set** spanning short / long / thin / paywalled-partial / dense-technical / note, run by `app/eval/`. Harness *depth* (scoring automation, regression gating) is its own doc.

---

## 5. Concepts & the S2↔S3 boundary **[decided — C9]**

S2 **proposes** concept links as facet-annotations (link-to-existing where a normalized name/alias matches, else propose-new) and writes status `ready`. **S3 materializes** the actual `Concept` / `ConceptEdge` rows on commit, and owns `awaiting_review` / auto-approve. Concept normalization/dedupe (case/space/diacritic-folded name + `aliases`) lives in `gulp_shared/domain` so both can use it. **Precision bar [decided]:** match only on a **high-confidence exact/alias hit**; when unsure, propose-new and let S3 deep-curation merge — never silently merge two concepts (a wrong merge is costlier to undo than a duplicate). Fuzzy/embedding matching is deferred.

## 6. Confidence & degradation **[decided — framed by `02` invariant 9; thresholds tunable]**

| content situation | behavior | status / pack |
|---|---|---|
| thin / low-signal | report shows "only what's reliable, and says so" | `ready`, low `confidence` |
| extraction failed | banner + retry + open-original | `needs_attention` → `processing` (retry) |
| unsupported type | store raw, no pack, still taggable/searchable | `in_library`, `pack = null` |

- `confidence`: a **per-pack** float `0..1` in v1 (per-block deferred), from signal density (length, extraction completeness, ground-vs-infer ratio). **Below `0.5` (tunable default)** the report self-labels thin with a banner — copy: *"Limited source — only the reliable parts are shown."* The model emits its own confidence in the digest turn; deterministic signals clamp it.
- **Retry:** arq retries a transient fetch/LLM failure ≤2× with backoff; persistent failure → `needs_attention`, user re-runs via **▶ Start**. `process_snapshot` is **idempotent** — checks existing pack/status and replaces on re-run.

## 7. Data layer & worker **[outline]**

### 7.1 New models
`gulp_shared` (all `TimestampedBase, Base`): `KnowledgePack`, **`PackSection`**, **`PackBlock`**, `PackElement` (re-roled), `Card`, `Concept`, `ConceptEdge`, `CardConcept`, `SourceConcept`. `KnowledgePack.snapshot_id` models the 1–1 (no double FK). New Alembic migration `down_revision='00371ef138ba'`.

### 7.2 Proposed amendments to `02` (flow back once locked)
1. `KnowledgePack` gains `sections: PackSection[]` (the readable report).
2. New `PackSection` / `PackBlock` with block types + `source_anchor` + `anchor_id`.
3. `PackElement` re-roled to a facet-**annotation** referencing a `PackBlock.anchor_id`.
4. An **intra-pack anchor** model so S6 can anchor a conversation to a *block*, not just a whole object.
5. A new **not-started** snapshot status (§7.4).
6. `Card` gains `explanation: text?` (the source-grounded reveal explanation, §4).
7. A note back to **`01`**: S2 processing is **manual-trigger**, relaxing the auto / invisible-until-ready principle (§2.4).

### 7.3 Storage seams **[decided]**
- **async/sync:** v1 runs the sync `SessionLocal` work via `asyncio.to_thread` inside the async arq job (no async engine yet). Reversible.
- **JSON vs child tables:** the structured report → **child tables** (`PackSection`/`PackBlock` rows) to honor union-under-sync (`02` inv. 7) + per-block anchors/edits. `Card.options` (ordered, atomic, owned by one card) → a **JSON column** (the first one).
- **Job granularity:** v1 = one `process_snapshot` job orchestrating the stages in-process (fetch→parse→chunk→digest→cards→propose-concepts), not fanned into multiple arq jobs. Reversible.

### 7.4 Manual-trigger ripple into S1 **[decided]**
- New `Snapshot.status` value **`unprocessed`** (capture lands here; distinct from `queued`=offline-buffer and `processing`=inline run in progress). Transitions: `unprocessed → processing → ready` (Start) or `unprocessed → ready` (Upload import).
- S1's `create_snapshot` **stops auto-enqueuing**; the enqueue moves to a new **`POST /snapshots/{id}/process`** (Start, `inline`). A second **`POST /snapshots/{id}/import`** ingests an `export` result tar (Upload).
- The future `auto_process` toggle (§9) would have `create_snapshot` auto-call the Start path — restoring S1's original behavior as a setting, not a hardcode.

## 8. Open questions (the live queue)

The brainstorm is **closed out** — all decisions are in the C-series (§10). What remains is implementation-tuning, not design forks:

- **Prompt authoring** — the digest, card, and map-reduce merge prompts themselves (written during build, evaluated against the §4 seed set).
- **Tuning values** — chunking thresholds, card caps, confidence cut, cost ceilings — all land as config defaults and get tuned against real content.
- **`auto_process` / `export` / `custom`** remain deferred (§9).

v1 **input scope = webpage/article + note** (deferred types follow the blob layer) — **confirmed**.

## 9. Forward-looking / deferred (record now, build later)

- **`export` executor** — tar job spec run by Claude Code/Codex (§2.4); cost-saving mode.
- **`custom` executor** — user-authored skill/workflow over `NormDoc` (§2.4).
- **`auto_process` toggle** — auto-call ▶ Start on capture (restores `01`'s invisible-until-ready); v1 is manual-only (§2.4).
- **Raster figure generation** — needs blob storage; mermaid ships earlier (§3.4).
- **Intra-pack fine-grained anchors → S6** — chat anchored to a block; sediment appends back as pack blocks (§3.3/§3.4).
- **Deferred input types** — pdf/video/podcast/audio/screenshot, each a new A-layer adapter + blob/ASR/OCR (§2.2).

**v1 build slices (the S2 plans, sequenced) — S2 ships report-first:**
- **Plan 1 — data layer** (models + migration). *Done.*
- **Plan 2 — LLM service layer + `NormDoc` + adapters** (webpage/note). *Done.*
- **Plan 3 — Processing pipeline (report generation):** manual Start → fetch → adapt → one **digest turn** → `KnowledgePack` (report `PackSection`/`PackBlock`) + `PackElement` facets (text, `concept_id` null) → `ready`. v1 narrowings of the decisions above:
  - **Card generation → its own later plan** (refines C8 — only the digest turn runs in Plan 3; the card turn comes later).
  - **Long-content map-reduce deferred** (refines C13 — Plan 3 is single-pass with a token-budget guard: over-budget content is truncated and flagged low-`confidence`; per-section map-reduce is a follow-up).
  - **`PackBlock.source_anchor` left null in v1** (refines C3 — its consumers, citation chips / region "open original" / S6 chat, are all deferred; the digest prompt still enforces faithfulness to `NormDoc`; `origin_url` covers whole-source "open original").
  - **Concept/edge materialization stays S3** (C9) — facets are text only.
  - **Pipeline LLM provider is injectable** for hermetic tests (`FakeProvider`); real Start hits the API (manual trigger = cost-controlled).

## 10. Decisions log (C-series) — *draft*

| # | Decision | Status | Reversible? |
|---|---|---|---|
| C1 | Pipeline = `Adapt→NormDoc` (mechanical) · `Digest→Pack` (LLM) · `Project→Cards` (LLM); `NormDoc` is the unification seam | decided | yes |
| C2 | Pack is a **reading-first, re-authored, paginated report** (spine) + facets as **annotations** | decided (pending `02` amend) | hard |
| C3 | Every `PackBlock` anchors back to `NormDoc` | decided | yes |
| C4 | **Job-spec ↔ pluggable executor** seam; v1 = `inline` | decided | yes |
| C5 | Figures **on-demand, user-triggered, anchored**; mermaid early, raster deferred | decided | yes |
| C6 | Pack is a **living document** (figures + sediment append) | decided | yes |
| C7 | Unification = **type-aware single digest path** | decided | yes |
| C8 | Pack & cards in **two** LLM turns | decided | yes |
| C9 | S2 **proposes** concept links + writes `ready`; S3 materializes concepts/edges + review | decided | yes |
| C10 | **Provider-agnostic LLM service layer**; model/provider by config (Anthropic/OpenAI/Qwen); v1 default Anthropic | decided | yes |
| C11 | **Manual trigger is the v1 model** (principle relaxed, owner-approved): snapshot lands *not-started*; ▶ Start = inline, ⤓ Upload = import; `auto_process` a future toggle | decided | yes |
| C12 | Review = keep/dismiss on facet-annotations + cards; report prose read/editable, not keep/dismiss | decided | yes |
| C13 | Chunking = **content-length tiering** (short=one pass, long=per-section, very-long=lazy) | decided | yes |
| C14 | Report authored in **English** in v1, regardless of source language | decided | yes |
| C15 | Cards drafted from facet-annotations (claim/counter_view primary; term/person→definitional), type by affinity, count budgeted by tier; `Card.explanation` added | decided | yes |
| C16 | Ship a card/pack **eval rubric + ~10–15 snapshot seed set** (`app/eval/`); harness depth deferred | decided | yes |
| C17 | v1 **input scope = webpage/article + note**; other media deferred with the blob layer | decided | yes |

---

*Next: resolve §8 (detail-level), fold §7.2 amendments back into `01`/`02`, then spin an implementation plan.*
