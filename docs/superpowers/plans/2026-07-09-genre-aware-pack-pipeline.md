# Genre-Aware Pack Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple the pack pipeline from paper-report semantics: detect a source's knowledge *genre* at parse time, store it, and dispatch pack production to a per-genre strategy — LLM deep-rewrite for papers (unchanged), deterministic zero-LLM markdown→blocks preservation for articles/notes.

**Architecture:** Three-axis model: `media_type` (format, exists) / `Source.genre` (new, detected + user-correctable) / `KnowledgePack.pack_type` (new, what was produced). `KnowledgePack` becomes the thin abstract base from docs/02 §4.4: `{title, summary, pack_type, status, extras JSON}` + the shared `PackSection`/`PackBlock` body substrate. A worker-side strategy registry maps genre → builder; fallback is always the preserve strategy (worst case = no enrichment, never misrepresentation).

**Tech Stack:** SQLAlchemy + Alembic (PG enums), Pydantic contracts, FastAPI, arq worker, Next.js + generated `@gulp/api-client`.

## Global Constraints

- Use `just` recipes, never raw tools: `just lint`, `just gen-client`, `just migrate-up`.
- Python tests run **per package**: `cd services/worker && uv run pytest` / `cd services/api && uv run pytest` (repo-root pytest collides on the `app` namespace).
- Web tests: `pnpm --filter @gulp/web test` (vitest, **classic JSX**: every JSX-bearing file including tests needs `import React`).
- All code/comments/commits/prompts in English. Commits end with the Claude Code trailer.
- `web`/`api-client` `tsc --noEmit` has 2 pre-existing dup-identifier errors in `schema.gen.ts` — ignore those two only.
- After changing `services/api/app/schemas`, run `just gen-client` before touching web.
- Keep `just lint` green at every commit.

---

### Task 1: PackDraft contract (worker, pure addition)

**Files:**
- Modify: `services/worker/app/pipeline/schemas.py`
- Test: `services/worker/tests/test_pipeline_schemas.py`

**Interfaces:**
- Produces: `PackDraft {title, summary: str|None, pack_type: Literal["paper","article"], extras: dict, sections: list[Section]}`, `draft_from_paper_report(report: PaperReport) -> PackDraft`, `CodeBlock {type="code", language: str|None, content: str}` added to the `Block` union, `FigureBlock.url: str | None = None`.

- [ ] **Step 1: Write failing tests** — append to `test_pipeline_schemas.py`:

```python
def test_code_block_in_union():
    section = Section(heading="h", blocks=[{"type": "code", "language": "python", "content": "x = 1"}])
    assert section.blocks[0].content == "x = 1"


def test_figure_block_url_optional():
    fig = FigureBlock(label="Figure 1", explanation="")
    assert fig.url is None


def test_draft_from_paper_report():
    report = PaperReport(
        title="T",
        core_contributions=["c1"],
        key_insight="k",
        sections=[Section(heading="h", blocks=[ProseBlock(content="p")])],
        references=[Reference(citation="c", why_interesting="w")],
    )
    draft = draft_from_paper_report(report)
    assert draft.pack_type == "paper"
    assert draft.extras["key_insight"] == "k"
    assert draft.extras["core_contributions"] == ["c1"]
    assert draft.extras["references"] == [{"citation": "c", "why_interesting": "w"}]
    assert draft.sections == report.sections
    assert draft.summary is None
```

- [ ] **Step 2: Run** `cd services/worker && uv run pytest tests/test_pipeline_schemas.py -v` — expect FAIL (names undefined).
- [ ] **Step 3: Implement** in `schemas.py`: `CodeBlock` model, add to `Block` union, `url` field on `FigureBlock`, then:

```python
class PackDraft(BaseModel):
    """Generic persist-boundary contract every strategy produces."""

    title: str
    summary: str | None = None
    pack_type: Literal["paper", "article"]
    extras: dict[str, Any] = Field(default_factory=dict)
    sections: list[Section] = Field(min_length=1)


def draft_from_paper_report(report: PaperReport) -> PackDraft:
    return PackDraft(
        title=report.title,
        pack_type="paper",
        extras={
            "key_insight": report.key_insight,
            "core_contributions": list(report.core_contributions),
            "references": [r.model_dump() for r in report.references],
        },
        sections=report.sections,
    )
```

- [ ] **Step 4: Run tests** — expect PASS. Also run full worker suite.
- [ ] **Step 5: Commit** `feat(worker): PackDraft contract + code block type`

---

### Task 2: Schema switch — ORM, migration, and all column consumers (atomic)

