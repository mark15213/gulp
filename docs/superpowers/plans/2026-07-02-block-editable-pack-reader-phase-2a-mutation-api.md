# Block-Editable Pack Reader — Phase 2a: Block Mutation API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add owner-scoped REST endpoints to edit, insert, delete, and reorder pack blocks, plus the generated `@gulp/api-client` helpers — the contract layer the Phase 2b editing UI consumes.

**Architecture:** Thin routes on the existing pack router do the snapshot-ownership check (mirroring `GET .../pack`), then delegate to `services/api/app/services/pack.py`, which loads the block/section scoped to that snapshot, mutates rows, keeps `position` dense within a section, and commits. Blocks are soft-deleted (`deleted_at`). Write bodies are a discriminated union on `type` (no `id`), reusing the five existing block shapes. No DB migration — the schema already supports all of this.

**Tech Stack:** FastAPI + Pydantic v2 (discriminated unions) + SQLAlchemy (`services/api`, `services/shared`); OpenAPI-generated `@gulp/api-client` (openapi-fetch); pytest.

## Global Constraints

- **The data model is the contract** (`docs/04 §2.5`): Python `app/schemas` is the source of truth. After changing schemas, run `just gen-client` and commit the regenerated client.
- **API layering** (`services/api/CLAUDE.md`): routers thin (parse/validate/authorize → call service → return); business logic in `app/services`; persistence via `gulp_shared` models. Services may raise `LookupError` for not-found; the router translates to HTTP 404.
- **Ownership:** every endpoint authorizes the snapshot owner exactly like `services/api/app/routers/pack.py:24-26` — `source = db.get(Source, snapshot_id); if source is None or source.owner_id != user.id or source.deleted_at is not None: raise HTTPException(404)`.
- **Soft delete:** deletion sets `deleted_at = datetime.now(UTC)`; all reads already filter `deleted_at.is_(None)`. Never hard-delete rows.
- **Ordering:** block order within a section is derived by sorting on `position`; after any structural change the service renumbers the section's live blocks to a dense `0..n-1`. Reorder is **within a section only** (cross-section moves are out of scope).
- **Block `type` is fixed on a block** in v1: editing replaces a block's content/type in place via the write union, but the Phase 2b UI edits within a type. Section-heading editing is **out of scope for 2a** (deferred).
- **No new dependencies.** Code/comments in English only.

**Environment (carry into every task):**
- Run API tests from inside the package: `cd services/api && uv run pytest tests/<file> -v` (repo-root `uv run pytest` collides on the api-vs-worker `app` namespace). See [[api-tests-per-package]].
- `just gen-client` runs from repo root.
- The working tree has PRE-EXISTING unrelated uncommitted changes under `services/shared` and `services/worker` (plus an untracked `.zip` and a worker migration). Stage ONLY each task's exact files (`git add <paths>` — never `git add .`/`-A`); do not touch the pre-existing changes.
- Test auth: in tests `get_current_user` resolves to `DEV_USER_ID` (see `services/api/tests/test_pack_router.py`); create owned rows with `owner_id=DEV_USER_ID`.

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `services/api/app/schemas/pack.py` | read + **write** DTOs | add the `BlockWrite` discriminated union (no id), `BlockUpdate`, `BlockCreate` |
| `services/api/app/services/pack.py` | pack read + **mutation** logic | add `block_dict` (extracted), scoped loaders, `_renumber`, `update_block`, `create_block`, `delete_block` |
| `services/api/app/routers/pack.py` | thin HTTP surface | add PATCH / POST / DELETE routes |
| `services/api/tests/test_pack_mutations.py` | endpoint tests | new file |
| `packages/api-client/openapi.json`, `src/schema.gen.ts`, `src/index.ts` | TS contract + helpers | regenerate + add `updateBlock`/`createBlock`/`deleteBlock` |

---

### Task 1: Write DTOs + extract the block serializer & ordering helpers

