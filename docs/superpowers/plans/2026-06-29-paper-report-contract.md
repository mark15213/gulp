# Paper Report Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `DigestResult` knowledge-pack contract with a `PaperReport` contract (title / core_contributions / key_insight / sections / references, with typed prose·formula·table·figure·list blocks) end-to-end: worker pipeline + export, shared DB model + migration, API schema + serializer, regenerated TS client, and apps/web rendering with KaTeX.

**Architecture:** The contract stays structured, schema-validated JSON. The `PaperReport` Pydantic model in `services/worker/app/pipeline/schemas.py` is the source of truth: the importer validates against it, and the exported `schema/pack.schema.json` is generated from it. Storage is normalized (`pack_sections` + `pack_blocks` with a per-block JSON `data` column); facets are dropped.

**Tech Stack:** Python 3 / Pydantic v2 / SQLAlchemy / Alembic (Postgres) / FastAPI; TypeScript / Next.js 15 / React 19 / Vitest; KaTeX + react-markdown for rendering.

## Global Constraints

- Output file names are fixed: `result/pack.json`, `schema/pack.schema.json` (referenced by `manifest.json` and downstream). Only contents change.
- The exported `schema/pack.schema.json` is generated from the `PaperReport` Pydantic model (`PaperReport.model_json_schema()`), never hand-maintained.
- Report language is English regardless of source language.
- Dropped permanently: `summary`, `background`, `confidence`, `facets` (`PackElement*`), `callout`/`quote` blocks, source anchoring (`anchor_id`/`source_anchor`/`content_ref`), and the generated `README.md`.
- Block `type` literals must match the `PackBlockType` enum string values exactly: `prose`, `formula`, `table`, `figure`, `list`.
- Pre-production: the migration recreates structure with no data backfill; downgrade restores the old shape.
- Use the `justfile`: `just test`, `just lint`, `just gen-client`, `just up`, `just migrate-up`. Never improvise the underlying tool.
- Reference branch base: `feat/paper-report-contract` off `docs/product-one-pager`. The spec is `docs/superpowers/specs/2026-06-28-paper-report-contract-design.md`.

