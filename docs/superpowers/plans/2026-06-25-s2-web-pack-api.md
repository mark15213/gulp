# S2 Web Slice — Plan A: Pack API + Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the generated Knowledge Pack over the API — `GET /snapshots/{id}/pack` returning the report (sections/blocks) + facets — and regenerate `@gulp/api-client` with `getPack` / `startProcessing` helpers, so the web reading page (Plan B) has a typed contract to read.

**Architecture:** A Pydantic `PackOut` contract (`app/schemas/pack.py`), a `pack_out` serializer that reads the `KnowledgePack`/`PackSection`/`PackBlock`/`PackElement` rows (`app/services/pack.py`), and a thin owner-scoped router (`app/routers/pack.py`) returning 404 when there's no pack. Then `just gen-client` regenerates the TS types and two typed helpers are added to the client.

**Tech Stack:** FastAPI, Pydantic 2, SQLAlchemy 2.0 (sync), pytest (SQLite in-memory api `db` fixture), `openapi-typescript` (client gen), TypeScript.

## Global Constraints

- **The data model is the contract** (CLAUDE.md rule 2): TS types are generated via `just gen-client` from the API's OpenAPI — never hand-write types that duplicate the model. The web talks to the backend only through `@gulp/api-client`.
- **Owner-scoped** like the other snapshot routes: 404 on missing / foreign-owned / soft-deleted (`deleted_at`).
- **English** comments/commits (CLAUDE.md rule 6).
- **api files import `gulp_shared` without `# type: ignore`** — when mypy runs from `services/api` it follows the workspace source (unlike the worker). Match the existing `app/services/capture.py` import style.
- **Gate:** `cd services/api && uv run pytest` GREEN; `pnpm --filter @gulp/api-client exec tsc --noEmit` GREEN. Repo-wide ruff/mypy/eslint carry accepted pre-existing debt (not this plan's job).
- **TDD + a commit per task.**

---

## File Structure

- `services/api/app/schemas/pack.py` *(new)* — `PackOut`, `PackSectionOut`, `PackBlockOut`, `PackFacetOut` (the OpenAPI contract; enum-typed for nice TS unions).
- `services/api/app/services/pack.py` *(new)* — `pack_out(db, snapshot_id) -> PackOut | None`.
- `services/api/app/routers/pack.py` *(new)* — `GET /snapshots/{id}/pack`.
- `services/api/app/main.py` *(modify)* — register the pack router.
- `packages/api-client/src/index.ts` *(modify)* — `PackOut` type + `getPack(id)` (null on 404) + `startProcessing(id)` helpers.
- `packages/api-client/{openapi.json,src/schema.gen.ts}` *(regenerated)* — `just gen-client`.
- Tests *(new)*: `services/api/tests/test_pack_service.py`, `services/api/tests/test_pack_router.py`.

Task order: serializer+schemas → endpoint → client regen.

---

### Task 1: `PackOut` schemas + `pack_out` serializer

**Files:**
- Create: `services/api/app/schemas/pack.py`, `services/api/app/services/pack.py`
- Test: `services/api/tests/test_pack_service.py`

**Interfaces:**
- Produces: `PackBlockOut(type: PackBlockType, content: str|None, anchor_id: str)`; `PackSectionOut(heading: str|None, blocks: list[PackBlockOut])`; `PackFacetOut(element_type: PackElementType, text: str|None)`; `PackOut(snapshot_id: uuid.UUID, status: PackStatus, summary: str, background: str|None, confidence: float|None, sections: list[PackSectionOut], facets: list[PackFacetOut])`. `pack_out(db: Session, snapshot_id: uuid.UUID) -> PackOut | None` — `None` when the snapshot has no pack; sections ordered by `position`, blocks ordered by `position`.

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_pack_service.py`:

```python
import uuid

from app.services.pack import pack_out
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackElement,
    PackElementType,
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
        snapshot_id=snapshot_id, summary="sum", background="bg",
        confidence=0.8, status=PackStatus.ready,
    )
    db.add(pack)
    db.flush()
    s0 = PackSection(pack_id=pack.id, heading="Overview", position=0)
    s1 = PackSection(pack_id=pack.id, heading="Details", position=1)
    db.add_all([s0, s1])
    db.flush()
    db.add(PackBlock(section_id=s0.id, block_type=PackBlockType.prose, content="b0",
                     anchor_id="s0b0", position=0))
    db.add(PackBlock(section_id=s0.id, block_type=PackBlockType.quote, content="b1",
                     anchor_id="s0b1", position=1))
    # PackElement.state defaults to `suggested`, so the seed omits it.
    db.add(PackElement(pack_id=pack.id, element_type=PackElementType.key_term, text="attention"))
    db.add(PackElement(pack_id=pack.id, element_type=PackElementType.claim, text="claim-x"))
    db.commit()


