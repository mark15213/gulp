# Paper Report Contract — End-to-End Redesign

Date: 2026-06-28
Status: Approved (design); pending implementation plan
Scope: The Gulp digest subsystem across `services/worker`, `services/shared`,
`services/api`, `packages/api-client`, and `apps/web`.

## Goal

Replace the generic `DigestResult` knowledge-pack contract with a
**`PaperReport`** contract that produces a technically deep, structured paper
interpretation. The reference for *content quality* is the redesigned job in
`gulp-job-extracted/` (its `schema/pack.schema.json`, `prompt.md`, `CLAUDE.md`,
and the BERT `result/pack.json`). That redesign currently lives **only** inside
the isolated job folder; this spec propagates it through the running system so
capture → generate → export → import → store → API → web all speak `PaperReport`.

The output stays a structured, schema-validated interface — it is a system
contract consumed across components, not a Markdown article.

## Decisions locked in

- **Scope: full stack, end-to-end.** The contract is propagated through every
  layer so the system stays internally consistent. No layer is left on the old
  shape.
- **Python is the source of truth.** The `PaperReport` Pydantic model in
  `services/worker/app/pipeline/schemas.py` is canonical: the importer validates
  against it, and the exported `schema/pack.schema.json` is *generated* from it
  (`PaperReport.model_json_schema()`), so the JSON Schema never drifts from
  Python. This honors the repo rule "the data model is the contract" (`docs/04
  §2.5`). The generated schema validates the same shapes as the hand-written one
  in `gulp-job-extracted/`; it just carries Pydantic's `$defs`/`discriminator`
  styling.
- **DB storage: normalized sections/blocks with JSON per block.** Keep
  `pack_sections` and `pack_blocks` (ordered rows); replace the block `content`
  text column with a `data` JSON column holding each variant's fields. Add
  `title` / `key_insight` / `core_contributions` / `references` to the
  `knowledge_packs` row. Drop `pack_elements` (facets are gone).
- **Frontend: KaTeX for math.** `formula` blocks render as typeset display math;
  `table` blocks render as real HTML tables; `list` blocks as `<ul>`/`<ol>`.
- **Pre-production migration, no data backfill.** The Alembic migration
  recreates structure cleanly; downgrade restores the old shape. There is no
  production pack data to preserve.
- **Dropped permanently:** `summary`, `background`, `confidence`, `facets`
  (`PackElement*`), `callout`/`quote` blocks, source anchoring
  (`anchor_id`/`source_anchor`/`content_ref`), and the generated `README.md`.

## ① The contract — `PaperReport` (Pydantic, worker)

`services/worker/app/pipeline/schemas.py` is rewritten to a discriminated-union
model. The `type` literals mirror the `PackBlockType` ORM enum exactly so persist
maps by string value.

### Blocks (discriminated union on `type`)

| `type` | Fields | Use |
|---|---|---|
| `prose` | `content: str` | Markdown prose; `**bold**`, inline `$math$`. |
| `formula` | `latex: str`, `explanation: str` | Display equation + one-line plain-language explanation. |
| `table` | `headers: str[]`, `rows: str[][]`, `caption?: str` | Results / baseline comparisons. |
| `figure` | `label: str`, `explanation: str` | No image available; describe the figure in words. |
| `list` | `items: str[]`, `ordered?: bool` | Hyperparameters, sub-points. |

`Block = Annotated[Union[ProseBlock, FormulaBlock, TableBlock, FigureBlock,
ListBlock], Field(discriminator="type")]`.

### Section / Reference / root

- `Section { heading: str, blocks: list[Block] }`
- `Reference { citation: str, why_interesting: str }`
- `PaperReport`:

  | Field | Type | Required | Notes |
  |---|---|---|---|
  | `title` | str | yes | Paper title. |
  | `core_contributions` | str[] (1–5) | yes | Concise standalone statements; primary skim entry. |
  | `key_insight` | str | yes | The single most transferable idea. |
  | `sections` | Section[] (≥1) | yes | Report body, ordered. |
  | `references` | Reference[] | no | Interesting follow-up references. |

