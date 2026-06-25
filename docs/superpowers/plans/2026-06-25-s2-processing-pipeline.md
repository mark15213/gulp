# S2 Processing Pipeline (Report Generation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow `process_snapshot` into the real report-generation pipeline — manual **Start** → fetch → adapt → one **digest** LLM turn → persist a `KnowledgePack` (re-authored report + facet annotations) → `ready` — plus the manual-trigger API (capture lands `unprocessed`; a Start endpoint enqueues processing).

**Architecture:** All worker code in `services/worker/app/`. A digest stage (`pipeline/digest.py`) turns a `NormDoc` (from Plan 2's adapters) into a pydantic `DigestResult` via `complete_structured` (Plan 2's LLM layer, provider-injectable for hermetic tests). A persist stage (`pipeline/persist.py`) maps `DigestResult` → ORM rows (Plan 1's models). An orchestration core (`pipeline/run.py`) wires fetch→adapt→digest→persist and drives status; `tasks/__init__.py` is the thin arq entry that opens a DB session and delegates. The API side adds `POST /snapshots/{id}/process` and switches capture to land `unprocessed` without auto-enqueuing.

**Tech Stack:** Python 3.13, pydantic 2, SQLAlchemy 2.0 (sync `SessionLocal`), arq, anthropic (via Plan 2's `app.llm`), trafilatura/httpx (via Plan 2's adapters), FastAPI, pytest + pytest-asyncio (`asyncio_mode=auto`).

## Global Constraints

- **Report-only slice** (S2 design §9): this plan generates the **report + facets**, NOT cards (deferred to a later plan) and NOT `Concept`/edge rows (S3). Facets are stored as `PackElement` text with `concept_id`/`block_id` null.
- **`PackBlock.source_anchor` stays `None`** in v1 (consumers deferred); the digest prompt enforces faithfulness instead. `origin_url` covers "open original".
- **Single digest turn + budget guard** (S2 design C13 v1): truncate `content_body` over `MAX_DIGEST_CHARS` and clamp `confidence ≤ 0.5`; no per-section map-reduce yet.
- **Manual trigger** (C11): capture lands `SnapshotStatus.unprocessed` and does **not** enqueue; `POST /snapshots/{id}/process` enqueues `process_snapshot`. Status path: `unprocessed → processing → ready`; any failure → `needs_attention` (no auto-retry in v1 — the user re-Starts).
- **Provider-injectable pipeline** for hermetic tests: `run_digest`/`process_source` accept a `provider`; tests pass a `FakeProvider` (no network, no `ANTHROPIC_API_KEY`). DB tests use in-memory SQLite (`Base.metadata.create_all`), exactly like `services/shared/tests`.
- **English everywhere** (CLAUDE.md rule 6): all code comments, the digest prompt, and commit messages in English.
- **`gulp_shared` imports in worker source files** carry `# type: ignore[import-untyped]` (gulp_shared has no `py.typed`; this matches the existing `app/llm/anthropic_provider.py`). New test functions get `-> None`.
- **Quality gate:** `cd services/worker && uv run pytest` and `cd services/api && uv run pytest` are GREEN. (Repo-wide `ruff`/`mypy` carry large pre-existing debt — api 55 / shared 21 mypy errors, ruff UP042 etc. — that is accepted baseline and NOT this plan's job. Keep new code clean and annotated, but pytest-green is the gate.)
- **TDD + a commit per task.**

---

## File Structure

- `services/worker/app/pipeline/schemas.py` *(new)* — `DigestBlock`/`DigestSection`/`DigestFacet`/`DigestResult` (the digest LLM's response contract).
- `services/worker/app/prompts/digest.py` *(new)* — `build_digest_messages(normdoc, body) -> (system, messages)`.
- `services/worker/app/pipeline/digest.py` *(new)* — `run_digest(normdoc, *, provider, config) -> DigestResult` + the budget guard.
- `services/worker/app/pipeline/persist.py` *(new)* — `persist_pack(db, source, digest) -> KnowledgePack` (idempotent; maps to ORM rows).
- `services/worker/app/pipeline/run.py` *(new)* — `process_source(db, source, *, fetch, provider, config)` + `_to_normdoc` + `PipelineError`.
- `services/worker/app/tasks/__init__.py` *(modify)* — `process_snapshot` opens `SessionLocal`, loads the `Source`, delegates to `process_source`.
- `services/api/app/services/processing.py` *(new)* — `start_processing(db, source, enqueue)`.
- `services/api/app/routers/processing.py` *(new)* — `POST /snapshots/{snapshot_id}/process`; registered in `app/main.py`.
- `services/api/app/services/capture.py` *(modify)* — land `unprocessed`, drop the enqueue.
- `services/api/app/routers/capture.py` *(modify)* — drop the `get_enqueue` dependency.
- Tests *(new/modified)*: `tests/test_pipeline_schemas.py`, `tests/test_prompt_digest.py`, `tests/test_digest.py`, `tests/test_persist.py`, `tests/test_run.py`, `tests/test_tasks.py` (worker); `tests/test_processing.py`, `tests/test_capture.py`, `tests/test_routers.py` (api).

Task order is dependency-driven: schemas → prompt → digest → persist → run → worker job → process API → capture change.

---

### Task 1: Digest response schemas

**Files:**
- Create: `services/worker/app/pipeline/schemas.py`
- Test: `services/worker/tests/test_pipeline_schemas.py`

**Interfaces:**
- Produces: `DigestBlock(type: Literal["prose","callout","quote"]="prose", content: str)`; `DigestSection(heading: str|None=None, blocks: list[DigestBlock])`; `DigestFacet(element_type: Literal["key_term","person_org","claim","counter_view","connection"], text: str)`; `DigestResult(summary: str, background: str|None=None, confidence: float=0.7, sections: list[DigestSection], facets: list[DigestFacet])`. All `pydantic.BaseModel`. The `Literal` values match `PackBlockType`/`PackElementType` string values exactly.

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_pipeline_schemas.py`:

```python
from app.pipeline.schemas import DigestBlock, DigestFacet, DigestResult, DigestSection


def test_digest_result_round_trips() -> None:
    r = DigestResult(
        summary="It explains attention.",
        background="Transformers context.",
        confidence=0.8,
        sections=[
            DigestSection(
                heading="Overview",
                blocks=[DigestBlock(content="Attention weighs tokens by relevance.")],
            )
        ],
        facets=[DigestFacet(element_type="key_term", text="attention")],
    )
    again = DigestResult.model_validate_json(r.model_dump_json())
    assert again == r
    assert again.sections[0].blocks[0].type == "prose"  # default


def test_block_type_and_facet_type_are_constrained() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        DigestBlock(type="diagram", content="x")  # not in the Literal
    with pytest.raises(ValidationError):
        DigestFacet(element_type="opinion", text="x")  # not in the Literal
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_pipeline_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.schemas'`

- [ ] **Step 3: Write the schemas**

Create `services/worker/app/pipeline/schemas.py`:

```python
"""The digest LLM's structured response contract (S2 design §2.5/§3).

The `Literal` values mirror the ORM enums `PackBlockType` / `PackElementType`
exactly, so the persist stage can map them by string value.
"""

from typing import Literal

from pydantic import BaseModel


class DigestBlock(BaseModel):
    type: Literal["prose", "callout", "quote"] = "prose"
    content: str


class DigestSection(BaseModel):
    heading: str | None = None
    blocks: list[DigestBlock]


class DigestFacet(BaseModel):
    element_type: Literal["key_term", "person_org", "claim", "counter_view", "connection"]
    text: str


class DigestResult(BaseModel):
    summary: str
    background: str | None = None
    confidence: float = 0.7
    sections: list[DigestSection]
    facets: list[DigestFacet]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_pipeline_schemas.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/pipeline/schemas.py services/worker/tests/test_pipeline_schemas.py
git commit -m "feat(s2): digest response schemas"
```

---

### Task 2: Digest prompt

**Files:**
- Create: `services/worker/app/prompts/digest.py`
- Test: `services/worker/tests/test_prompt_digest.py`

**Interfaces:**
- Consumes: `app.pipeline.normdoc.NormDoc` (Plan 2), `app.llm.base.Message` (Plan 2; `Message = dict[str, str]`).
- Produces: `build_digest_messages(normdoc: NormDoc, body: str) -> tuple[str, list[Message]]` — returns `(system_prompt, [{"role": "user", "content": ...}])`. `body` is the (possibly truncated) content the model should digest; the user message also carries the title and media-type hint.

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_prompt_digest.py`:

```python
from app.pipeline.normdoc import Anchor, NormBlock, NormDoc
from app.prompts.digest import build_digest_messages


def _doc() -> NormDoc:
    body = "Attention weighs tokens by relevance."
    return NormDoc(
        title="Attention",
        lang="en",
        media_type="article",
        content_body=body,
        blocks=[NormBlock(text=body, anchor=Anchor(start=0, end=len(body)))],
    )


def test_system_prompt_states_the_rules() -> None:
    system, _ = build_digest_messages(_doc(), "Attention weighs tokens by relevance.")
    low = system.lower()
    assert "english" in low
    assert "report" in low
    assert "faithful" in low or "do not invent" in low or "never invent" in low
    # facet vocabulary is described
    for t in ("key_term", "person_org", "claim", "counter_view", "connection"):
        assert t in system
    assert "confidence" in low


def test_user_message_carries_title_media_type_and_body() -> None:
    _, messages = build_digest_messages(_doc(), "BODY-CONTENT-HERE")
    assert len(messages) == 1 and messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert "Attention" in content        # title
    assert "article" in content          # media_type hint
    assert "BODY-CONTENT-HERE" in content  # the body we passed (not normdoc.content_body)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_prompt_digest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.prompts.digest'`

- [ ] **Step 3: Write the prompt builder**

Create `services/worker/app/prompts/digest.py`:

```python
"""The digest prompt — turn a NormDoc into a re-authored report + facets."""

from app.llm.base import Message
from app.pipeline.normdoc import NormDoc

_SYSTEM = """You are Gulp's digestion engine. Turn a captured source into a \
complete, re-authored study report the reader can page through, plus a set of \
structured facets.

Rules:
- Write everything in English, regardless of the source language.
- Re-author the material into clear, well-structured prose. Do NOT copy the \
source verbatim, but stay strictly faithful to it: never invent facts, figures, \
names, or claims the source does not support. If the source is thin, say less \
rather than padding.
- Structure the report as ordered sections, each with a short heading and one or \
more prose blocks. Add background only where it genuinely aids understanding.
- Extract facets that annotate the content, each tagged with an element_type:
  - key_term: an important term or concept the reader must know (the term itself).
  - person_org: a person or organization that matters.
  - claim: a load-bearing assertion the source makes.
  - counter_view: an opposing or contrasting view — surface the disagreement \
even if the source does not.
  - connection: how this relates to broader ideas the reader may know.
- Set confidence in [0,1]: how reliable and complete this digest is given the \
source (lower for thin, partial, or ambiguous sources).

Return your result via the provided tool."""


def build_digest_messages(normdoc: NormDoc, body: str) -> tuple[str, list[Message]]:
    user = f"Source type: {normdoc.media_type}\nTitle: {normdoc.title}\n\n---\n{body}"
    return _SYSTEM, [{"role": "user", "content": user}]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_prompt_digest.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/prompts/digest.py services/worker/tests/test_prompt_digest.py
git commit -m "feat(s2): digest prompt builder"
```

---

### Task 3: Digest stage (`run_digest`) + budget guard

**Files:**
- Create: `services/worker/app/pipeline/digest.py`
- Test: `services/worker/tests/test_digest.py`

**Interfaces:**
- Consumes: `app.pipeline.normdoc.NormDoc`; `app.pipeline.schemas.DigestResult`; `app.prompts.digest.build_digest_messages`; `app.llm.{complete_structured, ModelConfig, LLMProvider}`; `gulp_shared.settings.settings`.
- Produces: `MAX_DIGEST_CHARS: int` (module constant); `async def run_digest(normdoc: NormDoc, *, provider: LLMProvider | None = None, config: ModelConfig | None = None) -> DigestResult`. Default config = `ModelConfig(provider=settings.llm_provider, model=settings.llm_model)`. If `len(normdoc.content_body) > MAX_DIGEST_CHARS`, digest only the first `MAX_DIGEST_CHARS` chars and clamp the returned `confidence` to at most `0.5`.

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_digest.py`:

```python
from typing import Any

from app.llm.base import Message, ModelConfig
from app.pipeline.digest import MAX_DIGEST_CHARS, run_digest
from app.pipeline.normdoc import Anchor, NormBlock, NormDoc
from app.pipeline.schemas import DigestResult


class FakeProvider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.last_body: str | None = None

    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[Message],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]:
        self.last_body = messages[0]["content"]
        return self.payload


def _doc(body: str) -> NormDoc:
    return NormDoc(
        title="T",
        lang="en",
        media_type="article",
        content_body=body,
        blocks=[NormBlock(text=body, anchor=Anchor(start=0, end=len(body)))],
    )


_PAYLOAD = {
    "summary": "s",
    "background": None,
    "confidence": 0.9,
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "facets": [{"element_type": "claim", "text": "x"}],
}


async def test_run_digest_returns_validated_result() -> None:
    prov = FakeProvider(_PAYLOAD)
    out = await run_digest(_doc("short body"), provider=prov)
    assert isinstance(out, DigestResult)
    assert out.summary == "s" and out.confidence == 0.9
    assert prov.last_body == "short body"  # not truncated


async def test_over_budget_content_is_truncated_and_confidence_clamped() -> None:
    prov = FakeProvider(_PAYLOAD)  # provider reports confidence 0.9
    big = "x" * (MAX_DIGEST_CHARS + 500)
    out = await run_digest(_doc(big), provider=prov)
    assert prov.last_body is not None and len(prov.last_body) <= MAX_DIGEST_CHARS + 100
    assert big[:MAX_DIGEST_CHARS] in prov.last_body  # truncated body was sent
    assert out.confidence == 0.5  # clamped down because we dropped content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_digest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.digest'`

- [ ] **Step 3: Write the digest stage**

Create `services/worker/app/pipeline/digest.py`:

```python
"""Digest stage: NormDoc -> DigestResult via the LLM service (one turn).

Single-pass with a budget guard (S2 design C13 v1): content over
MAX_DIGEST_CHARS is truncated and the pack is flagged low-confidence.
Per-section map-reduce for long content is a later enhancement.
"""

from app.llm import ModelConfig, complete_structured
from app.llm.base import LLMProvider
from app.pipeline.normdoc import NormDoc
from app.pipeline.schemas import DigestResult
from app.prompts.digest import build_digest_messages
from gulp_shared.settings import settings  # type: ignore[import-untyped]

# ~12k tokens of input; tunable. Over this, we digest a prefix and flag it.
MAX_DIGEST_CHARS = 48_000
_TRUNCATED_CONFIDENCE_CAP = 0.5


async def run_digest(
    normdoc: NormDoc,
    *,
    provider: LLMProvider | None = None,
    config: ModelConfig | None = None,
) -> DigestResult:
    cfg = config or ModelConfig(provider=settings.llm_provider, model=settings.llm_model)
    body = normdoc.content_body
    truncated = len(body) > MAX_DIGEST_CHARS
    if truncated:
        body = body[:MAX_DIGEST_CHARS]
    system, messages = build_digest_messages(normdoc, body)
    result = await complete_structured(
        response_model=DigestResult,
        system=system,
        messages=messages,
        config=cfg,
        provider=provider,
    )
    if truncated and result.confidence > _TRUNCATED_CONFIDENCE_CAP:
        result.confidence = _TRUNCATED_CONFIDENCE_CAP
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_digest.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/pipeline/digest.py services/worker/tests/test_digest.py
git commit -m "feat(s2): digest stage with content-budget guard"
```

---

### Task 4: Persist stage (`persist_pack`)

**Files:**
- Create: `services/worker/app/pipeline/persist.py`
- Test: `services/worker/tests/test_persist.py`

**Interfaces:**
- Consumes: `sqlalchemy.orm.Session`; `app.pipeline.schemas.DigestResult`; Plan-1 models `KnowledgePack`, `PackSection`, `PackBlock`, `PackElement` (+ enums `PackStatus`, `PackBlockType`, `PackElementType`, `PackElementState`), `Source`.
- Produces: `def persist_pack(db: Session, source: Source, digest: DigestResult) -> KnowledgePack`. **Idempotent**: deletes any existing pack (and its sections/blocks/elements) for `source.id` first, then creates a fresh `KnowledgePack` (status `ready`, `confidence` clamped to `[0,1]`), `PackSection`/`PackBlock` rows (`source_anchor=None`, `anchor_id=f"s{i}b{j}"`, `position` by order), and `PackElement` facet rows (`state=suggested`, `concept_id`/`block_id`=None). Does **not** touch `source.status`.

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_persist.py`:

```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.pipeline.persist import persist_pack
from app.pipeline.schemas import DigestBlock, DigestFacet, DigestResult, DigestSection
from gulp_shared.db import Base  # type: ignore[import-untyped]
import gulp_shared.models  # type: ignore[import-untyped]  # noqa: F401
from gulp_shared.models.knowledge_pack import (  # type: ignore[import-untyped]
    KnowledgePack,
    PackBlock,
    PackElement,
    PackElementState,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import Source, SnapshotStatus, SourceKind  # type: ignore[import-untyped]
from gulp_shared.models.user import DEV_USER_ID, User  # type: ignore[import-untyped]


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _snapshot(s):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
        status=SnapshotStatus.processing,
    )
    s.add(snap)
    s.flush()
    return snap


_DIGEST = DigestResult(
    summary="sum", background="bg", confidence=1.5,  # out of range on purpose
    sections=[DigestSection(heading="H", blocks=[
        DigestBlock(type="prose", content="b0"), DigestBlock(type="quote", content="b1")])],
    facets=[DigestFacet(element_type="key_term", text="term"),
            DigestFacet(element_type="claim", text="claim-x")],
)


def test_persist_writes_report_and_facets_with_clamped_confidence() -> None:
    s = _session()
    snap = _snapshot(s)
    pack = persist_pack(s, snap, _DIGEST)
    s.commit()

    got = s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id))
    assert got is not None
    assert got.status == PackStatus.ready
    assert got.confidence == 1.0  # clamped
    sections = list(s.scalars(select(PackSection).where(PackSection.pack_id == pack.id)))
    assert len(sections) == 1 and sections[0].heading == "H"
    blocks = list(s.scalars(select(PackBlock).where(PackBlock.section_id == sections[0].id)))
    assert [b.anchor_id for b in sorted(blocks, key=lambda b: b.position)] == ["s0b0", "s0b1"]
    facets = list(s.scalars(select(PackElement).where(PackElement.pack_id == pack.id)))
    assert {f.text for f in facets} == {"term", "claim-x"}
    assert all(f.state == PackElementState.suggested for f in facets)
    assert all(f.concept_id is None and f.block_id is None for f in facets)


