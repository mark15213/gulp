# S2 Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the persistence layer S2 needs — `KnowledgePack` (as a readable report) + `Card` + `Concept` graph models, the `unprocessed` snapshot status, and a migration — so later S2 plans (LLM layer, pipeline) have schema to write into.

**Architecture:** New SQLAlchemy 2.0 ORM models in `services/shared/gulp_shared/models/`, each inheriting `(TimestampedBase, Base)` exactly like the existing `Source`. The Knowledge Pack is modeled as a report spine (`KnowledgePack → PackSection → PackBlock`) with facet-annotations (`PackElement`) hanging off blocks, per `docs/subsystems/S2-processing-design.md §3` and `docs/02-data-model.md §4.4`. A single Alembic migration creates all new tables and adds the `unprocessed` value to the existing `snapshot_status` enum.

**Tech Stack:** Python 3.13, SQLAlchemy 2.0 (sync), Alembic, PostgreSQL 17 (prod), SQLite in-memory (tests), uv workspace, `just` recipes.

## Global Constraints

- **Persistence lives only in `gulp_shared`** — never redefine these models in `services/api` or `services/worker` (CLAUDE.md, `docs/05` D4).
- **Every model** inherits `class X(TimestampedBase, Base)` (gives `id`/`created_at`/`updated_at`/`deleted_at`) and is registered in `gulp_shared/models/__init__.py` so `Base.metadata` and Alembic autogenerate see it.
- **Enums** are `class E(str, enum.Enum)` with a snake_case `name=` on the column (e.g. `Enum(PackStatus, name="pack_status")`), matching `Source`.
- **Collections:** the report is **child tables** (`PackSection`/`PackBlock`); small atomic ordered scalars (`Card.options`, `Concept.aliases`, `PackBlock.source_anchor`) are **`JSON` columns** (`docs/02` §2.3 inv. 7, S2 design §7.3).
- **Defer S5's fields:** do **not** add `scheduling`/`mastery` to `Card` or `Concept` — S5 owns them (S2 ships `draft` cards only).
- **Migration:** new revision with `down_revision = '00371ef138ba'`.
- **Quality gates:** `just test` (pytest) and `just lint` (mypy strict + ruff, line-length 100) must pass. Run via `just`, never the raw tool.
- **TDD + frequent commits:** one model module per task, test-first, commit per task.

---

## File Structure

- `services/shared/gulp_shared/models/card.py` *(new)* — `Card` + `CardType`/`CardOrigin`/`CardStatus`. Depends on `sources` only.
- `services/shared/gulp_shared/models/concept.py` *(new)* — `Concept`, `ConceptEdge`, `CardConcept`, `SourceConcept` + `ConceptType`/`ConceptRelation`. Depends on `concepts`, `cards`, `sources`.
- `services/shared/gulp_shared/models/knowledge_pack.py` *(new)* — `KnowledgePack`, `PackSection`, `PackBlock`, `PackElement` + their enums. Depends on `sources`, `concepts`.
- `services/shared/gulp_shared/models/source.py` *(modify)* — add `unprocessed` to `SnapshotStatus`; update the deferred comment.
- `services/shared/gulp_shared/models/__init__.py` *(modify)* — export all new models + enums.
- `services/api/alembic/versions/<rev>_s2_knowledge_pack.py` *(new, generated)* — create all new tables + `ALTER TYPE snapshot_status ADD VALUE 'unprocessed'`.
- Tests *(new)*: `test_card_model.py`, `test_concept_models.py`, `test_pack_models.py` under `services/shared/tests/`; one new test in the existing `test_models.py`.

Task order is FK-dependency-driven so each task's SQLite `create_all` resolves: **Card → Concept(+joins) → KnowledgePack → enum → migration.**

---

### Task 1: `Card` model

**Files:**
- Create: `services/shared/gulp_shared/models/card.py`
- Modify: `services/shared/gulp_shared/models/__init__.py`
- Test: `services/shared/tests/test_card_model.py`