`core_contributions` is a `list[str]` with `min_length=1, max_length=5`;
`sections` is a `list[Section]` with `min_length=1`.

## ② Prompts — authoring guide vs operating manual

`services/worker/app/prompts/digest.py`: `_SYSTEM` becomes the **authoring
guide** — the content of `gulp-job-extracted/prompt.md` (expert researcher &
reviewer role; the 7-section outline: Core Challenge / Overview of Approach /
Mathematical Formulation & Technical Details / What the Experiments Show /
Strengths & Limitations / Future Trajectories / One Potential Improvement; the 5
block types; faithfulness split — sections 1–4 strictly faithful, 5–7 reviewer
analysis). It is the single canonical string, reused two ways:

- `run_digest` (in-process LLM path) passes it as the system prompt.
- `services/worker/app/export/templates.py`:
  - `prompt_md()` emits it verbatim as `prompt.md`.
  - `claude_md()` emits a lean **operating manual** (what the job is, the file
    map, "follow `prompt.md` exactly", validate then stop) — matching
    `gulp-job-extracted/CLAUDE.md`.
  - `pack_schema()` returns `PaperReport.model_json_schema()`.
  - `readme_md()` is deleted.

## ③ Export builder + importer + digest stage

- `services/worker/app/export/builder.py`: file map becomes `CLAUDE.md`,
  `prompt.md`, `manifest.json`, `input/norm_doc.json`, `schema/pack.schema.json`,
  `result/HOWTO.txt` (drop `README.md`). `manifest.json` is unchanged
  (`format_version: 1`, `job_kind: "digest"`).
- `services/worker/app/export/importer.py`:
  `import_result_archive(data) -> PaperReport` validates `result/pack.json`
  against `PaperReport`.
- `services/worker/app/pipeline/digest.py`: keep the `MAX_DIGEST_CHARS`
  truncation guard; remove `_TRUNCATED_CONFIDENCE_CAP` and the confidence logic
  (confidence is gone). Return type becomes `PaperReport`.

## ④ DB model + migration

`services/shared/gulp_shared/models/knowledge_pack.py`:

- `KnowledgePack`: drop `summary` / `background` / `confidence`; add `title`
  (Text), `key_insight` (Text), `core_contributions` (JSON — `str[]`),
  `references` (JSON — `Reference[]`). Keep `snapshot_id`, `status`.
- `PackBlockType` enum → `prose` / `formula` / `table` / `figure` / `list`.
- `PackBlock`: drop `content` / `content_ref` / `source_anchor` / `anchor_id`;
  add `data` (JSON — the variant fields, e.g. `{latex, explanation}`). Keep
  `section_id`, `block_type`, `position`.
- `PackSection`: unchanged (`pack_id`, `heading`, `position`).
- Delete `PackElement`, `PackElementType`, `PackElementState`.

New Alembic migration (`just migrate`): drop `pack_elements` + its enum; rebuild
the `pack_block_type` enum; alter `knowledge_packs` and `pack_blocks` columns.
Downgrade restores the prior shape. No data backfill.

## ⑤ Persist

`services/worker/app/pipeline/persist.py`:
`persist_pack(db, source, report: PaperReport) -> KnowledgePack`.

- Write `title` / `key_insight` / `core_contributions` (list) / `references`
  (list of `{citation, why_interesting}`) onto the pack row; `status = ready`.
- Per section → `PackSection(heading, position=i)`.
- Per block → `PackBlock(block_type=PackBlockType(block.type),
  data=block.model_dump(exclude={"type"}), position=j)`.
- Remove facet writes, `_clamp`, and anchor handling. `_delete_existing` drops
  the pack's sections + blocks (no `pack_elements` anymore). Stays idempotent.

## ⑥ API contract + generated client

`services/api/app/schemas/pack.py`: define read DTOs mirroring the worker block
union — the same five variants as a discriminated union on `type`,
`PackSectionOut { heading, blocks }`, `PackReferenceOut { citation,
why_interesting }`, and:

```
PackOut { snapshot_id, status, title, core_contributions, key_insight,
          sections, references }
```