def test_persist_is_idempotent_and_replaces() -> None:
    s = _session()
    snap = _snapshot(s)
    persist_pack(s, snap, _DIGEST)
    s.commit()
    persist_pack(s, snap, _DIGEST)  # second run
    s.commit()
    packs = list(s.scalars(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id)))
    assert len(packs) == 1  # replaced, not duplicated
    blocks = list(s.scalars(select(PackBlock)))
    assert len(blocks) == 2  # not 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_persist.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.persist'`

- [ ] **Step 3: Write the persist stage**

Create `services/worker/app/pipeline/persist.py`:

```python
"""Persist stage: DigestResult -> KnowledgePack + report rows + facet rows.

Idempotent: a re-run drops the snapshot's existing pack and rebuilds it, so
re-Start cleanly regenerates. source.status is the caller's responsibility.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.pipeline.schemas import DigestResult
from gulp_shared.models.knowledge_pack import (  # type: ignore[import-untyped]
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackElement,
    PackElementState,
    PackElementType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import Source  # type: ignore[import-untyped]


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _delete_existing(db: Session, snapshot_id: object) -> None:
    pack = db.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snapshot_id))
    if pack is None:
        return
    sections = list(db.scalars(select(PackSection).where(PackSection.pack_id == pack.id)))
    for section in sections:
        for block in db.scalars(select(PackBlock).where(PackBlock.section_id == section.id)):
            db.delete(block)
        db.delete(section)
    for element in db.scalars(select(PackElement).where(PackElement.pack_id == pack.id)):
        db.delete(element)
    db.delete(pack)
    db.flush()


def persist_pack(db: Session, source: Source, digest: DigestResult) -> KnowledgePack:
    _delete_existing(db, source.id)
    pack = KnowledgePack(
        snapshot_id=source.id,
        summary=digest.summary,
        background=digest.background,
        confidence=_clamp(digest.confidence),
        status=PackStatus.ready,
    )
    db.add(pack)
    db.flush()
    for i, section in enumerate(digest.sections):
        row = PackSection(pack_id=pack.id, heading=section.heading, position=i)
        db.add(row)
        db.flush()
        for j, block in enumerate(section.blocks):
            db.add(
                PackBlock(
                    section_id=row.id,
                    block_type=PackBlockType(block.type),
                    content=block.content,
                    source_anchor=None,
                    anchor_id=f"s{i}b{j}",
                    position=j,
                )
            )
    for facet in digest.facets:
        db.add(
            PackElement(
                pack_id=pack.id,
                element_type=PackElementType(facet.element_type),
                text=facet.text,
                state=PackElementState.suggested,
            )
        )
    db.flush()
    return pack
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_persist.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/pipeline/persist.py services/worker/tests/test_persist.py
git commit -m "feat(s2): persist digest into KnowledgePack rows (idempotent)"
```