**Files:**
- Modify: `services/api/app/schemas/pack.py`
- Modify: `services/api/app/services/pack.py`
- Test: `services/api/tests/test_pack_mutations.py` (create)

**Interfaces:**
- Produces (schemas): `BlockWrite = Annotated[ProseWrite | FormulaWrite | TableWrite | FigureWrite | ListWrite, Field(discriminator="type")]`; `BlockUpdate { content: BlockWrite | None = None, position: int | None = None }`; `BlockCreate { content: BlockWrite, position: int }`. Each `*Write` mirrors the matching `*BlockOut` fields **without `id`**.
- Produces (service): `block_dict(b: PackBlock) -> dict` returns `{"id": b.id, "type": b.block_type.value, **(b.data or {})}`; `live_blocks_ordered(db, section_id) -> list[PackBlock]`; `renumber(blocks: list[PackBlock]) -> None` sets `b.position = i`.

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_pack_mutations.py`:

```python
import uuid

import pytest
from fastapi.testclient import TestClient

from app.deps import get_db
from app.main import app
from app.schemas.pack import BlockCreate, BlockUpdate, BlockWriteAdapter
from app.services.pack import block_dict, renumber
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


def _pack_with_blocks(db):  # type: ignore[no-untyped-def]
    """snapshot -> pack -> one section with two prose blocks (b0,b1). Returns ids."""
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready)
    db.add(snap)
    db.flush()
    pack = KnowledgePack(snapshot_id=snap.id, title="T", key_insight="ki",
                         core_contributions=[], references=[], status=PackStatus.ready)
    db.add(pack)
    db.flush()
    sec = PackSection(pack_id=pack.id, heading="H", position=0)
    db.add(sec)
    db.flush()
    b0 = PackBlock(section_id=sec.id, block_type=PackBlockType.prose, data={"content": "b0"}, position=0)
    b1 = PackBlock(section_id=sec.id, block_type=PackBlockType.prose, data={"content": "b1"}, position=1)
    db.add_all([b0, b1])
    db.commit()
    return {"snap": snap.id, "sec": sec.id, "b0": b0.id, "b1": b1.id}


def test_block_dict_shape(db) -> None:  # type: ignore[no-untyped-def]
    b = PackBlock(section_id=uuid.uuid4(), block_type=PackBlockType.prose,
                  data={"content": "x"}, position=0)
    b.id = uuid.uuid4()
    d = block_dict(b)
    assert d == {"id": b.id, "type": "prose", "content": "x"}


def test_renumber_makes_positions_dense() -> None:
    blocks = [
        PackBlock(section_id=uuid.uuid4(), block_type=PackBlockType.prose, data={}, position=5),
        PackBlock(section_id=uuid.uuid4(), block_type=PackBlockType.prose, data={}, position=9),
        PackBlock(section_id=uuid.uuid4(), block_type=PackBlockType.prose, data={}, position=2),
    ]
    renumber(blocks)
    assert [b.position for b in blocks] == [0, 1, 2]


def test_write_union_discriminates_and_drops_type() -> None:
    w = BlockWriteAdapter.validate_python({"type": "table", "headers": ["a"], "rows": [["1"]]})
    assert w.type == "table"
    assert w.model_dump(exclude={"type"}) == {"headers": ["a"], "rows": [["1"]], "caption": None}


def test_block_update_and_create_optional_fields() -> None:
    u = BlockUpdate(position=3)
    assert u.content is None and u.position == 3
    c = BlockCreate(content={"type": "prose", "content": "hi"}, position=0)
    assert c.content.type == "prose" and c.position == 0
```

Note: `BlockWrite` is an `Annotated[...]` union (not a class), so it is validated through a module-level `BlockWriteAdapter = TypeAdapter(BlockWrite)` defined in the schema module (Step 3) — that is what the test imports and calls.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_pack_mutations.py -v`
Expected: FAIL at import (`cannot import name 'BlockCreate'` / `'BlockWriteAdapter'` / `'block_dict'` / `'renumber'`).