**Interfaces:**
- Consumes: `gulp_shared.db.{Base, TimestampedBase}`; `sources.id` (existing FK target).
- Produces: `Card`, `CardType{short_answer·mcq·cloze·explain·apply·recall}`, `CardOrigin{pack·conversation·user}`, `CardStatus{draft·accepted·rejected}`. Table `cards`; columns `source_id?`, `card_type`, `prompt`, `answer?`, `explanation?`, `options?` (JSON list), `origin`, `status` (default `draft`).

- [ ] **Step 1: Write the failing test**

Create `services/shared/tests/test_card_model.py`:

```python
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from gulp_shared.db import Base
import gulp_shared.models  # noqa: F401  (registers tables)
from gulp_shared.models.card import Card, CardOrigin, CardStatus, CardType
from gulp_shared.models.source import Source, SnapshotStatus, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_draft_mcq_card_persists_with_options_and_defaults():
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="Example",
        status=SnapshotStatus.ready,
    )
    s.add(snap)
    s.flush()
    card = Card(
        source_id=snap.id,
        card_type=CardType.mcq,
        prompt="What is X?",
        answer="A",
        explanation="Because the source says so.",
        options=["A", "B", "C", "D"],
        origin=CardOrigin.pack,
    )
    s.add(card)
    s.commit()

    got = s.scalar(select(Card).where(Card.source_id == snap.id))
    assert got is not None
    assert got.status == CardStatus.draft  # default
    assert got.options == ["A", "B", "C", "D"]
    assert got.explanation == "Because the source says so."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/shared && uv run pytest tests/test_card_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gulp_shared.models.card'`

- [ ] **Step 3: Write the model**

Create `services/shared/gulp_shared/models/card.py`:

```python
"""Card — the atomic testable unit; S2 drafts cards (docs/02 §4.5, S2 design §4)."""

import enum
import uuid

from sqlalchemy import JSON, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class CardType(str, enum.Enum):
    short_answer = "short_answer"
    mcq = "mcq"
    cloze = "cloze"
    explain = "explain"
    apply = "apply"
    recall = "recall"


class CardOrigin(str, enum.Enum):
    pack = "pack"
    conversation = "conversation"
    user = "user"


class CardStatus(str, enum.Enum):
    draft = "draft"
    accepted = "accepted"
    rejected = "rejected"


class Card(TimestampedBase, Base):
    __tablename__ = "cards"

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id"), default=None, index=True
    )
    card_type: Mapped[CardType] = mapped_column(Enum(CardType, name="card_type"))
    prompt: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, default=None)
    explanation: Mapped[str | None] = mapped_column(Text, default=None)
    options: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    origin: Mapped[CardOrigin] = mapped_column(Enum(CardOrigin, name="card_origin"))
    status: Mapped[CardStatus] = mapped_column(
        Enum(CardStatus, name="card_status"), default=CardStatus.draft
    )
    # Deferred: scheduling / mastery value objects — added by S5.
```

- [ ] **Step 4: Register in `models/__init__.py`**

Edit `services/shared/gulp_shared/models/__init__.py` — add the import (after the `source_tag` import) and the `__all__` entries:

```python
from gulp_shared.models.card import Card, CardOrigin, CardStatus, CardType
```

Add to `__all__`: `"Card", "CardType", "CardOrigin", "CardStatus",`

- [ ] **Step 5: Run test to verify it passes**

Run: `cd services/shared && uv run pytest tests/test_card_model.py -v`
Expected: PASS

- [ ] **Step 6: Lint + commit**

```bash
just lint
git add services/shared/gulp_shared/models/card.py services/shared/gulp_shared/models/__init__.py services/shared/tests/test_card_model.py
git commit -m "feat(s2): add Card model"
```

---

### Task 2: `Concept` + edges + typed-link models

**Files:**
- Create: `services/shared/gulp_shared/models/concept.py`
- Modify: `services/shared/gulp_shared/models/__init__.py`
- Test: `services/shared/tests/test_concept_models.py`

**Interfaces:**
- Consumes: `gulp_shared.db.{Base, TimestampedBase}`; `concepts.id`, `cards.id` (Task 1), `sources.id`.
- Produces: `Concept` (`concept_type`, `name` indexed, `aliases?` JSON, `definition?`), `ConceptEdge` (`from_concept_id`, `to_concept_id`, `relation`, `weight?`), `CardConcept` (`card_id`, `concept_id`, `role?`), `SourceConcept` (`source_id`, `concept_id`, `role?`). Enums `ConceptType{idea·term·person·org}`, `ConceptRelation{related·part_of·contrasts·causes·example_of}`.