---

### Task 5: Pipeline orchestration core (`process_source`)

**Files:**
- Create: `services/worker/app/pipeline/run.py`
- Test: `services/worker/tests/test_run.py`

**Interfaces:**
- Consumes: `Session`, `Source`/`SnapshotStatus`/`MediaType` (Plan 1); `app.pipeline.adapters.{note_to_normdoc, webpage_to_normdoc}` + `fetch_html` (Plan 2); `run_digest` (Task 3); `persist_pack` (Task 4).
- Produces: `class PipelineError(Exception)`; `async def process_source(db: Session, source: Source, *, fetch: Callable[[str], Awaitable[str]] = fetch_html, provider=None, config=None) -> None`. It sets `source.status = processing` (commit), builds a `NormDoc` (`_to_normdoc`), writes `source.content_body` + precise `media_type` back, runs the digest, persists the pack, sets `ready` (commit). Any exception → rollback, `source.status = needs_attention` (commit), log, no re-raise (status carries the outcome; no auto-retry in v1).

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_run.py`:

```python
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.llm.base import Message, ModelConfig
from app.pipeline.run import process_source
from gulp_shared.db import Base  # type: ignore[import-untyped]
import gulp_shared.models  # type: ignore[import-untyped]  # noqa: F401
from gulp_shared.models.knowledge_pack import KnowledgePack  # type: ignore[import-untyped]
from gulp_shared.models.source import (  # type: ignore[import-untyped]
    MediaType,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.user import DEV_USER_ID, User  # type: ignore[import-untyped]


class FakeProvider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    async def complete_json(self, *, system: str | None, messages: list[Message],
                            json_schema: dict[str, Any], config: ModelConfig) -> dict[str, Any]:
        return self.payload


_OK = {
    "summary": "s", "background": None, "confidence": 0.8,
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "facets": [{"element_type": "claim", "text": "x"}],
}


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _note(s):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="N",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.note,
                  content_body="My note body.")
    s.add(snap)
    s.flush()
    return snap