- [ ] **Step 3: Add the write DTOs**

Append to `services/api/app/schemas/pack.py` (after `ListBlockOut`; `TypeAdapter` is a new import from `pydantic`):

```python
class ProseWrite(BaseModel):
    type: Literal["prose"] = "prose"
    content: str


class FormulaWrite(BaseModel):
    type: Literal["formula"] = "formula"
    latex: str
    explanation: str


class TableWrite(BaseModel):
    type: Literal["table"] = "table"
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None


class FigureWrite(BaseModel):
    type: Literal["figure"] = "figure"
    label: str
    explanation: str


class ListWrite(BaseModel):
    type: Literal["list"] = "list"
    items: list[str]
    ordered: bool = False


BlockWrite = Annotated[
    ProseWrite | FormulaWrite | TableWrite | FigureWrite | ListWrite,
    Field(discriminator="type"),
]
BlockWriteAdapter: TypeAdapter[BlockWrite] = TypeAdapter(BlockWrite)


class BlockUpdate(BaseModel):
    content: BlockWrite | None = None
    position: int | None = None


class BlockCreate(BaseModel):
    content: BlockWrite
    position: int
```

Update the import line `from pydantic import BaseModel, Field` → `from pydantic import BaseModel, Field, TypeAdapter`.

- [ ] **Step 4: Extract `block_dict` + ordering helpers in the service**

In `services/api/app/services/pack.py`, add `from typing import Any` to the imports, add these helpers (top-level, after imports), and use `block_dict` inside `pack_out`:

```python
def block_dict(b: PackBlock) -> dict[str, Any]:
    return {"id": b.id, "type": b.block_type.value, **(b.data or {})}


def live_blocks_ordered(db: Session, section_id: uuid.UUID) -> list[PackBlock]:
    return list(
        db.scalars(
            select(PackBlock)
            .where(PackBlock.section_id == section_id, PackBlock.deleted_at.is_(None))
            .order_by(PackBlock.position)
        )
    )


def renumber(blocks: list[PackBlock]) -> None:
    for i, b in enumerate(blocks):
        b.position = i
```

Then in `pack_out`, replace the inline block comprehension with:

```python
        blocks = [block_dict(b) for b in live_blocks_ordered(db, section.id)]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd services/api && uv run pytest tests/test_pack_mutations.py tests/test_pack_router.py -v`
Expected: PASS (new unit tests + the existing pack-router tests still green after the `pack_out` refactor).

- [ ] **Step 6: Commit**

```bash
git add services/api/app/schemas/pack.py services/api/app/services/pack.py \
        services/api/tests/test_pack_mutations.py
git commit -m "feat(api): block write DTOs + extract block_dict/renumber helpers"
```

---

### Task 2: DELETE block (soft-delete + renumber)

**Files:**
- Modify: `services/api/app/services/pack.py`
- Modify: `services/api/app/routers/pack.py`
- Test: `services/api/tests/test_pack_mutations.py`

**Interfaces:**
- Consumes: `block_dict`, `live_blocks_ordered`, `renumber` (Task 1); the ownership pattern from `routers/pack.py`.
- Produces (service): `load_block_scoped(db, snapshot_id, block_id) -> PackBlock` raises `LookupError` if the live block isn't under that snapshot's pack; `delete_block(db, snapshot_id, block_id) -> None` soft-deletes and renumbers the section.
- Produces (route): `DELETE /snapshots/{snapshot_id}/blocks/{block_id}` → `204 No Content`; `404` if snapshot not owned or block not found.

- [ ] **Step 1: Write the failing test**

Add to `services/api/tests/test_pack_mutations.py`:

```python
def test_delete_block_soft_deletes_and_renumbers(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.delete(f"/snapshots/{ids['snap']}/blocks/{ids['b0']}")
    assert r.status_code == 204
    # gone from the read contract, and the survivor is renumbered to position 0
    body = client.get(f"/snapshots/{ids['snap']}/pack").json()
    blocks = body["sections"][0]["blocks"]
    assert [b["id"] for b in blocks] == [str(ids["b1"])]


def test_delete_block_404_for_foreign_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    foreign = Source(owner_id=uuid.uuid4(), kind=SourceKind.snapshot, title="F",
                     status=SnapshotStatus.ready)
    db.add(foreign)
    db.commit()
    r = client.delete(f"/snapshots/{foreign.id}/blocks/{uuid.uuid4()}")
    assert r.status_code == 404


def test_delete_block_404_when_block_not_in_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.delete(f"/snapshots/{ids['snap']}/blocks/{uuid.uuid4()}")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_pack_mutations.py::test_delete_block_soft_deletes_and_renumbers -v`
Expected: FAIL (route not defined → 404/405, or `delete_block` import error).

- [ ] **Step 3: Add the scoped loader + `delete_block` service**

In `services/api/app/services/pack.py`, add (and add `from datetime import UTC, datetime` to imports):

```python
def load_block_scoped(db: Session, snapshot_id: uuid.UUID, block_id: uuid.UUID) -> PackBlock:
    """Load a live block that belongs to the given snapshot's pack, or raise LookupError."""
    block = db.scalar(
        select(PackBlock)
        .join(PackSection, PackBlock.section_id == PackSection.id)
        .join(KnowledgePack, PackSection.pack_id == KnowledgePack.id)
        .where(
            PackBlock.id == block_id,
            PackBlock.deleted_at.is_(None),
            PackSection.deleted_at.is_(None),
            KnowledgePack.deleted_at.is_(None),
            KnowledgePack.snapshot_id == snapshot_id,
        )
    )
    if block is None:
        raise LookupError("block not found")
    return block


def delete_block(db: Session, snapshot_id: uuid.UUID, block_id: uuid.UUID) -> None:
    block = load_block_scoped(db, snapshot_id, block_id)
    section_id = block.section_id
    block.deleted_at = datetime.now(UTC)
    db.flush()
    renumber(live_blocks_ordered(db, section_id))
    db.commit()
```

- [ ] **Step 4: Add the DELETE route**

In `services/api/app/routers/pack.py`, add imports and the route. Extend imports (add `from typing import Any` for the later route return types):

```python
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from app.schemas.pack import BlockOut, BlockCreate, BlockUpdate, PackOut
from app.services.pack import create_block, delete_block, pack_out, update_block
```

Add a small ownership helper and the route (below `get_pack`):

```python
def _owned_snapshot(db: Session, snapshot_id: uuid.UUID, user: User) -> Source:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return source


@router.delete("/snapshots/{snapshot_id}/blocks/{block_id}", status_code=204)
def delete_block_route(
    snapshot_id: uuid.UUID,
    block_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    _owned_snapshot(db, snapshot_id, user)
    try:
        delete_block(db, snapshot_id, block_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="block not found")
    return Response(status_code=204)
```

Refactor `get_pack` to reuse `_owned_snapshot` (replace its inline check with `_owned_snapshot(db, snapshot_id, user)`).

Note: `create_block`/`update_block` are imported now but defined in Tasks 3–4. Implement the DELETE route + `delete_block` in this task; the extra imports will resolve once Tasks 3–4 land. To keep this task's tests green in isolation, add `create_block`/`update_block` as `raise NotImplementedError` stubs in the service now, replaced in Tasks 3–4. (Stub bodies: `def update_block(*a, **k): raise NotImplementedError` / `def create_block(*a, **k): raise NotImplementedError`, with real signatures filled in the later tasks.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd services/api && uv run pytest tests/test_pack_mutations.py tests/test_pack_router.py -v`
Expected: PASS (delete tests + all prior).

- [ ] **Step 6: Commit**

```bash
git add services/api/app/services/pack.py services/api/app/routers/pack.py \
        services/api/tests/test_pack_mutations.py
git commit -m "feat(api): DELETE block endpoint (soft-delete + renumber)"
```