- [ ] **Step 1: Write the failing test**

Create `services/shared/tests/test_concept_models.py`:

```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from gulp_shared.db import Base
import gulp_shared.models  # noqa: F401  (registers tables)
from gulp_shared.models.card import Card, CardOrigin, CardType
from gulp_shared.models.concept import (
    CardConcept,
    Concept,
    ConceptEdge,
    ConceptRelation,
    ConceptType,
    SourceConcept,
)
from gulp_shared.models.source import Source, SnapshotStatus, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_concept_graph_and_links_persist():
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="Example",
        status=SnapshotStatus.ready,
    )
    s.add(snap)
    s.flush()

    a = Concept(concept_type=ConceptType.term, name="Transformer", aliases=["xformer"])
    b = Concept(concept_type=ConceptType.idea, name="Attention")
    s.add_all([a, b])
    s.flush()
    s.add(ConceptEdge(from_concept_id=a.id, to_concept_id=b.id, relation=ConceptRelation.part_of))

    card = Card(source_id=snap.id, card_type=CardType.cloze, prompt="___", origin=CardOrigin.pack)
    s.add(card)
    s.flush()
    s.add(CardConcept(card_id=card.id, concept_id=a.id, role="tests"))
    s.add(SourceConcept(source_id=snap.id, concept_id=a.id, role="about"))
    s.commit()

    got = s.scalar(select(Concept).where(Concept.name == "Transformer"))
    assert got is not None and got.aliases == ["xformer"]
    edge = s.scalar(select(ConceptEdge))
    assert edge.relation == ConceptRelation.part_of
    assert s.scalar(select(CardConcept)).role == "tests"
    assert s.scalar(select(SourceConcept)).role == "about"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/shared && uv run pytest tests/test_concept_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gulp_shared.models.concept'`

- [ ] **Step 3: Write the model**

Create `services/shared/gulp_shared/models/concept.py`:

```python
"""Concept + edges + typed links — the knowledge graph spine (docs/02 §4.6)."""

import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class ConceptType(str, enum.Enum):
    idea = "idea"
    term = "term"
    person = "person"
    org = "org"


class ConceptRelation(str, enum.Enum):
    related = "related"
    part_of = "part_of"
    contrasts = "contrasts"
    causes = "causes"
    example_of = "example_of"


class Concept(TimestampedBase, Base):
    __tablename__ = "concepts"

    concept_type: Mapped[ConceptType] = mapped_column(Enum(ConceptType, name="concept_type"))
    name: Mapped[str] = mapped_column(String, index=True)
    aliases: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    definition: Mapped[str | None] = mapped_column(Text, default=None)
    # Deferred: mastery rollup — added by S5.


class ConceptEdge(TimestampedBase, Base):
    __tablename__ = "concept_edges"

    from_concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    to_concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    relation: Mapped[ConceptRelation] = mapped_column(
        Enum(ConceptRelation, name="concept_relation")
    )
    weight: Mapped[float | None] = mapped_column(Float, default=None)


class CardConcept(TimestampedBase, Base):
    __tablename__ = "card_concepts"

    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cards.id"), index=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    role: Mapped[str | None] = mapped_column(String, default=None)


class SourceConcept(TimestampedBase, Base):
    __tablename__ = "source_concepts"

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    role: Mapped[str | None] = mapped_column(String, default=None)
```

- [ ] **Step 4: Register in `models/__init__.py`**

Add the import:

```python
from gulp_shared.models.concept import (
    CardConcept,
    Concept,
    ConceptEdge,
    ConceptRelation,
    ConceptType,
    SourceConcept,
)
```

Add to `__all__`: `"Concept", "ConceptType", "ConceptEdge", "ConceptRelation", "CardConcept", "SourceConcept",`

- [ ] **Step 5: Run test to verify it passes**

Run: `cd services/shared && uv run pytest tests/test_concept_models.py -v`
Expected: PASS

- [ ] **Step 6: Lint + commit**