async def test_note_pipeline_ends_ready_with_a_pack() -> None:
    s = _session()
    snap = _note(s)

    async def _no_fetch(url: str) -> str:  # notes never fetch
        raise AssertionError("note path must not fetch")

    await process_source(s, snap, fetch=_no_fetch, provider=FakeProvider(_OK))

    assert snap.status == SnapshotStatus.ready
    assert s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id)) is not None


async def test_link_pipeline_fetches_then_digests() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="L",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://x.example/a")
    s.add(snap)
    s.flush()

    async def _fetch(url: str) -> str:
        return ("<html><head><title>A</title></head><body><article>"
                "<h1>A</h1><p>Attention weighs tokens by relevance across the input.</p>"
                "</article></body></html>")

    await process_source(s, snap, fetch=_fetch, provider=FakeProvider(_OK))

    assert snap.status == SnapshotStatus.ready
    assert snap.media_type == MediaType.article  # precise type set
    assert snap.content_body and "relevance" in snap.content_body  # extracted body stored


async def test_failure_sets_needs_attention() -> None:
    s = _session()
    snap = _note(s)

    class Boom:
        async def complete_json(self, **kw: Any) -> dict[str, Any]:
            raise RuntimeError("llm down")

    await process_source(s, snap, provider=Boom())
    assert snap.status == SnapshotStatus.needs_attention
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_run.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.run'`