**Why Task 1 is one atomic task:** `persist.py` imports `DigestResult` (from `schemas.py`) *and* `PackElement*` (from the model); the API schema imports `PackElementType`. Removing either symbol breaks imports across worker + API simultaneously, so the whole Python contract must compile together. Within Task 1, run **targeted** `pytest <file>` per step (pytest only imports the file under test + its deps, so half-migrated siblings don't block a step), then the full suites at the end. Task 1 is a single commit.

---

### Task 1: Swap the Python contract (worker + storage + API) and migration

**Files:**
- Modify: `services/worker/app/pipeline/schemas.py` (full replacement)
- Test: `services/worker/tests/test_pipeline_schemas.py` (full replacement)
- Modify: `services/shared/gulp_shared/models/knowledge_pack.py` (full replacement)
- Modify: `services/shared/gulp_shared/models/__init__.py` (drop `PackElement*`)
- Test: `services/shared/tests/test_pack_models.py` (full replacement)
- Modify: `services/worker/app/pipeline/persist.py` (full replacement)
- Test: `services/worker/tests/test_persist.py` (full replacement)
- Modify: `services/worker/app/prompts/digest.py` (new `_SYSTEM`)
- Test: `services/worker/tests/test_prompt_digest.py` (update assertions)
- Modify: `services/worker/app/pipeline/digest.py` (return `PaperReport`, drop confidence)
- Test: `services/worker/tests/test_digest.py` (full replacement)
- Modify: `services/worker/app/export/templates.py` (full replacement)
- Modify: `services/worker/app/export/builder.py` (new file map)
- Modify: `services/worker/app/export/importer.py` (validate `PaperReport`)
- Test: `services/worker/tests/test_export_builder.py` (full replacement)
- Test: `services/worker/tests/test_export_importer.py` (full replacement)
- Test: `services/worker/tests/test_export_jobs.py` (update payload)
- Test: `services/worker/tests/test_tasks.py` (update FakeProvider payload)
- Modify: `services/api/app/schemas/pack.py` (full replacement)
- Modify: `services/api/app/services/pack.py` (full replacement)
- Test: `services/api/tests/test_pack_service.py` (full replacement)
- Test: `services/api/tests/test_pack_router.py` (full replacement)
- Create: `services/api/alembic/versions/a1b2c3d4e5f6_s2_paper_report_contract.py`

**Interfaces:**
- Produces: `app.pipeline.schemas.PaperReport` with `title: str`, `core_contributions: list[str]` (1–5), `key_insight: str`, `sections: list[Section]` (≥1), `references: list[Reference]` (default `[]`). `Section{heading: str, blocks: list[Block]}`. `Block = Annotated[Union[ProseBlock, FormulaBlock, TableBlock, FigureBlock, ListBlock], Field(discriminator="type")]`. `Reference{citation: str, why_interesting: str}`.
- Produces: ORM `KnowledgePack(snapshot_id, title, key_insight, core_contributions: JSON, references: JSON, status)`, `PackSection(pack_id, heading, position)`, `PackBlock(section_id, block_type: PackBlockType, data: JSON, position)`; `PackBlockType ∈ {prose, formula, table, figure, list}`. No `PackElement*`.
- Produces: `persist_pack(db, source, report: PaperReport) -> KnowledgePack`; `import_result_archive(data) -> PaperReport`; `run_digest(...) -> PaperReport`; `pack_schema()`, `prompt_md()`, `claude_md()`.
- Produces: API `PackOut{snapshot_id, status, title, core_contributions, key_insight, sections, references}` consumed by Task 2's client regen.

- [ ] **Step 1: Rewrite the contract — `schemas.py`**

Replace the entire contents of `services/worker/app/pipeline/schemas.py`:
```python
"""The paper-report structured contract (PaperReport).

The block `type` literals mirror the ORM enum `PackBlockType` exactly, so the
persist stage can map them by string value.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class ProseBlock(BaseModel):
    type: Literal["prose"] = "prose"
    content: str


class FormulaBlock(BaseModel):
    type: Literal["formula"] = "formula"
    latex: str
    explanation: str


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None


class FigureBlock(BaseModel):
    type: Literal["figure"] = "figure"
    label: str
    explanation: str


class ListBlock(BaseModel):
    type: Literal["list"] = "list"
    items: list[str]
    ordered: bool = False


Block = Annotated[
    Union[ProseBlock, FormulaBlock, TableBlock, FigureBlock, ListBlock],
    Field(discriminator="type"),
]


class Section(BaseModel):
    heading: str
    blocks: list[Block]


class Reference(BaseModel):
    citation: str
    why_interesting: str


class PaperReport(BaseModel):
    title: str
    core_contributions: list[str] = Field(min_length=1, max_length=5)
    key_insight: str
    sections: list[Section] = Field(min_length=1)
    references: list[Reference] = Field(default_factory=list)
```

- [ ] **Step 2: Replace `test_pipeline_schemas.py` and run it (expect PASS)**

Replace the entire contents of `services/worker/tests/test_pipeline_schemas.py`:
```python
import pytest
from pydantic import ValidationError

from app.pipeline.schemas import (
    FormulaBlock,
    PaperReport,
    ProseBlock,
    Reference,
    Section,
    TableBlock,
)


def _report() -> PaperReport:
    return PaperReport(
        title="BERT",
        core_contributions=["MLM enables deep bidirectionality."],
        key_insight="Change the objective, not the architecture.",
        sections=[
            Section(
                heading="The Core Challenge",
                blocks=[
                    ProseBlock(content="The **problem** and why it matters."),
                    FormulaBlock(latex="L=-\\sum_i y_i\\log p_i", explanation="Cross-entropy."),
                    TableBlock(headers=["Model", "F1"], rows=[["BERT", "93.2"]], caption="Results"),
                ],
            )
        ],
        references=[Reference(citation="Vaswani et al. (2017)", why_interesting="The Transformer.")],
    )


def test_paper_report_round_trips() -> None:
    r = _report()
    again = PaperReport.model_validate_json(r.model_dump_json())
    assert again == r
    assert again.sections[0].blocks[0].type == "prose"
    assert again.sections[0].blocks[1].latex.startswith("L=")


def test_blocks_are_discriminated_by_type() -> None:
    r = PaperReport.model_validate(
        {
            "title": "T",
            "core_contributions": ["c"],
            "key_insight": "k",
            "sections": [
                {"heading": "H", "blocks": [{"type": "list", "items": ["a", "b"], "ordered": True}]}
            ],
        }
    )
    blk = r.sections[0].blocks[0]
    assert blk.type == "list" and blk.items == ["a", "b"] and blk.ordered is True
    assert r.references == []  # optional, defaults empty


def test_core_contributions_bounds_enforced() -> None:
    base = dict(title="T", key_insight="k",
                sections=[Section(heading="H", blocks=[ProseBlock(content="x")])])
    with pytest.raises(ValidationError):
        PaperReport(core_contributions=[], **base)
    with pytest.raises(ValidationError):
        PaperReport(core_contributions=["1", "2", "3", "4", "5", "6"], **base)


def test_unknown_block_type_rejected() -> None:
    with pytest.raises(ValidationError):
        PaperReport.model_validate(
            {
                "title": "T", "core_contributions": ["c"], "key_insight": "k",
                "sections": [{"heading": "H", "blocks": [{"type": "diagram", "content": "x"}]}],
            }
        )
```
Run: `uv run --package gulp-worker pytest services/worker/tests/test_pipeline_schemas.py -q`
Expected: 4 passed.

- [ ] **Step 3: Rewrite the ORM model — `knowledge_pack.py`**

Replace the entire contents of `services/shared/gulp_shared/models/knowledge_pack.py`:
```python
"""KnowledgePack — a structured paper report (docs/02 §4.4, S2 design §3)."""

import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class PackStatus(str, enum.Enum):
    generating = "generating"
    ready = "ready"


class PackBlockType(str, enum.Enum):
    prose = "prose"
    formula = "formula"
    table = "table"
    figure = "figure"
    list = "list"


class KnowledgePack(TimestampedBase, Base):
    __tablename__ = "knowledge_packs"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id"), unique=True, index=True
    )
    title: Mapped[str] = mapped_column(Text)
    key_insight: Mapped[str] = mapped_column(Text)
    core_contributions: Mapped[list[str]] = mapped_column(JSON, default=list)
    references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[PackStatus] = mapped_column(Enum(PackStatus, name="pack_status"))


class PackSection(TimestampedBase, Base):
    __tablename__ = "pack_sections"

    pack_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_packs.id"), index=True)
    heading: Mapped[str | None] = mapped_column(String, default=None)
    position: Mapped[int] = mapped_column(Integer, default=0)


class PackBlock(TimestampedBase, Base):
    __tablename__ = "pack_blocks"

    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pack_sections.id"), index=True)
    block_type: Mapped[PackBlockType] = mapped_column(Enum(PackBlockType, name="pack_block_type"))
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0)
```
Note: the column attribute `references` maps to a SQL-reserved identifier; SQLAlchemy's compiler auto-quotes it on both Postgres and SQLite.

- [ ] **Step 4: Drop `PackElement*` from the models package exports**

In `services/shared/gulp_shared/models/__init__.py`, change the `knowledge_pack` import block from:
```python
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackElement,
    PackElementState,
    PackElementType,
    PackSection,
    PackStatus,
)
```
to:
```python
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
```
And in the `__all__` list, delete the three lines `"PackElement",`, `"PackElementType",`, `"PackElementState",`.

- [ ] **Step 5: Replace `test_pack_models.py` and run it (expect PASS)**

Replace the entire contents of `services/shared/tests/test_pack_models.py`:
```python
import gulp_shared.models  # noqa: F401  (registers tables)
from gulp_shared.db import Base
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_pack_stores_report_fields_and_typed_blocks():
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="Example",
                  status=SnapshotStatus.ready)
    s.add(snap)
    s.flush()

    pack = KnowledgePack(
        snapshot_id=snap.id,
        title="BERT",
        key_insight="Change the objective, not the architecture.",
        core_contributions=["MLM enables bidirectionality."],
        references=[{"citation": "Vaswani 2017", "why_interesting": "Transformer."}],
        status=PackStatus.ready,
    )
    s.add(pack)
    s.flush()
    section = PackSection(pack_id=pack.id, heading="Mathematical Formulation", position=0)
    s.add(section)
    s.flush()
    s.add(PackBlock(section_id=section.id, block_type=PackBlockType.formula,
                    data={"latex": "a=b", "explanation": "trivial"}, position=0))
    s.commit()

    got = s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id))
    assert got is not None
    assert got.title == "BERT"
    assert got.core_contributions == ["MLM enables bidirectionality."]
    assert got.references[0]["citation"] == "Vaswani 2017"
    blk = s.scalar(select(PackBlock))
    assert blk.block_type == PackBlockType.formula
    assert blk.data == {"latex": "a=b", "explanation": "trivial"}
```
Run: `uv run --package gulp-shared pytest services/shared/tests/test_pack_models.py -q`
Expected: 1 passed.

- [ ] **Step 6: Rewrite the persist stage — `persist.py`**

Replace the entire contents of `services/worker/app/pipeline/persist.py`:
```python
"""Persist stage: PaperReport -> KnowledgePack + section/block rows.

Idempotent: a re-run drops the snapshot's existing pack and rebuilds it, so
re-Start cleanly regenerates. source.status is the caller's responsibility.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.pipeline.schemas import PaperReport
from gulp_shared.models.knowledge_pack import (  # type: ignore[import-untyped]
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import Source  # type: ignore[import-untyped]


def _delete_existing(db: Session, snapshot_id: object) -> None:
    pack = db.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snapshot_id))
    if pack is None:
        return
    for section in db.scalars(select(PackSection).where(PackSection.pack_id == pack.id)):
        for block in db.scalars(select(PackBlock).where(PackBlock.section_id == section.id)):
            db.delete(block)
        db.delete(section)
    db.delete(pack)
    db.flush()


def persist_pack(db: Session, source: Source, report: PaperReport) -> KnowledgePack:
    _delete_existing(db, source.id)
    pack = KnowledgePack(
        snapshot_id=source.id,
        title=report.title,
        key_insight=report.key_insight,
        core_contributions=list(report.core_contributions),
        references=[r.model_dump() for r in report.references],
        status=PackStatus.ready,
    )
    db.add(pack)
    db.flush()
    for i, section in enumerate(report.sections):
        row = PackSection(pack_id=pack.id, heading=section.heading, position=i)
        db.add(row)
        db.flush()
        for j, block in enumerate(section.blocks):
            db.add(
                PackBlock(
                    section_id=row.id,
                    block_type=PackBlockType(block.type),
                    data=block.model_dump(exclude={"type"}),
                    position=j,
                )
            )
    db.flush()
    return pack
```

- [ ] **Step 7: Replace `test_persist.py` and run it (expect PASS)**

Replace the entire contents of `services/worker/tests/test_persist.py`:
```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.pipeline.persist import persist_pack
from app.pipeline.schemas import (
    FormulaBlock,
    PaperReport,
    ProseBlock,
    Reference,
    Section,
)
from gulp_shared.db import Base  # type: ignore[import-untyped]
import gulp_shared.models  # type: ignore[import-untyped]  # noqa: F401
from gulp_shared.models.knowledge_pack import (  # type: ignore[import-untyped]
    KnowledgePack,
    PackBlock,
    PackBlockType,
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


_REPORT = PaperReport(
    title="BERT",
    key_insight="ki",
    core_contributions=["c1", "c2"],
    sections=[Section(heading="H", blocks=[
        ProseBlock(content="b0"),
        FormulaBlock(latex="a=b", explanation="x"),
    ])],
    references=[Reference(citation="V2017", why_interesting="t")],
)


def test_persist_writes_report_fields_and_typed_blocks() -> None:
    s = _session()
    snap = _snapshot(s)
    pack = persist_pack(s, snap, _REPORT)
    s.commit()

    got = s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id))
    assert got is not None
    assert got.status == PackStatus.ready
    assert got.title == "BERT" and got.key_insight == "ki"
    assert got.core_contributions == ["c1", "c2"]
    assert got.references == [{"citation": "V2017", "why_interesting": "t"}]
    sections = list(s.scalars(select(PackSection).where(PackSection.pack_id == pack.id)))
    assert len(sections) == 1 and sections[0].heading == "H"
    blocks = sorted(
        s.scalars(select(PackBlock).where(PackBlock.section_id == sections[0].id)),
        key=lambda b: b.position,
    )
    assert [b.block_type for b in blocks] == [PackBlockType.prose, PackBlockType.formula]
    assert blocks[0].data == {"content": "b0"}
    assert blocks[1].data == {"latex": "a=b", "explanation": "x"}


def test_persist_is_idempotent_and_replaces() -> None:
    s = _session()
    snap = _snapshot(s)
    persist_pack(s, snap, _REPORT)
    s.commit()
    persist_pack(s, snap, _REPORT)  # second run
    s.commit()
    packs = list(s.scalars(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id)))
    assert len(packs) == 1  # replaced, not duplicated
    blocks = list(s.scalars(select(PackBlock)))
    assert len(blocks) == 2  # not 4
```
Run: `uv run --package gulp-worker pytest services/worker/tests/test_persist.py -q`
Expected: 2 passed.

- [ ] **Step 8: Rewrite the digest prompt — `prompts/digest.py`**

Replace the entire contents of `services/worker/app/prompts/digest.py`:
```python
"""The digest prompt — turn a NormDoc into a deep, structured paper report."""

from app.llm.base import Message
from app.pipeline.normdoc import NormDoc

_SYSTEM = """You are an expert researcher and paper reviewer. Read the paper \
carefully and produce a comprehensive, technically deep research report as \
structured JSON.

Write everything in English, regardless of the source language.

## What to produce
- title — the paper's title.
- core_contributions — 1-5 concise, standalone statements of the paper's key \
contributions. This is the reader's primary skim entry.
- key_insight — the single most transferable / innovative idea behind the paper.
- sections — the report body (see outline below).
- references — interesting follow-up references mentioned in the paper, each with \
a citation and a one-line why_interesting. Optional but encouraged.

## Body outline (sections, in this order; omit one only if the paper genuinely \
does not support it)
1. The Core Challenge — the problem, why it is scientifically important, and the \
specific gap this paper addresses.
2. Overview of Approach — architecture, training techniques, data pipeline, novel \
mechanisms.
3. Mathematical Formulation & Technical Details — formalize the problem and the \
proposed solution; cover loss functions, engineering optimizations, and key \
hyperparameters. Use formula blocks for equations.
4. What the Experiments Show — use table blocks to compare against baselines, and \
interpret what the numbers actually demonstrate.
5. Strengths & Limitations.
6. Future Trajectories.
7. One Potential Improvement — one concrete, technical suggestion.

Do not repeat key_insight, core_contributions, or references as body sections.

## Block types (each section's blocks)
- prose — Markdown text; bold key terms with **...**, inline math as $...$.
- formula — a display equation: latex (the formula) + explanation (one line on \
what it means / does).
- table — headers + rows (+ optional caption); use for results and baseline \
comparisons.
- figure — label (e.g. "Figure 1") + explanation; no image is available, so \
describe in words what the figure conveys.
- list — items (+ optional ordered); use for hyperparameters, sub-points.

## Depth and faithfulness
- Prioritize technical depth: no superficial summaries. Include formulas, \
specific hyperparameters, and concrete examples from the paper.
- Sections 1-4 and all root fields: stay strictly faithful. Never invent facts, \
figures, names, or claims the source does not support. If the source is thin, \
say less rather than pad.
- Sections 5-7: this is your expert reviewer analysis. You may go beyond the \
source, but stay grounded in the paper's content and frame these as analysis / \
suggestions — do not fabricate empirical results.

## Reading the input
- Treat the source's main text as the body. Do not put the paper's own \
References section into the body, but you may mine it for follow-up references.
- Ignore extraction noise: ligatures (e.g. the ligature for "fi" in "fine"), \
broken tables, and inline page headers / arXiv banners.

Return your result via the provided tool."""


def build_digest_messages(normdoc: NormDoc, body: str) -> tuple[str, list[Message]]:
    user = f"Source type: {normdoc.media_type}\nTitle: {normdoc.title}\n\n---\n{body}"
    return _SYSTEM, [{"role": "user", "content": user}]
```

- [ ] **Step 9: Update `test_prompt_digest.py` and run it (expect PASS)**

In `services/worker/tests/test_prompt_digest.py`, replace the body of `test_system_prompt_states_the_rules` (keep `test_user_message_carries_title_media_type_and_body` unchanged):
```python
def test_system_prompt_states_the_rules() -> None:
    system, _ = build_digest_messages(_doc(), "Attention weighs tokens by relevance.")
    low = system.lower()
    assert "english" in low
    assert "report" in low
    assert "faithful" in low or "never invent" in low
    # the report outline and the root fields are described
    for needle in ("core challenge", "mathematical formulation", "experiments",
                   "core_contributions", "key_insight"):
        assert needle in low
    # the typed block vocabulary is described
    for block in ("formula", "table", "figure"):
        assert block in low
```
Run: `uv run --package gulp-worker pytest services/worker/tests/test_prompt_digest.py -q`
Expected: 2 passed.

- [ ] **Step 10: Rewrite the digest stage — `pipeline/digest.py`**

Replace the entire contents of `services/worker/app/pipeline/digest.py`:
```python
"""Digest stage: NormDoc -> PaperReport via the LLM service (one turn).

Single-pass with a budget guard: content over MAX_DIGEST_CHARS is truncated
before sending. Per-section map-reduce for long content is a later enhancement.
"""

from app.llm import ModelConfig, complete_structured
from app.llm.base import LLMProvider
from app.pipeline.normdoc import NormDoc
from app.pipeline.schemas import PaperReport
from app.prompts.digest import build_digest_messages
from gulp_shared.settings import settings  # type: ignore[import-untyped]

# ~12k tokens of input; tunable. Over this, we digest a prefix.
MAX_DIGEST_CHARS = 48_000


async def run_digest(
    normdoc: NormDoc,
    *,
    provider: LLMProvider | None = None,
    config: ModelConfig | None = None,
) -> PaperReport:
    cfg = config or ModelConfig(provider=settings.llm_provider, model=settings.llm_model)
    body = normdoc.content_body
    if len(body) > MAX_DIGEST_CHARS:
        body = body[:MAX_DIGEST_CHARS]
    system, messages = build_digest_messages(normdoc, body)
    return await complete_structured(
        response_model=PaperReport,
        system=system,
        messages=messages,
        config=cfg,
        provider=provider,
    )
```

- [ ] **Step 11: Replace `test_digest.py` and run it (expect PASS)**

Replace the entire contents of `services/worker/tests/test_digest.py`:
```python
from typing import Any

from app.llm.base import Message, ModelConfig
from app.pipeline.digest import MAX_DIGEST_CHARS, run_digest
from app.pipeline.normdoc import Anchor, NormBlock, NormDoc
from app.pipeline.schemas import PaperReport


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
    "title": "T",
    "core_contributions": ["c1"],
    "key_insight": "k",
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "references": [],
}


async def test_run_digest_returns_validated_result() -> None:
    prov = FakeProvider(_PAYLOAD)
    out = await run_digest(_doc("short body"), provider=prov)
    assert isinstance(out, PaperReport)
    assert out.title == "T" and out.core_contributions == ["c1"]
    assert prov.last_body is not None and "short body" in prov.last_body  # not truncated


async def test_over_budget_content_is_truncated() -> None:
    prov = FakeProvider(_PAYLOAD)
    big = "x" * (MAX_DIGEST_CHARS + 500)
    out = await run_digest(_doc(big), provider=prov)
    assert prov.last_body is not None and len(prov.last_body) <= MAX_DIGEST_CHARS + 100
    assert big[:MAX_DIGEST_CHARS] in prov.last_body  # truncated body was sent
    assert isinstance(out, PaperReport)
```
Run: `uv run --package gulp-worker pytest services/worker/tests/test_digest.py -q`
Expected: 2 passed.

- [ ] **Step 12: Rewrite the export templates — `export/templates.py`**

Replace the entire contents of `services/worker/app/export/templates.py`:
```python
"""Generated archive text — reuses the inline digest prompt (one source of truth)."""

from typing import Any

from app.pipeline.schemas import PaperReport
from app.prompts.digest import _SYSTEM


def pack_schema() -> dict[str, Any]:
    return PaperReport.model_json_schema()


def prompt_md() -> str:
    return _SYSTEM + "\n"


def claude_md() -> str:
    return """# Gulp paper-digest job

Turn a captured paper into a structured, technically deep research report,
written as JSON to `result/pack.json` and validating against
`schema/pack.schema.json`.

## How to run this job
1. Read `input/norm_doc.json` (a NormDoc: `title`, `content_body`, `blocks`).
2. Author the report by following `prompt.md` exactly.
3. Write the result to `result/pack.json`.
4. Validate `result/pack.json` against `schema/pack.schema.json`. Fix until it
   validates, then stop.

## Files
- Input:        `input/norm_doc.json`
- Instructions: `prompt.md`                (how to write the report)
- Schema:       `schema/pack.schema.json`  (output MUST validate against this)
- Output:       `result/pack.json`

When done, re-zip this folder and upload it back into Gulp.
"""
```

- [ ] **Step 13: Update the builder file map — `export/builder.py`**

In `services/worker/app/export/builder.py`, change the import line:
```python
from app.export.templates import claude_md, pack_schema, readme_md
```
to:
```python
from app.export.templates import claude_md, pack_schema, prompt_md
```
And replace the `files = { ... }` dict literal with:
```python
    files = {
        "CLAUDE.md": claude_md().encode(),
        "prompt.md": prompt_md().encode(),
        "manifest.json": json.dumps(manifest, indent=2).encode(),
        "input/norm_doc.json": norm_doc_bytes,
        "schema/pack.schema.json": json.dumps(pack_schema(), indent=2).encode(),
        "result/HOWTO.txt": b"Write pack.json here, matching ../schema/pack.schema.json.\n",
    }
```

- [ ] **Step 14: Update the importer to validate `PaperReport` — `export/importer.py`**

Replace the entire contents of `services/worker/app/export/importer.py`:
```python
"""Parse + validate an uploaded result archive into a PaperReport."""

import json

from app.export.archive import find_entry, read_zip
from app.pipeline.schemas import PaperReport


def import_result_archive(data: bytes) -> PaperReport:
    files = read_zip(data)
    try:
        raw = find_entry(files, "result/pack.json")
    except KeyError as exc:
        raise ValueError("archive has no result/pack.json") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("result/pack.json is not valid JSON") from exc
    return PaperReport.model_validate(payload)
```

- [ ] **Step 15: Replace `test_export_builder.py` and `test_export_importer.py`; run them**

Replace the entire contents of `services/worker/tests/test_export_builder.py`:
```python
import json

from app.export.archive import find_entry, read_zip
from app.export.builder import build_job_archive
from app.export.templates import claude_md, pack_schema, prompt_md
from app.pipeline.normdoc import Anchor, NormBlock, NormDoc


def _doc() -> NormDoc:
    body = "Attention weighs tokens by relevance."
    return NormDoc(title="A", lang="en", media_type="article", content_body=body,
                   blocks=[NormBlock(text=body, anchor=Anchor(start=0, end=len(body)))])


def test_pack_schema_prompt_and_claude_md():
    schema = pack_schema()
    props = schema["properties"]
    assert "sections" in props and "core_contributions" in props and "key_insight" in props
    assert "facets" not in props and "summary" not in props
    cm = claude_md()
    for needle in ("result/pack.json", "input/norm_doc.json", "schema/pack.schema.json", "prompt.md"):
        assert needle in cm
    pm = prompt_md()
    assert "expert" in pm.lower() and "core_contributions" in pm and "key_insight" in pm


def test_build_job_archive_has_all_entries():
    data = build_job_archive(snapshot_id="s1", owner_id="o1", normdoc=_doc(),
                             created_at="2026-06-26T00:00:00Z")
    files = read_zip(data)
    for suffix in ("CLAUDE.md", "prompt.md", "manifest.json", "input/norm_doc.json",
                   "schema/pack.schema.json", "result/HOWTO.txt"):
        assert find_entry(files, suffix)  # present, non-empty
    assert not any(name.endswith("README.md") for name in files)  # README dropped
    nd = json.loads(find_entry(files, "input/norm_doc.json"))
    assert nd["title"] == "A" and nd["blocks"][0]["text"].startswith("Attention")
    man = json.loads(find_entry(files, "manifest.json"))
    assert man["snapshot_id"] == "s1" and man["job_kind"] == "digest"
```

Replace the entire contents of `services/worker/tests/test_export_importer.py`:
```python
import json

import pytest
from pydantic import ValidationError

from app.export.archive import write_zip
from app.export.importer import import_result_archive

_VALID = {
    "title": "T",
    "core_contributions": ["c"],
    "key_insight": "k",
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "references": [],
}


def test_import_valid_result():
    data = write_zip({"gulp-job-x/result/pack.json": json.dumps(_VALID).encode()})
    out = import_result_archive(data)
    assert out.title == "T" and out.sections[0].blocks[0].content == "c"


def test_import_missing_pack_raises():
    data = write_zip({"gulp-job-x/manifest.json": b"{}"})
    with pytest.raises(ValueError):
        import_result_archive(data)


def test_import_invalid_shape_raises():
    # missing required core_contributions / key_insight / sections
    data = write_zip({"result/pack.json": json.dumps({"title": "T"}).encode()})
    with pytest.raises(ValidationError):
        import_result_archive(data)
```
Run: `uv run --package gulp-worker pytest services/worker/tests/test_export_builder.py services/worker/tests/test_export_importer.py -q`
Expected: 5 passed.

- [ ] **Step 16: Update the export-jobs integration payload — `test_export_jobs.py`**

In `services/worker/tests/test_export_jobs.py`, replace the `_VALID` literal (the old summary/facets dict) with:
```python
_VALID = {
    "title": "T",
    "core_contributions": ["c"],
    "key_insight": "k",
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "references": [],
}
```
(The `test_import_result_invalid_sets_exported` case feeds `{"summary":"only"}`, which is still invalid for `PaperReport`, so it stays correct — no other change needed.)
Run: `uv run --package gulp-worker pytest services/worker/tests/test_export_jobs.py -q`
Expected: 3 passed.

- [ ] **Step 17: Update the worker integration FakeProvider payload — `test_tasks.py`**

In `services/worker/tests/test_tasks.py`, replace the `FakeProvider.complete_json` return value with the new shape:
```python
class FakeProvider:
    async def complete_json(self, **kw: Any) -> dict[str, Any]:
        return {
            "title": "T",
            "core_contributions": ["c"],
            "key_insight": "k",
            "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
            "references": [],
        }
```
Run: `uv run --package gulp-worker pytest services/worker/tests/test_tasks.py -q`
Expected: 5 passed.

- [ ] **Step 18: Rewrite the API read schema — `api/schemas/pack.py`**

Replace the entire contents of `services/api/app/schemas/pack.py`:
```python
"""Pack read contract — these become the OpenAPI types the web client reads."""

import uuid
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from gulp_shared.models.knowledge_pack import PackStatus


class ProseBlockOut(BaseModel):
    type: Literal["prose"] = "prose"
    content: str


class FormulaBlockOut(BaseModel):
    type: Literal["formula"] = "formula"
    latex: str
    explanation: str


class TableBlockOut(BaseModel):
    type: Literal["table"] = "table"
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None


class FigureBlockOut(BaseModel):
    type: Literal["figure"] = "figure"
    label: str
    explanation: str


class ListBlockOut(BaseModel):
    type: Literal["list"] = "list"
    items: list[str]
    ordered: bool = False


BlockOut = Annotated[
    Union[ProseBlockOut, FormulaBlockOut, TableBlockOut, FigureBlockOut, ListBlockOut],
    Field(discriminator="type"),
]


class PackSectionOut(BaseModel):
    heading: str | None
    blocks: list[BlockOut]


class PackReferenceOut(BaseModel):
    citation: str
    why_interesting: str


class PackOut(BaseModel):
    snapshot_id: uuid.UUID
    status: PackStatus
    title: str
    core_contributions: list[str]
    key_insight: str
    sections: list[PackSectionOut]
    references: list[PackReferenceOut]
```

- [ ] **Step 19: Rewrite the API serializer — `api/services/pack.py`**

Replace the entire contents of `services/api/app/services/pack.py`:
```python
"""Serialize a snapshot's KnowledgePack into the PackOut contract."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.pack import PackOut, PackReferenceOut, PackSectionOut
from gulp_shared.models.knowledge_pack import KnowledgePack, PackBlock, PackSection


def pack_out(db: Session, snapshot_id: uuid.UUID) -> PackOut | None:
    pack = db.scalar(
        select(KnowledgePack).where(
            KnowledgePack.snapshot_id == snapshot_id,
            KnowledgePack.deleted_at.is_(None),
        )
    )
    if pack is None:
        return None

    sections: list[PackSectionOut] = []
    for section in db.scalars(
        select(PackSection)
        .where(PackSection.pack_id == pack.id, PackSection.deleted_at.is_(None))
        .order_by(PackSection.position)
    ):
        blocks = [
            {"type": b.block_type.value, **(b.data or {})}
            for b in db.scalars(
                select(PackBlock)
                .where(PackBlock.section_id == section.id, PackBlock.deleted_at.is_(None))
                .order_by(PackBlock.position)
            )
        ]
        sections.append(PackSectionOut(heading=section.heading, blocks=blocks))

    return PackOut(
        snapshot_id=snapshot_id,
        status=pack.status,
        title=pack.title,
        core_contributions=list(pack.core_contributions or []),
        key_insight=pack.key_insight,
        sections=sections,
        references=[PackReferenceOut(**r) for r in (pack.references or [])],
    )
```
Note: `PackSectionOut(blocks=[{...}, ...])` validates each plain dict into the `BlockOut` discriminated union via the `type` key.

- [ ] **Step 20: Replace the API pack tests and run them**

Replace the entire contents of `services/api/tests/test_pack_service.py`:
```python
import uuid

from app.services.pack import pack_out
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import Source, SnapshotStatus, SourceKind
from gulp_shared.models.user import DEV_USER_ID


def _snapshot(db) -> Source:
    snap = Source(
        owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
        status=SnapshotStatus.ready,
    )
    db.add(snap)
    db.flush()
    return snap


def _seed_pack(db, snapshot_id: uuid.UUID) -> None:
    pack = KnowledgePack(
        snapshot_id=snapshot_id, title="BERT", key_insight="ki",
        core_contributions=["c1", "c2"],
        references=[{"citation": "V2017", "why_interesting": "t"}],
        status=PackStatus.ready,
    )
    db.add(pack)
    db.flush()
    s0 = PackSection(pack_id=pack.id, heading="Overview", position=0)
    s1 = PackSection(pack_id=pack.id, heading="Details", position=1)
    db.add_all([s0, s1])
    db.flush()
    db.add(PackBlock(section_id=s0.id, block_type=PackBlockType.prose,
                     data={"content": "b0"}, position=0))
    db.add(PackBlock(section_id=s0.id, block_type=PackBlockType.formula,
                     data={"latex": "a=b", "explanation": "x"}, position=1))
    db.commit()


def test_pack_out_serializes_ordered_report(db) -> None:
    snap = _snapshot(db)
    _seed_pack(db, snap.id)
    out = pack_out(db, snap.id)
    assert out is not None
    assert out.status == PackStatus.ready and out.title == "BERT"
    assert out.core_contributions == ["c1", "c2"] and out.key_insight == "ki"
    assert [s.heading for s in out.sections] == ["Overview", "Details"]
    b0, b1 = out.sections[0].blocks
    assert b0.type == "prose" and b0.content == "b0"
    assert b1.type == "formula" and b1.latex == "a=b" and b1.explanation == "x"
    assert out.references[0].citation == "V2017"


def test_pack_out_returns_none_when_no_pack(db) -> None:
    snap = _snapshot(db)
    db.commit()
    assert pack_out(db, snap.id) is None
```

Replace the entire contents of `services/api/tests/test_pack_router.py`:
```python
import uuid

import pytest
from fastapi.testclient import TestClient

from app.deps import get_db
from app.main import app
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import Source, SnapshotStatus, SourceKind
from gulp_shared.models.user import DEV_USER_ID


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _ready_snapshot_with_pack(db) -> uuid.UUID:  # type: ignore[no-untyped-def]
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready)
    db.add(snap)
    db.flush()
    pack = KnowledgePack(snapshot_id=snap.id, title="BERT", key_insight="ki",
                         core_contributions=["c1"], references=[], status=PackStatus.ready)
    db.add(pack)
    db.flush()
    sec = PackSection(pack_id=pack.id, heading="H", position=0)
    db.add(sec)
    db.flush()
    db.add(PackBlock(section_id=sec.id, block_type=PackBlockType.prose,
                     data={"content": "hello"}, position=0))
    db.commit()
    return snap.id


def test_get_pack_returns_report(client, db) -> None:  # type: ignore[no-untyped-def]
    sid = _ready_snapshot_with_pack(db)
    r = client.get(f"/snapshots/{sid}/pack")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "BERT" and body["core_contributions"] == ["c1"]
    assert body["sections"][0]["blocks"][0]["content"] == "hello"
    assert body["sections"][0]["blocks"][0]["type"] == "prose"


def test_get_pack_404_when_no_pack(client, db) -> None:  # type: ignore[no-untyped-def]
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="N",
                  status=SnapshotStatus.unprocessed)
    db.add(snap)
    db.commit()
    r = client.get(f"/snapshots/{snap.id}/pack")
    assert r.status_code == 404


def test_get_pack_404_for_unknown_id(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/snapshots/00000000-0000-0000-0000-0000000000ff/pack")
    assert r.status_code == 404


def test_get_pack_404_for_foreign_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    foreign_snap = Source(
        owner_id=uuid.uuid4(), kind=SourceKind.snapshot, title="Foreign",
        status=SnapshotStatus.ready,
    )
    db.add(foreign_snap)
    db.commit()
    r = client.get(f"/snapshots/{foreign_snap.id}/pack")
    assert r.status_code == 404
```
Run: `uv run --package gulp-api pytest services/api/tests/test_pack_service.py services/api/tests/test_pack_router.py -q`
Expected: 6 passed.

- [ ] **Step 21: Create the Alembic migration**

Create `services/api/alembic/versions/a1b2c3d4e5f6_s2_paper_report_contract.py`:
```python
"""s2 paper report contract

Revision ID: a1b2c3d4e5f6
Revises: b14db36cfeec
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'b14db36cfeec'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop facets entirely.
    op.drop_index('ix_pack_elements_pack_id', table_name='pack_elements')
    op.drop_index('ix_pack_elements_concept_id', table_name='pack_elements')
    op.drop_table('pack_elements')
    op.execute("DROP TYPE IF EXISTS pack_element_type")
    op.execute("DROP TYPE IF EXISTS pack_element_state")

    # 2. knowledge_packs: narrative columns -> paper-report fields.
    op.drop_column('knowledge_packs', 'summary')
    op.drop_column('knowledge_packs', 'background')
    op.drop_column('knowledge_packs', 'confidence')
    op.add_column('knowledge_packs', sa.Column('title', sa.Text(), nullable=False, server_default=''))
    op.add_column('knowledge_packs', sa.Column('key_insight', sa.Text(), nullable=False, server_default=''))
    op.add_column('knowledge_packs', sa.Column('core_contributions', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('knowledge_packs', sa.Column('references', sa.JSON(), nullable=False, server_default='[]'))
    for col in ('title', 'key_insight', 'core_contributions', 'references'):
        op.alter_column('knowledge_packs', col, server_default=None)

    # 3. pack_blocks: content/anchor columns -> a single JSON `data`.
    op.drop_index('ix_pack_blocks_anchor_id', table_name='pack_blocks')
    op.drop_column('pack_blocks', 'content')
    op.drop_column('pack_blocks', 'content_ref')
    op.drop_column('pack_blocks', 'source_anchor')
    op.drop_column('pack_blocks', 'anchor_id')
    op.add_column('pack_blocks', sa.Column('data', sa.JSON(), nullable=False, server_default='{}'))
    op.alter_column('pack_blocks', 'data', server_default=None)

    # 4. Swap the block-type enum: callout/quote -> formula/table/list.
    op.execute("ALTER TYPE pack_block_type RENAME TO pack_block_type_old")
    op.execute("CREATE TYPE pack_block_type AS ENUM ('prose', 'formula', 'table', 'figure', 'list')")
    op.execute(
        "ALTER TABLE pack_blocks ALTER COLUMN block_type TYPE pack_block_type "
        "USING block_type::text::pack_block_type"
    )
    op.execute("DROP TYPE pack_block_type_old")


def downgrade() -> None:
    # Reverse 4.
    op.execute("ALTER TYPE pack_block_type RENAME TO pack_block_type_new")
    op.execute("CREATE TYPE pack_block_type AS ENUM ('prose', 'figure', 'callout', 'quote')")
    op.execute(
        "ALTER TABLE pack_blocks ALTER COLUMN block_type TYPE pack_block_type "
        "USING block_type::text::pack_block_type"
    )
    op.execute("DROP TYPE pack_block_type_new")

    # Reverse 3.
    op.add_column('pack_blocks', sa.Column('content', sa.Text(), nullable=True))
    op.add_column('pack_blocks', sa.Column('content_ref', sa.String(), nullable=True))
    op.add_column('pack_blocks', sa.Column('source_anchor', sa.JSON(), nullable=True))
    op.add_column('pack_blocks', sa.Column('anchor_id', sa.String(), nullable=False, server_default=''))
    op.alter_column('pack_blocks', 'anchor_id', server_default=None)
    op.drop_column('pack_blocks', 'data')
    op.create_index('ix_pack_blocks_anchor_id', 'pack_blocks', ['anchor_id'], unique=False)

    # Reverse 2.
    op.add_column('knowledge_packs', sa.Column('summary', sa.Text(), nullable=False, server_default=''))
    op.alter_column('knowledge_packs', 'summary', server_default=None)
    op.add_column('knowledge_packs', sa.Column('background', sa.Text(), nullable=True))
    op.add_column('knowledge_packs', sa.Column('confidence', sa.Float(), nullable=True))
    op.drop_column('knowledge_packs', 'references')
    op.drop_column('knowledge_packs', 'core_contributions')
    op.drop_column('knowledge_packs', 'key_insight')
    op.drop_column('knowledge_packs', 'title')

    # Reverse 1.
    op.create_table(
        'pack_elements',
        sa.Column('pack_id', sa.Uuid(), nullable=False),
        sa.Column('element_type', sa.Enum('key_term', 'person_org', 'claim', 'counter_view', 'connection', name='pack_element_type'), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('concept_id', sa.Uuid(), nullable=True),
        sa.Column('block_id', sa.Uuid(), nullable=True),
        sa.Column('section_label', sa.String(), nullable=True),
        sa.Column('state', sa.Enum('suggested', 'kept', 'dismissed', name='pack_element_state'), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['block_id'], ['pack_blocks.id'], ),
        sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
        sa.ForeignKeyConstraint(['pack_id'], ['knowledge_packs.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pack_elements_concept_id', 'pack_elements', ['concept_id'], unique=False)
    op.create_index('ix_pack_elements_pack_id', 'pack_elements', ['pack_id'], unique=False)
```

- [ ] **Step 22: Verify single migration head + upgrade/downgrade round-trip**

Run (brings local Postgres up first):
```bash
just up
cd services/api && uv run --package gulp-api alembic heads
```
Expected: exactly one head — `a1b2c3d4e5f6 (head)`.
Then round-trip:
```bash
cd services/api && uv run --package gulp-api alembic upgrade head \
  && uv run --package gulp-api alembic downgrade -1 \
  && uv run --package gulp-api alembic upgrade head
```
Expected: all three commands exit 0 with no error (upgrade applies the new shape, downgrade restores the old shape, re-upgrade re-applies).

- [ ] **Step 23: Run the full Python suites (expect all green)**

Run:
```bash
uv run pytest
```
Expected: the whole Python test suite passes — worker, shared, and api (including `test_export_jobs`, `test_tasks`, `test_pack_service`, `test_pack_router`).
Then lint/typecheck:
```bash
uv run ruff check . && uv run mypy .
```
Expected: no errors.

- [ ] **Step 24: Commit the Python contract**

```bash
git add services/worker services/shared services/api
git commit -m "feat(s2): swap DigestResult for the PaperReport contract end-to-end (Python)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Regenerate the TypeScript API client

**Files:**
- Modify: `packages/api-client/openapi.json` (regenerated)
- Modify: `packages/api-client/src/schema.gen.ts` (regenerated)

**Interfaces:**
- Consumes: the new `PackOut` from Task 1.
- Produces: `PackOut` in `@gulp/api-client` with `title`, `core_contributions`, `key_insight`, `sections[].blocks[]` (discriminated union on `type`), `references[]`; no `facets`/`summary`/`background`/`confidence`. Consumed by Task 3.

- [ ] **Step 1: Regenerate the client**

Run:
```bash
just gen-client
```
Expected: exits 0; `packages/api-client/openapi.json` and `packages/api-client/src/schema.gen.ts` are rewritten.

- [ ] **Step 2: Verify the generated contract**

Run:
```bash
grep -c "core_contributions" packages/api-client/src/schema.gen.ts
grep -c "key_insight" packages/api-client/src/schema.gen.ts
grep -c "FormulaBlockOut" packages/api-client/src/schema.gen.ts
grep -c "PackFacetOut" packages/api-client/src/schema.gen.ts
```
Expected: the first three are `>=1`; the last (`PackFacetOut`) is `0` (facets gone). Then typecheck the package:
```bash
pnpm --filter @gulp/api-client run build || pnpm --filter @gulp/api-client exec tsc --noEmit
```
Expected: no type errors. (If the package has no build/typecheck script, this is a no-op; the real typecheck happens in Task 3's web build.)

- [ ] **Step 3: Commit the regenerated client**

```bash
git add packages/api-client/openapi.json packages/api-client/src/schema.gen.ts
git commit -m "chore(api-client): regenerate for the PaperReport pack contract

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Render the PaperReport on the web (KaTeX, drop facets)

**Files:**
- Modify: `apps/web/package.json` (add deps)
- Modify: `apps/web/lib/pack.ts` (drop facet helpers)
- Test: `apps/web/lib/pack.test.ts` (drop facet tests)
- Modify: `apps/web/components/snapshot/PackReport.tsx` (full replacement)
- Modify: `apps/web/components/snapshot/PackReport.module.css` (new block styles)
- Test: `apps/web/components/snapshot/PackReport.test.tsx` (full replacement)
- Modify: `apps/web/components/snapshot/ReaderToggle.tsx` (drop facet rail)
- Delete: `apps/web/components/snapshot/FacetRail.tsx`
- Delete: `apps/web/components/snapshot/FacetRail.module.css`

**Interfaces:**
- Consumes: the regenerated `PackOut` from Task 2.
- Produces: a `PackReport` that renders title, core contributions, key insight, typed blocks (prose/formula/table/figure/list), and references; `ReaderToggle` that shows only the report (no rail).

- [ ] **Step 1: Add rendering dependencies**

Run (requires network access to the pnpm registry):
```bash
pnpm --filter @gulp/web add katex@^0.16.11 react-markdown@^9.0.1 remark-math@^6.0.0 remark-gfm@^4.0.0 rehype-katex@^7.0.1
pnpm --filter @gulp/web add -D @types/katex@^0.16.7
```
Expected: `apps/web/package.json` gains these under `dependencies`/`devDependencies` and the lockfile updates.

- [ ] **Step 2: Trim `lib/pack.ts` (remove facet helpers)**

Replace the entire contents of `apps/web/lib/pack.ts`:
```ts
import type { Snapshot } from "@gulp/api-client";

// The poller keeps going while the snapshot is still being processed.
export function isProcessing(status: Snapshot["status"]): boolean {
  return status === "processing" || status === "queued";
}

export function statusLabel(status: Snapshot["status"]): string {
  if (status === "processing" || status === "queued") return "Processing";
  if (status === "needs_attention") return "Needs attention";
  if (status === "unprocessed") return "Not started";
  if (status === "exported") return "Exported";
  return "Ready";
}

// Host label for a source; never throws on a malformed/relative URL.
export function safeHost(url: string | null | undefined): string {
  if (!url) return "Note";
  try {
    return new URL(url).host;
  } catch {
    return "Note";
  }
}
```

- [ ] **Step 3: Trim `lib/pack.test.ts` (drop facet tests)**

Replace the entire contents of `apps/web/lib/pack.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { isProcessing, safeHost, statusLabel } from "./pack";

describe("isProcessing", () => {
  it("is true only for processing/queued", () => {
    expect(isProcessing("processing")).toBe(true);
    expect(isProcessing("queued")).toBe(true);
    expect(isProcessing("ready")).toBe(false);
    expect(isProcessing("needs_attention")).toBe(false);
  });
});

describe("statusLabel", () => {
  it("labels exported and the rest", () => {
    expect(statusLabel("exported")).toBe("Exported");
    expect(statusLabel("ready")).toBe("Ready");
    expect(statusLabel("unprocessed")).toBe("Not started");
  });
});

describe("safeHost", () => {
  it("returns host for a valid URL", () => {
    expect(safeHost("https://example.com/x")).toBe("example.com");
  });

  it("returns Note for a schemeless URL", () => {
    expect(safeHost("example.com")).toBe("Note");
  });

  it("returns Note for null", () => {
    expect(safeHost(null)).toBe("Note");
  });
});
```

- [ ] **Step 4: Rewrite `PackReport.tsx`**

Replace the entire contents of `apps/web/components/snapshot/PackReport.tsx`:
```tsx
import React from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import type { PackOut } from "@gulp/api-client";
import styles from "./PackReport.module.css";

type Block = PackOut["sections"][number]["blocks"][number];

function Md({ children }: { children: string }) {
  return (
    <Markdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
      {children}
    </Markdown>
  );
}

function BlockView({ block }: { block: Block }) {
  switch (block.type) {
    case "prose":
      return (
        <div className={styles.prose}>
          <Md>{block.content}</Md>
        </div>
      );
    case "formula":
      return (
        <figure className={styles.formula}>
          <Md>{`$$\n${block.latex}\n$$`}</Md>
          <figcaption className={styles.explanation}>{block.explanation}</figcaption>
        </figure>
      );
    case "table":
      return (
        <figure className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                {block.headers.map((h, i) => (
                  <th key={i}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, r) => (
                <tr key={r}>
                  {row.map((cell, c) => (
                    <td key={c}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {block.caption && <figcaption className={styles.caption}>{block.caption}</figcaption>}
        </figure>
      );
    case "figure":
      return (
        <figure className={styles.figure}>
          <div className={styles.figureLabel}>{block.label}</div>
          <div className={styles.explanation}>{block.explanation}</div>
        </figure>
      );
    case "list":
      return block.ordered ? (
        <ol className={styles.list}>
          {block.items.map((it, i) => (
            <li key={i}>
              <Md>{it}</Md>
            </li>
          ))}
        </ol>
      ) : (
        <ul className={styles.list}>
          {block.items.map((it, i) => (
            <li key={i}>
              <Md>{it}</Md>
            </li>
          ))}
        </ul>
      );
    default:
      return null;
  }
}

export function PackReport({ pack }: { pack: PackOut }) {
  return (
    <article className={styles.report}>
      <h1 className={styles.title}>{pack.title}</h1>

      {pack.core_contributions.length > 0 && (
        <section className={styles.contributions}>
          <h2 className={styles.heading}>Core contributions</h2>
          <ul className={styles.list}>
            {pack.core_contributions.map((c, i) => (
              <li key={i}>
                <Md>{c}</Md>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className={styles.insight}>
        <h2 className={styles.heading}>Key insight</h2>
        <div className={styles.prose}>
          <Md>{pack.key_insight}</Md>
        </div>
      </section>

      {pack.sections.map((section, i) => (
        <section key={i} className={styles.section}>
          {section.heading && <h2 className={styles.heading}>{section.heading}</h2>}
          {section.blocks.map((block, j) => (
            <BlockView key={j} block={block} />
          ))}
        </section>
      ))}

      {pack.references.length > 0 && (
        <section className={styles.references}>
          <h2 className={styles.heading}>Further reading</h2>
          <ul className={styles.list}>
            {pack.references.map((r, i) => (
              <li key={i}>
                <strong>{r.citation}</strong> — {r.why_interesting}
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
```

- [ ] **Step 5: Update `PackReport.module.css`**

Replace the entire contents of `apps/web/components/snapshot/PackReport.module.css`:
```css
.report { max-width: 720px; }
.title { font-size: 24px; line-height: 30px; font-weight: 650; margin-bottom: 20px; }
.section { margin-bottom: 28px; }
.contributions, .insight, .references { margin-bottom: 28px; }
.heading { font-weight: 600; font-size: 18px; line-height: 24px; margin-bottom: 10px; }
.prose { line-height: 22px; margin-bottom: 10px; }
.list { line-height: 22px; margin: 0 0 10px 20px; }
.formula { margin: 12px 0; overflow-x: auto; }
.explanation { font-size: 13px; color: var(--text-muted, #777); margin-top: 4px; }
.tableWrap { margin: 12px 0; overflow-x: auto; }
.table { border-collapse: collapse; font-size: 13px; width: 100%; }
.table th, .table td { border: 1px solid var(--border, #ddd); padding: 4px 8px; text-align: left; }
.caption { font-size: 13px; color: var(--text-muted, #777); margin-top: 6px; }
.figure { background: var(--surface-2, #f6f6f6); border-radius: var(--radius-sm, 6px); padding: 10px 12px; margin: 12px 0; }
.figureLabel { font-weight: 600; font-size: 13px; margin-bottom: 4px; }
```

- [ ] **Step 6: Rewrite `PackReport.test.tsx` (drop FacetRail, cover the new blocks)**

Replace the entire contents of `apps/web/components/snapshot/PackReport.test.tsx`:
```tsx
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { PackOut } from "@gulp/api-client";
import { PackReport } from "./PackReport";

const pack: PackOut = {
  snapshot_id: "00000000-0000-0000-0000-000000000001",
  status: "ready",
  title: "BERT",
  core_contributions: ["MLM enables **bidirectionality**."],
  key_insight: "Change the objective.",
  sections: [
    {
      heading: "Math",
      blocks: [
        { type: "prose", content: "Loss is $L=-\\sum_i y_i$ here." },
        { type: "formula", latex: "E=mc^2", explanation: "Mass-energy." },
        { type: "table", headers: ["Model", "F1"], rows: [["BERT", "93.2"]], caption: "Results" },
        { type: "list", ordered: false, items: ["lr=1e-4"] },
        { type: "figure", label: "Figure 1", explanation: "Architecture overview." },
      ],
    },
  ],
  references: [{ citation: "Vaswani 2017", why_interesting: "Transformer." }],
};

describe("PackReport", () => {
  it("renders title, contributions, key insight and references", () => {
    const html = renderToStaticMarkup(<PackReport pack={pack} />);
    expect(html).toContain("BERT");
    expect(html).toContain("Core contributions");
    expect(html).toContain("<strong>bidirectionality</strong>");
    expect(html).toContain("Key insight");
    expect(html).toContain("Vaswani 2017");
  });

  it("renders typed blocks: math via KaTeX, real tables, lists, figures", () => {
    const html = renderToStaticMarkup(<PackReport pack={pack} />);
    expect(html).toContain("katex"); // rehype-katex typeset both inline and display math
    expect(html).toContain("<table");
    expect(html).toContain("93.2");
    expect(html).toContain("Results");
    expect(html).toContain("lr=1e-4");
    expect(html).toContain("Figure 1");
    expect(html).toContain("Architecture overview.");
  });
});
```

- [ ] **Step 7: Drop the facet rail from `ReaderToggle.tsx`**

Replace the entire contents of `apps/web/components/snapshot/ReaderToggle.tsx`:
```tsx
"use client";

import { useState } from "react";
import type { PackOut } from "@gulp/api-client";
import { PackReport } from "./PackReport";
import styles from "./ReaderToggle.module.css";

export function ReaderToggle({ pack, original }: { pack: PackOut; original: string | null }) {
  const [view, setView] = useState<"pack" | "original">("pack");
  return (
    <div>
      <div className={styles.bar}>
        <button
          className={`${styles.tab} ${view === "pack" ? styles.active : ""}`}
          onClick={() => setView("pack")}
        >
          Pack
        </button>
        <button
          className={`${styles.tab} ${view === "original" ? styles.active : ""}`}
          onClick={() => setView("original")}
          disabled={!original}
        >
          Original
        </button>
      </div>
      {view === "pack" ? (
        <div className={styles.main}>
          <PackReport pack={pack} />
        </div>
      ) : (
        <div className={styles.original}>{original ?? "No original text stored."}</div>
      )}
    </div>
  );
}
```

- [ ] **Step 8: Delete the FacetRail files**

```bash
git rm apps/web/components/snapshot/FacetRail.tsx apps/web/components/snapshot/FacetRail.module.css
```

- [ ] **Step 9: Run the web tests and lint (expect green)**

Run:
```bash
pnpm --filter @gulp/web test
pnpm --filter @gulp/web run lint
```
Expected: vitest passes (`pack.test.ts` + `PackReport.test.tsx`); eslint clean. If lint flags a remaining `groupFacets`/`Facet`/`FacetRail` reference anywhere, remove it.

- [ ] **Step 10: Commit the frontend**

```bash
git add apps/web
git commit -m "feat(web): render the PaperReport pack (KaTeX math, tables, lists); drop facet rail

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage:**
- Contract `PaperReport` (root fields, Section, 5 Block variants, Reference) → Task 1 Step 1–2. ✓
- Python source-of-truth + generated schema (`pack_schema()` from `PaperReport`) → Task 1 Step 12, asserted Step 15. ✓
- Prompt split (authoring guide `_SYSTEM`/`prompt_md`; lean `claude_md`) → Task 1 Steps 8, 12, 13. ✓
- Builder file map (add `prompt.md`, drop `README.md`) → Task 1 Step 13, asserted Step 15. ✓
- Importer validates `PaperReport`; digest returns `PaperReport`, confidence dropped → Steps 14, 10. ✓
- DB model (new columns/enum, drop `PackElement*`) + migration → Steps 3, 4, 21; round-trip Step 22. ✓
- Persist maps report → rows, drops facets → Step 6. ✓
- API `PackOut` + serializer + client regen → Steps 18, 19; Task 2. ✓
- Frontend KaTeX render + drop FacetRail → Task 3. ✓
- Dropped `summary`/`background`/`confidence`/`facets`/`callout`/`quote`/anchoring → enforced by model/schema (Steps 1, 3) and asserted absent (Steps 15, Task 2 Step 2). ✓
- Pre-production migration, no backfill → Step 21 (drop/recreate), Step 22 (round-trip). ✓

**2. Placeholder scan:** No TBD/TODO. Every code step shows full file contents or an exact edit. Task 1 Step 22/23 are verification commands with explicit expected output. The one conditional ("if lint flags a remaining reference") in Task 3 Step 9 is a guarded cleanup, not a placeholder. ✓

**3. Type consistency:** Field/symbol names are identical across layers — `PaperReport`/`Section`/`Reference`; blocks `ProseBlock`/`FormulaBlock`/`TableBlock`/`FigureBlock`/`ListBlock` with fields `content`/`latex`+`explanation`/`headers`+`rows`+`caption`/`label`+`explanation`/`items`+`ordered`; ORM `PackBlockType ∈ {prose,formula,table,figure,list}` and `PackBlock.data`; `persist_pack(..., report)`, `import_result_archive(...) -> PaperReport`, `run_digest(...) -> PaperReport`; API `PackOut{title, core_contributions, key_insight, sections, references}` mirrored by the generated client and consumed by `PackReport.tsx`. The block `type` literals match the enum string values exactly (Global Constraints). ✓