**Files:**
- Modify: `services/shared/gulp_shared/models/source.py` (add `SourceGenre`, `Source.genre`)
- Modify: `services/shared/gulp_shared/models/knowledge_pack.py` (add `PackType`, `pack_type`, `summary`, `extras`; drop `key_insight`/`core_contributions`/`references`; `PackBlockType.code`)
- Create: `services/api/alembic/versions/<rev>_genre_aware_packs.py`
- Modify: `services/worker/app/pipeline/persist.py` (accept `PackDraft`)
- Modify: `services/worker/app/pipeline/run.py:74-75` (`persist_pack(db, source, draft_from_paper_report(digest))`)
- Modify: `services/worker/app/export/jobs.py:106-107` (wrap import in `draft_from_paper_report`)
- Modify: `services/worker/app/pipeline/cards.py` (`render_pack_text` reads summary/extras; `_render_block` code branch)
- Modify: `services/api/app/schemas/pack.py` (`PackOut` + `pack_type`, `summary`; paper fields optional; `CodeBlockOut`/`CodeWrite`; `url` on figure schemas)
- Modify: `services/api/app/services/pack.py:57-65` (project from extras)
- Modify: `services/api/app/services/chat.py:65` (key_insight from extras)
- Tests: `services/worker/tests/test_persist.py`, `test_cards.py`, api pack tests

**Interfaces:**
- Consumes: `PackDraft`, `draft_from_paper_report` (Task 1).
- Produces: ORM `Source.genre: SourceGenre|None` (`paper|article|note`), `KnowledgePack.pack_type: PackType` (`paper|article`), `.summary: str|None`, `.extras: dict`; `persist_pack(db, source, draft: PackDraft)`; API `PackOut.pack_type/summary` with `key_insight: str|None`, `core_contributions: list[str] = []`.

- [ ] **Step 1: ORM changes.** `source.py`:

```python
class SourceGenre(enum.StrEnum):
    """Knowledge genre — what kind of knowledge artifact this is (not the media
    format). Detected at parse time, user-correctable; drives the pack strategy."""

    paper = "paper"
    article = "article"
    note = "note"
```

plus on `Source`: `genre: Mapped[SourceGenre | None] = mapped_column(Enum(SourceGenre, name="source_genre"), default=None)`.

`knowledge_pack.py`: add `PackType(enum.StrEnum)` with `paper`/`article`; on `KnowledgePack` replace the three paper columns with:

```python
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    pack_type: Mapped[PackType] = mapped_column(Enum(PackType, name="pack_type"))
    extras: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
```

and add `code = "code"` to `PackBlockType`.

- [ ] **Step 2: Migration** (revision `a7b8c9d0e1f2`, down_revision `f6a7b8c9d0e1`):

```python
def upgrade() -> None:
    op.execute("ALTER TYPE pack_block_type ADD VALUE IF NOT EXISTS 'code'")
    sa.Enum('paper', 'article', 'note', name='source_genre').create(op.get_bind())
    op.add_column('sources', sa.Column(
        'genre', postgresql.ENUM(name='source_genre', create_type=False), nullable=True))
    op.execute("""
        UPDATE sources SET genre = (CASE
            WHEN origin_url IS NULL THEN 'note'
            WHEN origin_url ILIKE '%arxiv.org%' OR origin_url ILIKE '%openreview.net%' THEN 'paper'
            WHEN media_type = 'pdf' THEN 'paper'
            ELSE 'article' END)::source_genre
        WHERE kind = 'snapshot'
    """)
    sa.Enum('paper', 'article', name='pack_type').create(op.get_bind())
    op.add_column('knowledge_packs', sa.Column(
        'pack_type', postgresql.ENUM(name='pack_type', create_type=False), nullable=True))
    op.add_column('knowledge_packs', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('knowledge_packs', sa.Column(
        'extras', sa.JSON(), nullable=False, server_default='{}'))
    op.execute("""
        UPDATE knowledge_packs SET pack_type = 'paper',
            extras = json_build_object(
                'key_insight', key_insight,
                'core_contributions', core_contributions,
                'references', "references")
    """)
    op.alter_column('knowledge_packs', 'pack_type', nullable=False)
    op.drop_column('knowledge_packs', 'key_insight')
    op.drop_column('knowledge_packs', 'core_contributions')
    op.drop_column('knowledge_packs', 'references')
```

Downgrade restores the three columns from extras, drops new columns/enums, and rebuilds `pack_block_type` without `'code'` via the rename-recreate dance (safe only if no code blocks exist — note it).