- [ ] **Step 3: Write the orchestration core**

Create `services/worker/app/pipeline/run.py`:

```python
"""Pipeline orchestration: Source -> (fetch -> adapt -> digest -> persist) -> status.

Testable in isolation: pass an injected `fetch` and `provider`. The arq entry
(app/tasks) provides the real ones and a real DB session.
"""

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from app.llm.base import LLMProvider, ModelConfig
from app.pipeline.adapters.note import note_to_normdoc
from app.pipeline.adapters.webpage import fetch_html, webpage_to_normdoc
from app.pipeline.digest import run_digest
from app.pipeline.normdoc import NormDoc
from app.pipeline.persist import persist_pack
from gulp_shared.models.source import MediaType, SnapshotStatus, Source  # type: ignore[import-untyped]

logger = logging.getLogger("gulp.worker")

FetchFn = Callable[[str], Awaitable[str]]


class PipelineError(Exception):
    """A processing failure that should land the snapshot in needs_attention."""


async def _to_normdoc(source: Source, fetch: FetchFn) -> NormDoc:
    if source.origin_url:
        html = await fetch(source.origin_url)
        return webpage_to_normdoc(html, fallback_title=source.title, url=source.origin_url)
    return note_to_normdoc(source.title, source.content_body or "")


async def process_source(
    db: Session,
    source: Source,
    *,
    fetch: FetchFn = fetch_html,
    provider: LLMProvider | None = None,
    config: ModelConfig | None = None,
) -> None:
    source.status = SnapshotStatus.processing
    db.commit()
    try:
        normdoc = await _to_normdoc(source, fetch)
        if not normdoc.content_body.strip():
            raise PipelineError("extraction produced no content")
        source.content_body = normdoc.content_body
        source.media_type = MediaType(normdoc.media_type)
        digest = await run_digest(normdoc, provider=provider, config=config)
        persist_pack(db, source, digest)
        source.status = SnapshotStatus.ready
        db.commit()
    except Exception:
        db.rollback()
        source.status = SnapshotStatus.needs_attention
        db.commit()
        logger.exception("process_snapshot failed for %s", source.id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_run.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/pipeline/run.py services/worker/tests/test_run.py
git commit -m "feat(s2): pipeline orchestration (fetch->adapt->digest->persist->status)"
```