`services/api/app/services/pack.py`: rebuild each block as `{type, **data}`,
sections ordered by `position`; populate the new root fields; drop facets.

Then `just gen-client` regenerates `packages/api-client/src/schema.gen.ts`.

## ⑦ Frontend (apps/web)

- `components/snapshot/PackReport.tsx`: render `title`; `core_contributions` as a
  skim list; `key_insight` highlighted; then each section with a block renderer
  switching on `block.type` — `prose` (markdown + inline math), `formula` (KaTeX
  display math + explanation), `table` (`<table>` with optional caption),
  `figure` (label + explanation), `list` (`<ul>`/`<ol>`); a `references` section
  at the end. Key blocks by index (anchors are gone). Add **KaTeX** as an
  `apps/web` dependency.
- Delete `components/snapshot/FacetRail.tsx`; update
  `components/snapshot/ReaderToggle.tsx` to drop the facet rail.
- `lib/pack.ts`: remove `Facet` / `ElementType` / `FacetGroup` / `groupFacets` /
  `FACET_ORDER`; keep `isProcessing` / `statusLabel` / `safeHost`.

## ⑧ Tests

Update pinning tests alongside each layer, using the BERT `PaperReport` shape
(reuse `gulp-job-extracted/result/pack.json` as a golden fixture):

- `services/shared/tests/test_pack_models.py` — new columns/enum.
- `services/worker/tests/test_persist.py` — block `data`, root fields, no facets.
- `services/worker/tests/test_export_importer.py` — validates `PaperReport`.
- `services/worker/tests/test_export_builder.py` — emits `prompt.md`, not
  `README.md`; schema is the generated `PaperReport` schema.
- `services/worker/tests/test_prompt_digest.py` — new system prompt content.
- `services/api/tests/test_export.py` + any pack serializer test — new `PackOut`.
- `apps/web/components/snapshot/PackReport.test.tsx`,
  `apps/web/lib/pack.test.ts` — new rendering, facets removed.

Add a worker test asserting `PaperReport.model_json_schema()` accepts the BERT
golden fixture (proves the generated export schema matches the contract).

## Out of scope

- Markdown article output / standalone reader.
- Source anchoring / "dive into original location".
- Batch processing of multiple papers.
- Changing the Gulp upload / packaging workflow (manifest format, zip layout).
- Migrating existing pack data (pre-production; none to migrate).

## File-change inventory

| Layer | File | Change |
|---|---|---|
| Worker contract | `services/worker/app/pipeline/schemas.py` | Rewrite to `PaperReport`. |
| Worker prompt | `services/worker/app/prompts/digest.py` | New `_SYSTEM` authoring guide. |
| Worker export | `services/worker/app/export/templates.py` | `pack_schema` from `PaperReport`; `prompt_md`; lean `claude_md`; drop `readme_md`. |
| Worker export | `services/worker/app/export/builder.py` | New file map (add `prompt.md`, drop `README.md`). |
| Worker export | `services/worker/app/export/importer.py` | Validate `PaperReport`. |
| Worker pipeline | `services/worker/app/pipeline/digest.py` | Return `PaperReport`; drop confidence. |
| Worker persist | `services/worker/app/pipeline/persist.py` | Map `PaperReport` → rows; drop facets. |
| Shared model | `services/shared/gulp_shared/models/knowledge_pack.py` | New columns/enum; drop `PackElement*`. |
| Migration | `services/api/alembic/versions/*` | New revision. |
| API schema | `services/api/app/schemas/pack.py` | New `PackOut` + block union. |
| API service | `services/api/app/services/pack.py` | Rebuild blocks from `data`; drop facets. |
| Client | `packages/api-client/src/schema.gen.ts` | Regenerate via `just gen-client`. |
| Web | `apps/web/components/snapshot/PackReport.tsx` | New renderer + KaTeX. |
| Web | `apps/web/components/snapshot/ReaderToggle.tsx` | Drop facet rail. |
| Web | `apps/web/components/snapshot/FacetRail.tsx` | Delete. |
| Web | `apps/web/lib/pack.ts` | Drop facet helpers. |
| Tests | (per ⑧) | Update + golden fixture. |