def test_pack_out_serializes_ordered_report_and_facets(db) -> None:
    snap = _snapshot(db)
    _seed_pack(db, snap.id)
    out = pack_out(db, snap.id)
    assert out is not None
    assert out.status == PackStatus.ready and out.summary == "sum" and out.confidence == 0.8
    assert [s.heading for s in out.sections] == ["Overview", "Details"]
    assert [b.anchor_id for b in out.sections[0].blocks] == ["s0b0", "s0b1"]
    assert out.sections[0].blocks[0].type == PackBlockType.prose
    assert {f.text for f in out.facets} == {"attention", "claim-x"}
    assert {f.element_type for f in out.facets} == {PackElementType.key_term, PackElementType.claim}


def test_pack_out_returns_none_when_no_pack(db) -> None:
    snap = _snapshot(db)
    db.commit()
    assert pack_out(db, snap.id) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_pack_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.pack'`

- [ ] **Step 3: Write the schemas**

Create `services/api/app/schemas/pack.py`:

```python
"""Pack read contract — these become the OpenAPI types the web client reads."""

import uuid

from pydantic import BaseModel

from gulp_shared.models.knowledge_pack import PackBlockType, PackElementType, PackStatus


class PackBlockOut(BaseModel):
    type: PackBlockType
    content: str | None
    anchor_id: str


class PackSectionOut(BaseModel):
    heading: str | None
    blocks: list[PackBlockOut]


class PackFacetOut(BaseModel):
    element_type: PackElementType
    text: str | None


class PackOut(BaseModel):
    snapshot_id: uuid.UUID
    status: PackStatus
    summary: str
    background: str | None
    confidence: float | None
    sections: list[PackSectionOut]
    facets: list[PackFacetOut]
```

- [ ] **Step 4: Write the serializer**

Create `services/api/app/services/pack.py`:

```python
"""Serialize a snapshot's KnowledgePack into the PackOut contract."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.pack import PackBlockOut, PackFacetOut, PackOut, PackSectionOut
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackElement,
    PackSection,
)


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
        .where(PackSection.pack_id == pack.id)
        .order_by(PackSection.position)
    ):
        blocks = [
            PackBlockOut(type=b.block_type, content=b.content, anchor_id=b.anchor_id)
            for b in db.scalars(
                select(PackBlock)
                .where(PackBlock.section_id == section.id)
                .order_by(PackBlock.position)
            )
        ]
        sections.append(PackSectionOut(heading=section.heading, blocks=blocks))

    facets = [
        PackFacetOut(element_type=e.element_type, text=e.text)
        for e in db.scalars(select(PackElement).where(PackElement.pack_id == pack.id))
    ]

    return PackOut(
        snapshot_id=snapshot_id,
        status=pack.status,
        summary=pack.summary,
        background=pack.background,
        confidence=pack.confidence,
        sections=sections,
        facets=facets,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd services/api && uv run pytest tests/test_pack_service.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add services/api/app/schemas/pack.py services/api/app/services/pack.py services/api/tests/test_pack_service.py
git commit -m "feat(s2): PackOut schema + serializer"
```

---

### Task 2: `GET /snapshots/{id}/pack` endpoint

**Files:**
- Create: `services/api/app/routers/pack.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_pack_router.py`

**Interfaces:**
- Consumes: `pack_out` (Task 1), `get_db`/`get_current_user`, `Source`.
- Produces: `GET /snapshots/{snapshot_id}/pack` → `PackOut`; 404 when the snapshot is missing/foreign/deleted, or has no pack.

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_pack_router.py`:

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
    pack = KnowledgePack(snapshot_id=snap.id, summary="sum", background=None,
                         confidence=0.7, status=PackStatus.ready)
    db.add(pack)
    db.flush()
    sec = PackSection(pack_id=pack.id, heading="H", position=0)
    db.add(sec)
    db.flush()
    db.add(PackBlock(section_id=sec.id, block_type=PackBlockType.prose, content="hello",
                     anchor_id="s0b0", position=0))
    db.commit()
    return snap.id


def test_get_pack_returns_report(client, db) -> None:  # type: ignore[no-untyped-def]
    sid = _ready_snapshot_with_pack(db)
    r = client.get(f"/snapshots/{sid}/pack")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] == "sum"
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_pack_router.py -v`
Expected: FAIL — 404 route not found / `ModuleNotFoundError` for `app.routers.pack`.

- [ ] **Step 3: Write the router**