---

### Task 6: Worker job entry (`process_snapshot`)

**Files:**
- Modify: `services/worker/app/tasks/__init__.py`
- Test: `services/worker/tests/test_tasks.py` (replace the S1 no-op tests)

**Interfaces:**
- Consumes: `gulp_shared.db.SessionLocal`; `Source` (Plan 1); `process_source` (Task 5).
- Produces: `async def process_snapshot(ctx: dict, snapshot_id: str) -> None` — opens a `SessionLocal`, loads the `Source` by UUID, delegates to `process_source` (default registry provider), closes the session. Still registered in `WorkerSettings.functions`. Returns early (no error) if the snapshot is missing.

- [ ] **Step 1: Write the failing test**

Replace `services/worker/tests/test_tasks.py` with:

```python
from typing import Any

import app.tasks as tasks
from app.tasks import WorkerSettings, process_snapshot
from gulp_shared.db import Base  # type: ignore[import-untyped]
import gulp_shared.models  # type: ignore[import-untyped]  # noqa: F401
from gulp_shared.models.source import (  # type: ignore[import-untyped]
    MediaType,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.user import DEV_USER_ID, User  # type: ignore[import-untyped]
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class FakeProvider:
    async def complete_json(self, **kw: Any) -> dict[str, Any]:
        return {"summary": "s", "background": None, "confidence": 0.7,
                "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
                "facets": [{"element_type": "claim", "text": "x"}]}


def test_worker_registers_process_snapshot() -> None:
    assert process_snapshot in WorkerSettings.functions


async def test_process_snapshot_loads_and_processes(monkeypatch: Any) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Local = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Local()
    seed.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="N",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.note,
                  content_body="body")
    seed.add(snap)
    seed.commit()
    sid = str(snap.id)
    seed.close()

    # process_snapshot opens its own session via SessionLocal, and uses the
    # registered provider — point both at our test doubles.
    monkeypatch.setattr(tasks, "SessionLocal", Local)
    from app.llm import register_provider
    register_provider("anthropic", FakeProvider())

    await process_snapshot({}, sid)

    check = Local()
    got = check.get(Source, snap.id)
    assert got is not None and got.status == SnapshotStatus.ready
    check.close()


async def test_missing_snapshot_is_a_noop(monkeypatch: Any) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Local = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(tasks, "SessionLocal", Local)
    await process_snapshot({}, "00000000-0000-0000-0000-0000000000ff")  # no raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_tasks.py -v`
Expected: FAIL — the old no-op `process_snapshot` doesn't load/process; `test_process_snapshot_loads_and_processes` fails (status stays `unprocessed`).

- [ ] **Step 3: Rewrite the worker job**

Replace `services/worker/app/tasks/__init__.py` with:

```python
"""Job definitions (arq). `process_snapshot` runs the S2 report pipeline."""

import logging
import uuid

from arq.connections import RedisSettings

from app.pipeline.run import process_source
from gulp_shared.db import SessionLocal  # type: ignore[import-untyped]
from gulp_shared.models.source import Source  # type: ignore[import-untyped]
from gulp_shared.settings import settings  # type: ignore[import-untyped]

logger = logging.getLogger("gulp.worker")


async def process_snapshot(ctx: dict, snapshot_id: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("process_snapshot: snapshot %s not found", snapshot_id)
            return
        await process_source(db, source)
    finally:
        db.close()


class WorkerSettings:
    functions = [process_snapshot]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_tasks.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full worker suite**

Run: `cd services/worker && uv run pytest -q`
Expected: PASS (all worker tests).

- [ ] **Step 6: Commit**

```bash
git add services/worker/app/tasks/__init__.py services/worker/tests/test_tasks.py
git commit -m "feat(s2): process_snapshot runs the report pipeline"
```

---

### Task 7: API — Start endpoint (`POST /snapshots/{id}/process`)

**Files:**
- Create: `services/api/app/services/processing.py`, `services/api/app/routers/processing.py`
- Modify: `services/api/app/main.py` (register the router)
- Test: `services/api/tests/test_processing.py`

**Interfaces:**
- Consumes: `Source`/`SnapshotStatus` (Plan 1); `to_out` (`app.services.snapshots`); `get_db`/`get_current_user`/`get_enqueue` (existing deps); the enqueue seam.
- Produces: `def start_processing(db: Session, source: Source, enqueue: Callable[..., None]) -> None` — only when `source.status in {unprocessed, needs_attention, ready}`; sets `source.status = processing` (commit) and enqueues `("process_snapshot", str(source.id))`; raises `ValueError` if the status is not startable. Router `POST /snapshots/{snapshot_id}/process` → loads the owned snapshot (404 if missing/foreign/deleted), calls `start_processing` (409 on `ValueError`), returns the updated `SnapshotOut`.

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_processing.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.deps import get_db, get_enqueue
from app.main import app


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    calls: list[tuple[object, ...]] = []
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: calls.append(a))
    c = TestClient(app)
    c.enqueue_calls = calls  # type: ignore[attr-defined]
    yield c
    app.dependency_overrides.clear()


def _capture(client: TestClient) -> str:
    r = client.post("/capture", json={"url": "https://a.com/x"})
    return r.json()["snapshot"]["id"]


def test_process_enqueues_and_marks_processing(client: TestClient) -> None:
    sid = _capture(client)
    r = client.post(f"/snapshots/{sid}/process")
    assert r.status_code == 200
    assert r.json()["status"] == "processing"
    assert client.enqueue_calls == [("process_snapshot", sid)]


def test_process_unknown_snapshot_404(client: TestClient) -> None:
    r = client.post("/snapshots/00000000-0000-0000-0000-0000000000ff/process")
    assert r.status_code == 404


def test_process_twice_conflicts(client: TestClient) -> None:
    sid = _capture(client)
    client.post(f"/snapshots/{sid}/process")  # -> processing
    r = client.post(f"/snapshots/{sid}/process")  # already processing
    assert r.status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_processing.py -v`