---

### Task 3: PATCH block (edit content and/or reorder)

**Files:**
- Modify: `services/api/app/services/pack.py`
- Modify: `services/api/app/routers/pack.py`
- Test: `services/api/tests/test_pack_mutations.py`

**Interfaces:**
- Consumes: `load_block_scoped`, `live_blocks_ordered`, `renumber`, `block_dict` (Tasks 1–2); `BlockUpdate` (Task 1).
- Produces (service): `update_block(db, snapshot_id, block_id, update: BlockUpdate) -> dict` — applies content (replaces `block_type` + `data`) and/or moves the block to `position` within its section, then returns `block_dict`.
- Produces (route): `PATCH /snapshots/{snapshot_id}/blocks/{block_id}` body `BlockUpdate` → `BlockOut`; `404` if not owned / not found.

- [ ] **Step 1: Write the failing test**

Add to `services/api/tests/test_pack_mutations.py`:

```python
def test_update_block_content(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.patch(
        f"/snapshots/{ids['snap']}/blocks/{ids['b0']}",
        json={"content": {"type": "prose", "content": "edited"}},
    )
    assert r.status_code == 200
    assert r.json() == {"id": str(ids["b0"]), "type": "prose", "content": "edited"}
    body = client.get(f"/snapshots/{ids['snap']}/pack").json()
    assert body["sections"][0]["blocks"][0]["content"] == "edited"


def test_update_block_changes_type(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.patch(
        f"/snapshots/{ids['snap']}/blocks/{ids['b0']}",
        json={"content": {"type": "list", "items": ["x", "y"], "ordered": True}},
    )
    assert r.status_code == 200
    assert r.json() == {"id": str(ids["b0"]), "type": "list", "items": ["x", "y"], "ordered": True}


def test_update_block_position_reorders(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)  # b0@0, b1@1
    r = client.patch(f"/snapshots/{ids['snap']}/blocks/{ids['b0']}", json={"position": 1})
    assert r.status_code == 200
    body = client.get(f"/snapshots/{ids['snap']}/pack").json()
    assert [b["id"] for b in body["sections"][0]["blocks"]] == [str(ids["b1"]), str(ids["b0"])]


def test_update_block_404_when_not_in_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.patch(f"/snapshots/{ids['snap']}/blocks/{uuid.uuid4()}", json={"position": 0})
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_pack_mutations.py::test_update_block_content -v`
Expected: FAIL (`update_block` is the NotImplementedError stub → 500, or route missing → 405).

- [ ] **Step 3: Implement `update_block` (replace the stub)**

In `services/api/app/services/pack.py`, replace the `update_block` stub with the following. First extend the two existing import lines: `from app.schemas.pack import PackOut, PackReferenceOut, PackSectionOut` → add `BlockUpdate`; and `from gulp_shared.models.knowledge_pack import KnowledgePack, PackBlock, PackSection` → add `PackBlockType` (shown below).

```python
def update_block(
    db: Session, snapshot_id: uuid.UUID, block_id: uuid.UUID, update: BlockUpdate
) -> dict[str, Any]:
    block = load_block_scoped(db, snapshot_id, block_id)
    if update.content is not None:
        block.block_type = PackBlockType(update.content.type)
        block.data = update.content.model_dump(exclude={"type"})
    if update.position is not None:
        others = [b for b in live_blocks_ordered(db, block.section_id) if b.id != block.id]
        pos = max(0, min(update.position, len(others)))
        others.insert(pos, block)
        renumber(others)
    db.commit()
    db.refresh(block)
    return block_dict(block)
```

Extend the model import in `services/api/app/services/pack.py`:
`from gulp_shared.models.knowledge_pack import KnowledgePack, PackBlock, PackBlockType, PackSection`

- [ ] **Step 4: Add the PATCH route**

In `services/api/app/routers/pack.py`, add (imports for `BlockOut`/`BlockUpdate`/`update_block` were added in Task 2):