- [ ] **Step 3:** `persist.py` — signature `persist_pack(db, source, draft: PackDraft)`; pack row gets `title=draft.title, summary=draft.summary, pack_type=PackType(draft.pack_type), extras=draft.extras, status=ready`; section/block loop unchanged.
- [ ] **Step 4:** `run.py` + `export/jobs.py` call sites wrap with `draft_from_paper_report(...)`.
- [ ] **Step 5:** `cards.py` — `_render_block` gains:

```python
    if block.block_type is PackBlockType.code:
        lang = data.get("language") or ""
        return f"```{lang}\n{data.get('content', '')}\n```"
```

`render_pack_text` header becomes extras-driven (no dispatch):

```python
    parts = [f"# {pack.title}"]
    if pack.summary:
        parts.append(pack.summary)
    extras = pack.extras or {}
    if extras.get("key_insight"):
        parts.append(f"Key insight: {extras['key_insight']}")
    if extras.get("core_contributions"):
        parts.append("Core contributions:")
        parts += [f"- {c}" for c in extras["core_contributions"]]
```

(references likewise from `extras.get("references")`).

- [ ] **Step 6:** API `schemas/pack.py` — `PackOut`: add `pack_type: PackType`, `summary: str | None`; make `key_insight: str | None = None`, `core_contributions: list[str] = []`, `references: list[PackReferenceOut] = []`. Add `CodeBlockOut`/`CodeWrite {language: str | None = None, content: str}` to both unions; add `url: str | None = None` to `FigureBlockOut`/`FigureWrite`. `services/pack.py::pack_out` projects from `pack.extras`. `chat.py:65` reads `(pack.extras or {}).get("key_insight", "")`.
- [ ] **Step 7:** Update worker + api tests that construct packs with old columns. Run both suites per-package — expect PASS.
- [ ] **Step 8:** `just migrate-up` against local infra (`just up` first if down). Verify: `psql` check that an existing pack has `pack_type='paper'` and populated extras.
- [ ] **Step 9: Commit** `feat: generalize KnowledgePack to thin base + pack_type/extras; Source.genre`

---

### Task 3: Genre classifier (worker, zero LLM)

**Files:**
- Create: `services/worker/app/pipeline/classify.py`
- Modify: `services/worker/app/pipeline/run.py` (set `source.genre` when NULL)
- Test: `services/worker/tests/test_classify.py`

**Interfaces:**
- Produces: `detect_genre(origin_url: str | None, media_type: str) -> SourceGenre`.

- [ ] **Step 1: Failing tests** (`test_classify.py`) — table-driven:

```python
import pytest
from app.pipeline.classify import detect_genre
from gulp_shared.models.source import SourceGenre


@pytest.mark.parametrize(
    ("url", "media_type", "expected"),
    [
        (None, "note", SourceGenre.note),
        ("https://arxiv.org/abs/2607.001", "pdf", SourceGenre.paper),
        ("https://arxiv.org/pdf/2607.001v2", "pdf", SourceGenre.paper),
        ("https://openreview.net/forum?id=x", "article", SourceGenre.paper),
        ("https://example.com/whitepaper.pdf", "pdf", SourceGenre.paper),
        ("https://lilianweng.github.io/posts/2026-07-04-harness/", "article", SourceGenre.article),
    ],
)
def test_detect_genre(url, media_type, expected):
    assert detect_genre(url, media_type) == expected
```

- [ ] **Step 2:** Run — FAIL. **Step 3: Implement:**

```python
"""Genre detection — pure heuristics, no LLM (design: preserve is the safe fallback)."""

from gulp_shared.models.source import SourceGenre
from gulp_shared.urls import host_of

_PAPER_HOSTS = ("arxiv.org", "openreview.net")


def detect_genre(origin_url: str | None, media_type: str) -> SourceGenre:
    if origin_url is None:
        return SourceGenre.note
    host = (host_of(origin_url) or "").lower()
    if any(host == h or host.endswith("." + h) for h in _PAPER_HOSTS):
        return SourceGenre.paper
    if media_type == "pdf":
        return SourceGenre.paper
    return SourceGenre.article
```

- [ ] **Step 4:** In `run.py::process_source`, after `source.media_type` is set: `if source.genre is None: source.genre = detect_genre(source.origin_url, normdoc.media_type)` (never overwrite a user correction). Assert in `test_run.py` that a processed webpage source gets `genre == article` and a pre-set genre survives re-run.
- [ ] **Step 5:** Run worker suite — PASS. **Commit** `feat(worker): heuristic genre classifier wired into process_source`