Expected: FAIL — `404` route not found / `ModuleNotFoundError` for `app.routers.processing`.

- [ ] **Step 3: Write the service**

Create `services/api/app/services/processing.py`:

```python
"""Start-processing business logic (S2 manual trigger, design §2.4)."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from gulp_shared.models.source import SnapshotStatus, Source

_STARTABLE = {
    SnapshotStatus.unprocessed,
    SnapshotStatus.needs_attention,
    SnapshotStatus.ready,  # allow re-generation
}


def start_processing(db: Session, source: Source, enqueue: Callable[..., None]) -> None:
    if source.status not in _STARTABLE:
        raise ValueError(f"snapshot in status {source.status.value} is not startable")
    source.status = SnapshotStatus.processing
    db.commit()
    enqueue("process_snapshot", str(source.id))
```

- [ ] **Step 4: Write the router**

Create `services/api/app/routers/processing.py`:

```python
"""Processing trigger endpoint — thin (docs/05 D4)."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db, get_enqueue
from app.schemas.capture import SnapshotOut
from app.services.processing import start_processing
from app.services.snapshots import to_out
from gulp_shared.models.source import Source
from gulp_shared.models.user import User

router = APIRouter()


@router.post("/snapshots/{snapshot_id}/process", response_model=SnapshotOut)
def process_snapshot_endpoint(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> SnapshotOut:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    try:
        start_processing(db, source, enqueue)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return to_out(db, source)
```

- [ ] **Step 5: Register the router**

In `services/api/app/main.py`, add `processing` to the import and `include_router`:

```python
from app.routers import capture, inbox, processing
...
app.include_router(processing.router, tags=["processing"])
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd services/api && uv run pytest tests/test_processing.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add services/api/app/services/processing.py services/api/app/routers/processing.py services/api/app/main.py services/api/tests/test_processing.py
git commit -m "feat(s2): Start endpoint POST /snapshots/{id}/process"
```

---

### Task 8: Capture lands `unprocessed` (S1 change)

**Files:**
- Modify: `services/api/app/services/capture.py`, `services/api/app/routers/capture.py`
- Test: `services/api/tests/test_capture.py`, `services/api/tests/test_routers.py`

**Interfaces:**
- Changes `create_snapshot` signature to `create_snapshot(db: Session, owner_id: uuid.UUID, req: CaptureRequest) -> tuple[Source, bool]` (drops the `enqueue` param); both snapshot branches set `status=SnapshotStatus.unprocessed`; **no enqueue**. The capture router drops its `get_enqueue` dependency.

- [ ] **Step 1: Update the capture tests (they encode the new behavior)**

Edit `services/api/tests/test_capture.py`: remove the `_enqueue_spy` helper and all `enq`/`calls` usage; `create_snapshot` is now called with 3 args; assert `status == SnapshotStatus.unprocessed` and that no enqueue happens. Replace the file body's tests with:

```python
from app.schemas.capture import CaptureRequest
from app.services.capture import create_snapshot
from gulp_shared.models.source import CapturedVia, MediaType, SnapshotStatus
from gulp_shared.models.user import DEV_USER_ID


def test_link_capture_creates_unprocessed_webpage(db) -> None:  # type: ignore[no-untyped-def]
    snap, dup = create_snapshot(
        db, DEV_USER_ID,
        CaptureRequest(url="https://Example.com/x/?utm_source=z", captured_via=CapturedVia.paste),
    )
    assert dup is False
    assert snap.media_type == MediaType.webpage
    assert snap.status == SnapshotStatus.unprocessed
    assert snap.origin_url == "https://example.com/x"
    assert snap.title == "example.com"


def test_note_capture_stores_body_unprocessed(db) -> None:  # type: ignore[no-untyped-def]
    snap, dup = create_snapshot(
        db, DEV_USER_ID, CaptureRequest(text="first line\nsecond", captured_via=CapturedVia.manual),
    )
    assert snap.media_type == MediaType.note
    assert snap.content_body == "first line\nsecond"
    assert snap.title == "first line"
    assert snap.status == SnapshotStatus.unprocessed


def test_duplicate_url_returns_existing(db) -> None:  # type: ignore[no-untyped-def]
    first, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/p"))
    again, dup = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/p?utm_x=1"))
    assert dup is True
    assert again.id == first.id


def test_tags_are_persisted_as_rows(db) -> None:  # type: ignore[no-untyped-def]
    from app.services.snapshots import _tags_for

    snap, _ = create_snapshot(
        db, DEV_USER_ID, CaptureRequest(url="https://a.com/t", tags=["ml", "memory"]),
    )
    assert sorted(_tags_for(db, snap.id)) == ["memory", "ml"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_capture.py -v`