```python
@router.patch("/snapshots/{snapshot_id}/blocks/{block_id}", response_model=BlockOut)
def update_block_route(
    snapshot_id: uuid.UUID,
    block_id: uuid.UUID,
    update: BlockUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _owned_snapshot(db, snapshot_id, user)
    try:
        return update_block(db, snapshot_id, block_id, update)
    except LookupError:
        raise HTTPException(status_code=404, detail="block not found")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd services/api && uv run pytest tests/test_pack_mutations.py -v`
Expected: PASS (all update tests + prior).

- [ ] **Step 6: Commit**

```bash
git add services/api/app/services/pack.py services/api/app/routers/pack.py \
        services/api/tests/test_pack_mutations.py
git commit -m "feat(api): PATCH block endpoint (edit content + reorder)"
```

---

### Task 4: POST create block (insert at position)

**Files:**
- Modify: `services/api/app/services/pack.py`
- Modify: `services/api/app/routers/pack.py`
- Test: `services/api/tests/test_pack_mutations.py`

**Interfaces:**
- Consumes: `live_blocks_ordered`, `renumber`, `block_dict` (Task 1); `BlockCreate` (Task 1).
- Produces (service): `load_section_scoped(db, snapshot_id, section_id) -> PackSection` raises `LookupError`; `create_block(db, snapshot_id, section_id, create: BlockCreate) -> dict` inserts a new block at `create.position`, renumbers, returns `block_dict`.
- Produces (route): `POST /snapshots/{snapshot_id}/sections/{section_id}/blocks` body `BlockCreate` → `201` + `BlockOut`.

- [ ] **Step 1: Write the failing test**

Add to `services/api/tests/test_pack_mutations.py`:

```python
def test_create_block_inserts_at_position(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)  # b0@0, b1@1
    r = client.post(
        f"/snapshots/{ids['snap']}/sections/{ids['sec']}/blocks",
        json={"content": {"type": "prose", "content": "mid"}, "position": 1},
    )
    assert r.status_code == 201
    new_id = r.json()["id"]
    assert r.json()["content"] == "mid"
    body = client.get(f"/snapshots/{ids['snap']}/pack").json()
    order = [b["id"] for b in body["sections"][0]["blocks"]]
    assert order == [str(ids["b0"]), new_id, str(ids["b1"])]


def test_create_block_position_clamped_to_end(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.post(
        f"/snapshots/{ids['snap']}/sections/{ids['sec']}/blocks",
        json={"content": {"type": "figure", "label": "F1", "explanation": "e"}, "position": 99},
    )
    assert r.status_code == 201
    body = client.get(f"/snapshots/{ids['snap']}/pack").json()
    assert body["sections"][0]["blocks"][-1]["id"] == r.json()["id"]


def test_create_block_404_when_section_not_in_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.post(
        f"/snapshots/{ids['snap']}/sections/{uuid.uuid4()}/blocks",
        json={"content": {"type": "prose", "content": "x"}, "position": 0},
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_pack_mutations.py::test_create_block_inserts_at_position -v`
Expected: FAIL (`create_block` is the NotImplementedError stub / route missing).

- [ ] **Step 3: Implement `load_section_scoped` + `create_block` (replace the stub)**

In `services/api/app/services/pack.py` (extend the existing `from app.schemas.pack import ...` line to also include `BlockCreate`):