---

### Task 4: NormDoc.description + adapter metadata

**Files:**
- Modify: `services/worker/app/pipeline/normdoc.py` (`description: str | None = None`, cleaned in validator)
- Modify: `services/worker/app/pipeline/adapters/webpage.py` (`extract_markdown` also returns `meta.description`; `webpage_to_normdoc` fills it)
- Tests: `services/worker/tests/test_normdoc.py`, `test_adapter_webpage.py`

- [ ] **Step 1:** Failing test: webpage fixture with `<meta name="description" content="...">` yields `normdoc.description == "..."`; NormDoc default is None.
- [ ] **Step 2:** Implement (trafilatura `extract_metadata(html).description`). Run suite — PASS.
- [ ] **Step 3: Commit** `feat(worker): carry page meta description on NormDoc`

---

### Task 5: Preserve strategy — deterministic markdown → blocks

**Files:**
- Create: `services/worker/app/pipeline/strategies/__init__.py` (empty for now)
- Create: `services/worker/app/pipeline/strategies/preserve.py`
- Test: `services/worker/tests/test_strategy_preserve.py`

**Interfaces:**
- Produces: `build_preserve_draft(normdoc: NormDoc) -> PackDraft` (pure, sync, zero LLM).

Transformation rules (input = NormDoc `content_body` markdown):
1. Fenced ``` blocks → `code {language, content}` (state machine first, so nothing inside a fence is misparsed).
2. `#`–`######` heading → starts a new section (flat; content before first heading goes to a `heading=None` intro section).
3. Paragraph classification (blank-line separated): image-only `![alt](url)` → `figure {label: alt or "Figure", explanation: "", url}`; `$$…$$` → `formula {latex, explanation: ""}`; pipe-table with `|---|` separator → `table`; all-bullet/all-ordered lines → `list`; else `prose` verbatim.
4. `summary` = `normdoc.description` else first prose paragraph truncated to 280 chars.
5. Guarantee ≥1 section: empty-ish body yields one intro section with one prose block of the whole body.
6. `pack_type = "article"`, `extras = {}`, `title = normdoc.title`.

- [ ] **Step 1: Failing golden test** — a fixture markdown exercising every rule (heading levels, fenced python code, pipe table, standalone image, `$$` math, ordered+unordered lists, prose with inline `$x$`), asserting the exact section/block sequence, plus: summary-from-description, summary-from-first-paragraph fallback, empty-body single-section guarantee, code fence containing `# not a heading` stays one code block.
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement `preserve.py` (~120 lines: `_split_fences`, `_paragraphs`, `_classify_paragraph`, `_parse_table`, `build_preserve_draft`).
- [ ] **Step 4:** Run suite — PASS. **Commit** `feat(worker): preserve strategy — deterministic markdown-to-blocks article packs`

---

### Task 6: Strategy registry + run.py dispatch + export gate

**Files:**
- Create: `services/worker/app/pipeline/strategies/paper.py` (async wrapper: `run_digest` → `draft_from_paper_report`)
- Modify: `services/worker/app/pipeline/strategies/__init__.py` (registry)
- Modify: `services/worker/app/pipeline/run.py` (dispatch on `source.genre`)
- Modify: `services/api/app/routers/export.py::export_snapshot` (400 unless `source.genre == SourceGenre.paper`)
- Tests: `services/worker/tests/test_run.py`, api export tests

**Interfaces:**
- Produces: `build_pack_draft(genre, normdoc, *, provider, config) -> PackDraft` — the single entry `run.py` calls; paper → LLM path, everything else (article/note/None/unknown) → preserve.

- [ ] **Step 1: Failing tests:** in `test_run.py` — processing a webpage source produces a pack with `pack_type == article` and **no LLM call** (inject a provider stub that raises if called); an arxiv-URL source still goes through the digest provider and lands `pack_type == paper`; a note source → article-type pack. API test: export on an article-genre snapshot → 400.
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement:

```python
# strategies/__init__.py
async def build_pack_draft(genre, normdoc, *, provider=None, config=None) -> PackDraft:
    if genre is SourceGenre.paper:
        return await build_paper_draft(normdoc, provider=provider, config=config)
    return build_preserve_draft(normdoc)  # article, note, and any future/unknown genre
```

`run.py::process_source` replaces the `run_digest` call with `draft = await build_pack_draft(source.genre, normdoc, provider=provider, config=config)` then `persist_pack(db, source, draft)`. Export router raises `HTTPException(400, "digest jobs only apply to paper sources")` for non-paper genre.