Expected: FAIL — `create_snapshot()` still requires the `enqueue` arg (TypeError) / status is `processing` not `unprocessed`.

- [ ] **Step 3: Update `create_snapshot`**

In `services/api/app/services/capture.py`: remove the `enqueue: EnqueueFn` parameter and the `EnqueueFn`/`Callable` import; change both `status=SnapshotStatus.processing` to `status=SnapshotStatus.unprocessed`; delete the final two lines (`# The S1↔S2 seam...` comment and `enqueue("process_snapshot", str(source.id))`), returning `source, False` directly. The function now ends:

```python
    db.add(source)
    db.flush()  # assign source.id
    for tag in req.tags:
        db.add(SourceTag(source_id=source.id, tag=tag))
    db.commit()
    db.refresh(source)
    # Manual trigger (S2 design §2.4): the snapshot rests at `unprocessed` until
    # the user Starts it (POST /snapshots/{id}/process). Capture never enqueues.
    return source, False
```

(Also drop the now-unused `from collections.abc import Callable` and the `EnqueueFn = Callable[..., None]` line.)

- [ ] **Step 4: Update the capture router**

In `services/api/app/routers/capture.py`: drop the `get_enqueue` import and the `enqueue` dependency/argument. The `capture` handler becomes:

```python
@router.post("/capture", response_model=CaptureResponse)
def capture(
    req: CaptureRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaptureResponse:
    source, duplicate = create_snapshot(db, user.id, req)
    return CaptureResponse(snapshot=to_out(db, source), duplicate=duplicate)
```

(Remove `from collections.abc import Callable` and `from app.deps import get_db, get_enqueue` → `from app.deps import get_db`.)

- [ ] **Step 5: Update `test_routers.py`**

Edit `services/api/tests/test_routers.py`: the `client` fixture keeps the `get_enqueue` override (the process endpoint still uses it). Change `test_post_capture_creates_a_snapshot_and_returns_it` to assert the snapshot is `unprocessed` and that capture did NOT enqueue:

```python
def test_post_capture_creates_an_unprocessed_snapshot(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/capture", json={"url": "https://a.com/x", "captured_via": "paste"})
    assert r.status_code == 200
    body = r.json()
    assert body["duplicate"] is False
    assert body["snapshot"]["status"] == "unprocessed"
    assert body["snapshot"]["media_type"] == "webpage"
    assert client.enqueue_calls == []  # capture no longer enqueues
```

(Leave the other three router tests unchanged.)

- [ ] **Step 6: Run the api suite**

Run: `cd services/api && uv run pytest -q`
Expected: PASS (all api tests, including the updated capture/router tests and Task 7's processing tests).

- [ ] **Step 7: Commit**

```bash
git add services/api/app/services/capture.py services/api/app/routers/capture.py services/api/tests/test_capture.py services/api/tests/test_routers.py
git commit -m "feat(s2): capture lands unprocessed (manual trigger); drop auto-enqueue"
```

---

## Self-Review

**Spec coverage** (against S2 design §9 Plan-3 slice + §2.4/§3/§6):
- Manual trigger: capture → `unprocessed` (Task 8); Start endpoint enqueues (Task 7); status `unprocessed→processing→ready`/`needs_attention` (Tasks 5–7) ✓.
- One digest turn → report + facets (Tasks 1–4); report = `KnowledgePack`+`PackSection`/`PackBlock`, facets = `PackElement` text, `concept_id`/`block_id` null (Task 4) ✓.
- `source_anchor` null; faithfulness via the prompt (Tasks 2, 4) ✓.
- Budget guard: truncate + clamp confidence (Task 3); confidence clamped to [0,1] on persist (Task 4) ✓.
- Fetch/adapt reuse Plan 2; `content_body` + precise `media_type` written back for links (Task 5) ✓.
- Provider-injectable, hermetic tests throughout (FakeProvider + SQLite + injected fetch) ✓.
- Idempotent re-Start (Task 4 `_delete_existing`; Task 7 allows re-start from `ready`/`needs_attention`) ✓.
- **Deferred (correctly out of plan):** card generation (later plan); `Concept`/edge materialization (S3); per-section map-reduce; per-block `source_anchor`; arq auto-retry (manual re-Start instead); `/import` Upload + export executor; `auto_process` toggle. The S1↔S2 enqueue moved from capture to the Start endpoint.

**Placeholder scan:** none — every step carries concrete code/commands. The `# type: ignore[import-untyped]` markers are deliberate (gulp_shared has no `py.typed`; matches the existing `app/llm/anthropic_provider.py`).

**Type consistency:** `DigestResult`/`DigestSection`/`DigestBlock`/`DigestFacet`, `build_digest_messages(normdoc, body)`, `run_digest(normdoc, *, provider, config)`, `persist_pack(db, source, digest)`, `process_source(db, source, *, fetch, provider, config)`, `process_snapshot(ctx, snapshot_id)`, `start_processing(db, source, enqueue)` are named identically across tasks and tests. The digest `Literal` values (`prose|callout|quote`, `key_term|person_org|claim|counter_view|connection`) map by string to `PackBlockType`/`PackElementType` in Task 4. `create_snapshot(db, owner_id, req)` (Task 8) matches its new call sites in the router and both test files. The provider double's `complete_json(*, system, messages, json_schema, config)` matches the Plan-2 `LLMProvider` protocol exactly.