Create `services/api/app/routers/pack.py`:

```python
"""Pack read endpoint — thin (docs/05 D4)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.pack import PackOut
from app.services.pack import pack_out
from gulp_shared.models.source import Source
from gulp_shared.models.user import User

router = APIRouter()


@router.get("/snapshots/{snapshot_id}/pack", response_model=PackOut)
def get_pack(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PackOut:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    pack = pack_out(db, snapshot_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="no pack for this snapshot")
    return pack
```

- [ ] **Step 4: Register the router**

In `services/api/app/main.py`, add `pack` to the import and `include_router`:

```python
from app.routers import capture, inbox, pack, processing
...
app.include_router(pack.router, tags=["pack"])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd services/api && uv run pytest tests/test_pack_router.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run the full api suite + commit**

```bash
cd services/api && uv run pytest -q && cd ../..
git add services/api/app/routers/pack.py services/api/app/main.py services/api/tests/test_pack_router.py
git commit -m "feat(s2): GET /snapshots/{id}/pack endpoint"
```

---

### Task 3: Regenerate `@gulp/api-client` + helpers

**Files:**
- Regenerate: `packages/api-client/openapi.json`, `packages/api-client/src/schema.gen.ts`
- Modify: `packages/api-client/src/index.ts`

**Interfaces:**
- Produces: `PackOut` type; `getPack(id: string): Promise<PackOut | null>` (null on 404); `startProcessing(id: string): Promise<SnapshotOut>` (POST the existing `/snapshots/{id}/process`).

- [ ] **Step 1: Regenerate the client from the new OpenAPI**

Run: `just gen-client`
Expected: rewrites `packages/api-client/openapi.json` and `packages/api-client/src/schema.gen.ts`. (Requires the api to import cleanly + pnpm.)

- [ ] **Step 2: Verify the new path is in the generated schema**

Run: `grep -c "/snapshots/{snapshot_id}/pack" packages/api-client/src/schema.gen.ts`
Expected: ≥ 1 (the new GET path was generated).

- [ ] **Step 3: Add the typed helpers**

In `packages/api-client/src/index.ts`, add the `PackOut` type (next to the other `export type` lines) and the two helpers (next to `getSnapshot`):

```typescript
export type PackOut =
  paths["/snapshots/{snapshot_id}/pack"]["get"]["responses"]["200"]["content"]["application/json"];

export async function getPack(id: string): Promise<PackOut | null> {
  const { data, error } = await client.GET("/snapshots/{snapshot_id}/pack", {
    params: { path: { snapshot_id: id } },
    cache: "no-store",
  });
  if (error) return null; // 404 = no pack yet (still processing / needs attention)
  return data ?? null;
}

export async function startProcessing(id: string): Promise<SnapshotOut> {
  const { data, error } = await client.POST("/snapshots/{snapshot_id}/process", {
    params: { path: { snapshot_id: id } },
  });
  if (error || !data) throw new Error("start processing failed");
  return data;
}
```

- [ ] **Step 4: Type-check the client against the regenerated schema**

Run: `pnpm --filter @gulp/api-client exec tsc --noEmit`
Expected: no type errors (the helpers resolve against the new `/snapshots/{snapshot_id}/pack` path and the existing `/process` path).

- [ ] **Step 5: Commit**

```bash
git add packages/api-client/openapi.json packages/api-client/src/schema.gen.ts packages/api-client/src/index.ts
git commit -m "feat(s2): regenerate api-client with getPack + startProcessing"
```

---

## Self-Review

**Spec coverage** (against the design spec §2 Plan A):
- `PackOut` contract + serializer → Task 1 ✓ (sections/blocks ordered by position; facets; null when no pack).
- `GET /snapshots/{id}/pack`, owner-scoped, 404 when no pack → Task 2 ✓.
- Regenerate `@gulp/api-client` + `getPack` (null on 404) + `startProcessing` helpers → Task 3 ✓.
- **Deferred (Plan B):** the web reading page + Start UI consume these.

**Placeholder scan:** none — every step carries concrete code/commands. The Task-1 seed omits `PackElement.state` deliberately (it defaults to `suggested`).

**Type consistency:** `pack_out(db, snapshot_id) -> PackOut | None`, `PackOut`/`PackSectionOut`/`PackBlockOut`/`PackFacetOut`, and the enum-typed fields (`PackBlockType`/`PackElementType`/`PackStatus`) are identical across the schema, serializer, router, and tests. The route path `/snapshots/{snapshot_id}/pack` matches the grep in Task 3 and the generated `getPack` helper. `startProcessing` targets the existing `/snapshots/{snapshot_id}/process` route (Plan 3).