```bash
just lint
git add services/shared/gulp_shared/models/concept.py services/shared/gulp_shared/models/__init__.py services/shared/tests/test_concept_models.py
git commit -m "feat(s2): add Concept graph + typed-link models"
```

---

### Task 3: `KnowledgePack` report + facet models

**Files:**
- Create: `services/shared/gulp_shared/models/knowledge_pack.py`
- Modify: `services/shared/gulp_shared/models/__init__.py`
- Test: `services/shared/tests/test_pack_models.py`

**Interfaces:**
- Consumes: `gulp_shared.db.{Base, TimestampedBase}`; `sources.id`, `concepts.id` (Task 2), `knowledge_packs.id`, `pack_sections.id`, `pack_blocks.id` (self).
- Produces: `KnowledgePack` (`snapshot_id` unique 1–1, `summary`, `background?`, `confidence?`, `status`), `PackSection` (`pack_id`, `heading?`, `position`), `PackBlock` (`section_id`, `block_type`, `content?`, `content_ref?`, `source_anchor?` JSON, `anchor_id` indexed, `position`), `PackElement` (`pack_id`, `element_type`, `text?`, `concept_id?`, `block_id?`, `section_label?`, `state` default `suggested`). Enums `PackStatus{generating·ready}`, `PackBlockType{prose·figure·callout·quote}`, `PackElementType{key_term·person_org·claim·counter_view·connection}`, `PackElementState{suggested·kept·dismissed}`.

- [ ] **Step 1: Write the failing test**

Create `services/shared/tests/test_pack_models.py`:

```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from gulp_shared.db import Base
import gulp_shared.models  # noqa: F401  (registers tables)
from gulp_shared.models.concept import Concept, ConceptType
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
from gulp_shared.models.source import Source, SnapshotStatus, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_pack_report_with_block_and_facet_annotation():
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="Example",
        status=SnapshotStatus.ready,
    )
    s.add(snap)
    s.flush()

    pack = KnowledgePack(
        snapshot_id=snap.id, summary="It says X.", confidence=0.8, status=PackStatus.ready
    )
    s.add(pack)
    s.flush()
    section = PackSection(pack_id=pack.id, heading="Overview", position=0)
    s.add(section)
    s.flush()
    block = PackBlock(
        section_id=section.id,
        block_type=PackBlockType.prose,
        content="Rewritten prose.",
        source_anchor={"kind": "char_range", "start": 0, "end": 42},
        anchor_id="b1",
        position=0,
    )
    s.add(block)
    concept = Concept(concept_type=ConceptType.term, name="X")
    s.add(concept)
    s.flush()
    s.add(
        PackElement(
            pack_id=pack.id,
            element_type=PackElementType.key_term,
            text="X — a thing",
            concept_id=concept.id,
            block_id=block.id,
        )
    )
    s.commit()

    got = s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id))
    assert got is not None and got.confidence == 0.8
    blk = s.scalar(select(PackBlock).where(PackBlock.anchor_id == "b1"))
    assert blk.source_anchor == {"kind": "char_range", "start": 0, "end": 42}
    el = s.scalar(select(PackElement))
    assert el.state == PackElementState.suggested  # default
    assert el.block_id == blk.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/shared && uv run pytest tests/test_pack_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gulp_shared.models.knowledge_pack'`

- [ ] **Step 3: Write the model**

Create `services/shared/gulp_shared/models/knowledge_pack.py`:

```python
"""KnowledgePack — readable report + facet-annotations (docs/02 §4.4, S2 design §3)."""

import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class PackStatus(str, enum.Enum):
    generating = "generating"
    ready = "ready"


class PackBlockType(str, enum.Enum):
    prose = "prose"
    figure = "figure"
    callout = "callout"
    quote = "quote"


class PackElementType(str, enum.Enum):
    key_term = "key_term"
    person_org = "person_org"
    claim = "claim"
    counter_view = "counter_view"
    connection = "connection"


class PackElementState(str, enum.Enum):
    suggested = "suggested"
    kept = "kept"
    dismissed = "dismissed"


class KnowledgePack(TimestampedBase, Base):
    __tablename__ = "knowledge_packs"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id"), unique=True, index=True
    )
    summary: Mapped[str] = mapped_column(Text)
    background: Mapped[str | None] = mapped_column(Text, default=None)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
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
    content: Mapped[str | None] = mapped_column(Text, default=None)
    content_ref: Mapped[str | None] = mapped_column(String, default=None)
    source_anchor: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    anchor_id: Mapped[str] = mapped_column(String, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class PackElement(TimestampedBase, Base):
    __tablename__ = "pack_elements"

    pack_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_packs.id"), index=True)
    element_type: Mapped[PackElementType] = mapped_column(
        Enum(PackElementType, name="pack_element_type")
    )
    text: Mapped[str | None] = mapped_column(Text, default=None)
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("concepts.id"), default=None, index=True
    )
    block_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pack_blocks.id"), default=None
    )
    section_label: Mapped[str | None] = mapped_column(String, default=None)
    state: Mapped[PackElementState] = mapped_column(
        Enum(PackElementState, name="pack_element_state"),
        default=PackElementState.suggested,
    )
```

- [ ] **Step 4: Register in `models/__init__.py`**

Add the import:

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

Add to `__all__`: `"KnowledgePack", "PackStatus", "PackSection", "PackBlock", "PackBlockType", "PackElement", "PackElementType", "PackElementState",`

- [ ] **Step 5: Run test to verify it passes**

Run: `cd services/shared && uv run pytest tests/test_pack_models.py -v`
Expected: PASS

- [ ] **Step 6: Lint + commit**

```bash
just lint
git add services/shared/gulp_shared/models/knowledge_pack.py services/shared/gulp_shared/models/__init__.py services/shared/tests/test_pack_models.py
git commit -m "feat(s2): add KnowledgePack report + facet models"
```

---

### Task 4: Add `unprocessed` snapshot status

**Files:**
- Modify: `services/shared/gulp_shared/models/source.py:18-24` (the `SnapshotStatus` enum) and `:69` (the deferred comment)
- Test: `services/shared/tests/test_models.py` (add one test)

**Interfaces:**
- Consumes: existing `SnapshotStatus`.
- Produces: `SnapshotStatus.unprocessed` (the v1 capture-lands state, S2 design §2.4/§7.4).

- [ ] **Step 1: Write the failing test**

Add to `services/shared/tests/test_models.py` (it already imports `SnapshotStatus`, `Source`, `SourceKind`, `User`, `DEV_USER_ID` and has `_session()`):

```python
def test_snapshot_can_be_unprocessed():
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="Example",
        status=SnapshotStatus.unprocessed,
    )
    s.add(snap)
    s.commit()
    assert SnapshotStatus.unprocessed.value == "unprocessed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/shared && uv run pytest tests/test_models.py::test_snapshot_can_be_unprocessed -v`
Expected: FAIL — `AttributeError: unprocessed`

- [ ] **Step 3: Add the enum value + update the comment**

Edit `services/shared/gulp_shared/models/source.py`. In `SnapshotStatus`, add `unprocessed` right after `queued`:

```python
class SnapshotStatus(str, enum.Enum):
    queued = "queued"
    unprocessed = "unprocessed"
    processing = "processing"
    ready = "ready"
    awaiting_review = "awaiting_review"
    in_library = "in_library"
    needs_attention = "needs_attention"
```

Replace the deferred comment on the last line with:

```python
    # 1–1 KnowledgePack is modeled from KnowledgePack.snapshot_id (S2). Deferred: emitted_by (S7).
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/shared && uv run pytest tests/test_models.py -v`
Expected: PASS (all, including the new test)

- [ ] **Step 5: Lint + commit**

```bash
just lint
git add services/shared/gulp_shared/models/source.py services/shared/tests/test_models.py
git commit -m "feat(s2): add 'unprocessed' snapshot status"
```

---

### Task 5: Alembic migration

**Files:**
- Create (via generator): `services/api/alembic/versions/<rev>_s2_knowledge_pack.py`