```python
def load_section_scoped(db: Session, snapshot_id: uuid.UUID, section_id: uuid.UUID) -> PackSection:
    section = db.scalar(
        select(PackSection)
        .join(KnowledgePack, PackSection.pack_id == KnowledgePack.id)
        .where(
            PackSection.id == section_id,
            PackSection.deleted_at.is_(None),
            KnowledgePack.deleted_at.is_(None),
            KnowledgePack.snapshot_id == snapshot_id,
        )
    )
    if section is None:
        raise LookupError("section not found")
    return section


def create_block(
    db: Session, snapshot_id: uuid.UUID, section_id: uuid.UUID, create: BlockCreate
) -> dict[str, Any]:
    load_section_scoped(db, snapshot_id, section_id)
    block = PackBlock(
        section_id=section_id,
        block_type=PackBlockType(create.content.type),
        data=create.content.model_dump(exclude={"type"}),
        position=0,
    )
    db.add(block)
    db.flush()
    blocks = [b for b in live_blocks_ordered(db, section_id) if b.id != block.id]
    pos = max(0, min(create.position, len(blocks)))
    blocks.insert(pos, block)
    renumber(blocks)
    db.commit()
    db.refresh(block)
    return block_dict(block)
```

- [ ] **Step 4: Add the POST route**

In `services/api/app/routers/pack.py` (extend the service import with `create_block`; add `status` import if you prefer, but `status_code=201` literal is fine):

```python
@router.post(
    "/snapshots/{snapshot_id}/sections/{section_id}/blocks",
    response_model=BlockOut,
    status_code=201,
)
def create_block_route(
    snapshot_id: uuid.UUID,
    section_id: uuid.UUID,
    create: BlockCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _owned_snapshot(db, snapshot_id, user)
    try:
        return create_block(db, snapshot_id, section_id, create)
    except LookupError:
        raise HTTPException(status_code=404, detail="section not found")
```

- [ ] **Step 5: Run the full mutation + router suites**

Run: `cd services/api && uv run pytest tests/test_pack_mutations.py tests/test_pack_router.py -v`
Expected: PASS (all create/update/delete tests + read tests). Confirm no `NotImplementedError` stubs remain in `services/pack.py`.

- [ ] **Step 6: Commit**

```bash
git add services/api/app/services/pack.py services/api/app/routers/pack.py \
        services/api/tests/test_pack_mutations.py
git commit -m "feat(api): POST create-block endpoint (insert at position)"
```

---

### Task 5: Regenerate the client + typed mutation helpers

**Files:**
- Regenerate: `packages/api-client/openapi.json`, `packages/api-client/src/schema.gen.ts`
- Modify: `packages/api-client/src/index.ts`

**Interfaces:**
- Consumes: the three routes from Tasks 2–4.
- Produces (client): `PackBlockOut` type; `BlockUpdateBody` / `BlockCreateBody` types; `updateBlock(snapshotId, blockId, body: BlockUpdateBody): Promise<PackBlockOut>`; `createBlock(snapshotId, sectionId, body: BlockCreateBody): Promise<PackBlockOut>`; `deleteBlock(snapshotId, blockId): Promise<void>` — the helpers Phase 2b's editing UI calls.

- [ ] **Step 1: Regenerate the client from the new OpenAPI**

Run: `just gen-client`
Expected: `schema.gen.ts` gains `patch`/`delete` on `/snapshots/{snapshot_id}/blocks/{block_id}` and `post` on `/snapshots/{snapshot_id}/sections/{section_id}/blocks`, plus `BlockUpdate`/`BlockCreate`/`*Write` component schemas.

- [ ] **Step 2: Add the typed helpers**

Append to `packages/api-client/src/index.ts` (after `getPack`):