- [ ] **Step 4:** Run both suites — PASS. **Commit** `feat: genre-dispatched pack strategies; digest export gated to papers`

---

### Task 7: Cards prompt wording

**Files:**
- Modify: `services/worker/app/prompts/cards.py` ("name the paper/method they refer to" → "name the source/method they refer to")
- Test: existing `test_cards.py` prompt assertions if any.

- [ ] **Step 1:** Edit, run worker suite, **commit** `chore(worker): de-paper the cards prompt wording`

---

### Task 8: API surface — genre exposure + PATCH + regenerate client

**Files:**
- Modify: `services/api/app/schemas/capture.py` (`SnapshotOut.genre: SourceGenre | None`; new `SnapshotPatch {genre: SourceGenre}`)
- Modify: `services/api/app/routers/capture.py` (add `PATCH /snapshots/{snapshot_id}`)
- Test: api capture tests
- Run: `just gen-client`

- [ ] **Step 1: Failing test:** PATCH sets genre, returns updated SnapshotOut; 404 for other users' snapshots.
- [ ] **Step 2:** Implement — thin router per api CLAUDE.md: ownership check (reuse the module's existing owned-source lookup), assign, commit, return `SnapshotOut.model_validate(source)` shape used by `get_snapshot`.
- [ ] **Step 3:** Suites PASS → `just gen-client` → **commit** `feat(api): expose + patch Source.genre; regen client`

---

### Task 9: Web — code blocks, figure URLs, per-type header, genre control

**Files:**
- Modify: `apps/web/lib/packEdit.ts` (`emptyContent` case `"code"` → `{type: "code", language: null, content: ""}`)
- Modify: `apps/web/components/snapshot/BlockView.tsx` (case `"code"` → `<pre><code>`; figure case renders `<img src={block.url}>` when `figure_id` is null and `url` set)
- Create: `apps/web/components/snapshot/editors/CodeEditor.tsx` (textarea + language input, same EditorShell pattern as ProseEditor)
- Modify: `apps/web/components/snapshot/editors/BlockEditor.tsx` (dispatch `"code"`), `AddBlockMenu.tsx` (add entry)
- Modify: `apps/web/components/snapshot/PackReport.tsx` (article header: render `pack.summary` paragraph + origin link when `pack.pack_type === "article"`; paper sections already conditional on non-empty fields)
- Create: `apps/web/components/snapshot/GenreSelect.tsx` (chip + dropdown → `updateSnapshot` PATCH; on change, hint to re-run processing) wired into `apps/web/app/snapshots/[id]/page.tsx`
- Tests: `BlockView.test.tsx`, `PackReport.test.tsx`, `editors/textEditors.test.tsx`, new `GenreSelect.test.tsx` (all with `import React`)

- [ ] **Step 1:** Failing vitest cases: code block renders `<pre>`; figure block with `url` and no `figure_id` renders remote `<img>`; PackReport with `pack_type: "article"` + summary shows summary and no "Core contributions"; GenreSelect fires PATCH.
- [ ] **Step 2:** Implement components. **Step 3:** `pnpm --filter @gulp/web test` PASS; `just lint` green.
- [ ] **Step 4: Commit** `feat(web): article pack reader — code blocks, remote figures, summary header, genre control`

---

### Task 10: Docs + final verification

**Files:**
- Modify: `docs/02-data-model.md` (§4.3 Source gains `genre` row; §4.4: base gains `extras`, PackSection/PackBlock promoted to the shared body substrate of all pack types, `code` block type, `ArticlePack (pack_type=article)` implementation; §8 new decision row: genre→strategy registry, preserve fallback, zero-LLM article path)
- Modify: `docs/subsystems/S2-processing-design.md` (pipeline flow gains `classify` stage; strategy table; note that the digest-export job applies to `genre=paper` only)

- [ ] **Step 1:** Amend docs (English).
- [ ] **Step 2:** Full verification: `just lint`; `cd services/api && uv run pytest`; `cd services/worker && uv run pytest`; `pnpm --filter @gulp/web test`.
- [ ] **Step 3:** E2E: `just dev` (single worker! kill stale ones), capture `https://lilianweng.github.io/posts/2026-07-04-harness/`, process → verify `genre=article`, pack is verbatim sections/blocks with code blocks + images, zero LLM calls in worker log; re-run an arxiv source → still a paper report.
- [ ] **Step 4: Commit** `docs: genre-aware pack pipeline (02 §4.3-4.4, S2)`