**Interfaces:**
- Consumes: all models from Tasks 1–4 (registered in `__init__.py`, picked up by `alembic/env.py`'s `import gulp_shared.models`).
- Produces: a migration with `down_revision = '00371ef138ba'` creating `knowledge_packs`, `pack_sections`, `pack_blocks`, `pack_elements`, `cards`, `concepts`, `concept_edges`, `card_concepts`, `source_concepts` (+ their enums), and adding `unprocessed` to `snapshot_status`.

- [ ] **Step 1: Bring up infra and autogenerate**

```bash
just up
just migrate "s2 knowledge pack"
```

Expected: a new file `services/api/alembic/versions/<rev>_s2_knowledge_pack.py` with `create_table(...)` for the nine new tables and `sa.Enum(...)` for the new enums.

- [ ] **Step 2: Verify and hand-adjust the generated migration**

Open the new file and confirm/fix:
- `down_revision = '00371ef138ba'`.
- All nine `create_table` calls are present and ordered so FK targets precede dependents (`concepts`, `cards`, `knowledge_packs` before `pack_elements`, `card_concepts`, etc.). Alembic usually orders correctly; reorder if a FK references a not-yet-created table.
- **Add the enum value** at the very top of `upgrade()` (autogenerate does NOT detect enum-value additions):

```python
    op.execute("ALTER TYPE snapshot_status ADD VALUE IF NOT EXISTS 'unprocessed'")
```

- In `downgrade()`, drop the nine tables (autogenerated). Add a comment noting the enum value is **not** removed (PostgreSQL cannot `DROP VALUE`; harmless to leave):

```python
    # Note: 'unprocessed' is left on snapshot_status — PostgreSQL has no DROP VALUE.
```

- [ ] **Step 3: Apply the migration**

```bash
just migrate-up
```

Expected: `Running upgrade 00371ef138ba -> <rev>, s2 knowledge pack` with no errors.

- [ ] **Step 4: Verify the schema landed**

```bash
docker compose -f infra/docker-compose.yml exec -T postgres psql -U gulp -d gulp -c "\dt" -c "\dT"
```

Expected: the nine new tables listed under `\dt`; the new enum types (`pack_status`, `pack_block_type`, `pack_element_type`, `pack_element_state`, `card_type`, `card_origin`, `card_status`, `concept_type`, `concept_relation`) under `\dT`.

- [ ] **Step 5: Run the full test + lint gates**

```bash
just test
just lint
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add services/api/alembic/versions/
git commit -m "feat(s2): migration for knowledge pack, cards, concepts + unprocessed status"
```

---

## Self-Review

**Spec coverage** (against `docs/subsystems/S2-processing-design.md §7.1–7.2`):
- New models `KnowledgePack`/`PackSection`/`PackBlock`/`PackElement` → Task 3 ✓; `Card` → Task 1 ✓; `Concept`/`ConceptEdge`/`CardConcept`/`SourceConcept` → Task 2 ✓.
- 1–1 modeled from `KnowledgePack.snapshot_id` (no double FK) → Task 3 + Task 4 comment ✓.
- `Card.explanation` (amendment 6) → Task 1 ✓. `unprocessed` status (amendment 5) → Task 4 ✓.
- Report = child tables; `options`/`aliases`/`source_anchor` = JSON → Tasks 1–3 ✓.
- Migration `down_revision='00371ef138ba'` + enum ADD VALUE → Task 5 ✓.
- **Deferred (correctly out of this plan):** `scheduling`/`mastery` (S5), the `pack_block` conversation anchor + intra-pack anchor model (S6, lands when S6 builds), `Source` reading-UI, the pipeline that *writes* these rows (Plan 3). The `anchor_id` column that S6 will reference is included now.

**Placeholder scan:** none — every step has concrete code/commands.

**Type consistency:** enum/class/column names are identical across the model files, the `__init__.py` exports, the tests, and the §7 of the design doc (`KnowledgePack`, `PackSection`, `PackBlock`, `PackElement`, `PackStatus`, `PackBlockType`, `PackElementType`, `PackElementState`, `Card`, `CardType`, `CardOrigin`, `CardStatus`, `Concept`, `ConceptType`, `ConceptEdge`, `ConceptRelation`, `CardConcept`, `SourceConcept`, `SnapshotStatus.unprocessed`). FK target tables (`sources`, `cards`, `concepts`, `knowledge_packs`, `pack_sections`, `pack_blocks`) all exist by the task that references them.