```typescript
export type PackBlockOut = PackOut["sections"][number]["blocks"][number];
export type BlockUpdateBody =
  paths["/snapshots/{snapshot_id}/blocks/{block_id}"]["patch"]["requestBody"]["content"]["application/json"];
export type BlockCreateBody =
  paths["/snapshots/{snapshot_id}/sections/{section_id}/blocks"]["post"]["requestBody"]["content"]["application/json"];

export async function updateBlock(
  snapshotId: string,
  blockId: string,
  body: BlockUpdateBody,
): Promise<PackBlockOut> {
  const { data, error } = await client.PATCH("/snapshots/{snapshot_id}/blocks/{block_id}", {
    params: { path: { snapshot_id: snapshotId, block_id: blockId } },
    body,
  });
  if (error || !data) throw new Error("update block failed");
  return data;
}

export async function createBlock(
  snapshotId: string,
  sectionId: string,
  body: BlockCreateBody,
): Promise<PackBlockOut> {
  const { data, error } = await client.POST(
    "/snapshots/{snapshot_id}/sections/{section_id}/blocks",
    { params: { path: { snapshot_id: snapshotId, section_id: sectionId } }, body },
  );
  if (error || !data) throw new Error("create block failed");
  return data;
}

export async function deleteBlock(snapshotId: string, blockId: string): Promise<void> {
  const { error } = await client.DELETE("/snapshots/{snapshot_id}/blocks/{block_id}", {
    params: { path: { snapshot_id: snapshotId, block_id: blockId } },
  });
  if (error) throw new Error("delete block failed");
}
```

- [ ] **Step 3: Typecheck the client + web consumer**

Run: `pnpm --filter @gulp/web exec tsc --noEmit`
Expected: exit 0 (the new helper types resolve against the regenerated `paths`).

- [ ] **Step 4: Commit**

```bash
git add packages/api-client/openapi.json packages/api-client/src/schema.gen.ts \
        packages/api-client/src/index.ts
git commit -m "feat(api-client): block mutation helpers (update/create/delete)"
```

---

## Self-Review

**Spec coverage (Phase 2a slice of the design spec):**
- `PATCH /snapshots/{sid}/blocks/{bid}` (update data + position) → Task 3. ✔
- `POST /snapshots/{sid}/sections/{secid}/blocks` (insert at position) → Task 4. ✔
- `DELETE /snapshots/{sid}/blocks/{bid}` → Task 2. ✔
- Per-type validation via write union → Task 1 (`BlockWrite` discriminated on `type`). ✔
- Position semantics owned by the service, dense renumber, within-section only → `renumber`/`live_blocks_ordered` (Task 1), applied in Tasks 2–4. ✔
- Ownership on every endpoint mirroring `GET .../pack` → `_owned_snapshot` (Task 2), reused in 3–4. ✔
- Soft-delete via `deleted_at` → Task 2. ✔
- Regenerate client after schema change; typed helpers → Task 5. ✔
- `PATCH .../sections/{secid}` heading edit → **out of scope for 2a** (design marked it optional/stretch); note for a later plan. ✔ (intentional)
- Frontend editing UI (client island, per-type editors, toolbar, add-menu, optimistic updates) → **Phase 2b, separate plan.** ✔

**Placeholder scan:** No TBD/TODO; every code step shows full code and exact commands. The only deferred symbols are the deliberate `NotImplementedError` stubs introduced in Task 2 and replaced in Tasks 3–4 (called out explicitly), so no route references an undefined function at any commit.

**Type consistency:** `BlockWrite`/`BlockUpdate`/`BlockCreate` (Task 1) are the exact request models used by `update_block`/`create_block` (Tasks 3–4) and the routes. `block_dict` returns the `{id,type,**data}` shape validated by the `BlockOut` response_model. `load_block_scoped`/`load_section_scoped` raise `LookupError` → routers translate to 404 consistently. Service functions commit; routers stay thin. Client helper names (`updateBlock`/`createBlock`/`deleteBlock`) are what Phase 2b will import.

## Notes for Phase 2b (frontend editing UI — separate plan)

Consumes this plan's contract: `updateBlock`/`createBlock`/`deleteBlock` + `PackBlockOut`/`BlockUpdateBody`/`BlockCreateBody`. Builds: `PackReport` → client island holding `useState<PackOut>` with optimistic update + rollback + toast; per-type editors (`ProseEditor`/`FormulaEditor`/`TableEditor`/`ListEditor`/`FigureEditor`); `BlockToolbar` (delete via `deleteBlock`, move via `updateBlock({position})`, drag handle); `AddBlockMenu` (`+` insert via `createBlock`). Re-run-replaces-pack confirm prompt on the Start/Retry entry point.
