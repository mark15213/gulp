# Library redesign + source tags — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Library a left tag sidebar that groups items by **source feed** (derived) and **user tags**, with a reserved (disabled) **Topics** group for future AI tagging, plus inline add/remove of user tags.

**Architecture:** The **Sources** facet is derived from the existing `Source.emitted_by → subscription.title` link (no new column, no migration). **Mine** reuses the existing `SourceTag` rows exposed as `tags: string[]`. Backend adds one nullable contract field (`source_feed`) and two tag endpoints; the web page becomes a two-pane layout (sidebar + list) with single-select filtering and optimistic tag edits.

**Tech Stack:** FastAPI + SQLAlchemy (`services/api`, `services/shared`), Pydantic schemas → OpenAPI → `packages/api-client` (openapi-typescript), Next.js App Router + CSS Modules (`apps/web`), pytest + vitest/RTL.

## Global Constraints

- **Web-first only** — no `apps/mobile` changes.
- **Talk to the backend only through `@gulp/api-client`** — never hand-write fetch types (`apps/web/CLAUDE.md`).
- **API is the contract source of truth** — after changing `app/schemas`, run `just gen-client` (`services/api/CLAUDE.md`).
- **API routers stay thin** — parse/validate → call a service → return; business logic in `app/services` (`services/api/CLAUDE.md`).
- **Visual primitives from `@gulp/ui`** — use existing tokens (`--border`, `--surface`, `--blue-50`, `--blue-700`, `--text-muted`, `--measure`); don't redefine them.
- **vitest uses the classic JSX transform** — every file containing JSX (components **and** tests) must `import React`; JSX-free `.ts` files must **not**.
- **Run tests per-package** — `cd services/api && uv run pytest ...`; web via `pnpm --filter @gulp/web test`.
- **No AI/topic tagging logic, no `origin` column, no DB migration** this spec — Topics is a disabled placeholder only.
- **Single-select** filtering only (no multi-select/AND).
- **`just lint` must be green** before the final commit; `just gen-client` regenerates `schema.gen.ts` (ignore its 2 pre-existing dup-identifier `tsc` warnings — unrelated).

---

## File Structure

**Backend (create):** none.
**Backend (modify):**
- `services/api/app/schemas/capture.py` — add `SourceFeedOut`, `TagCreate`; add `source_feed` to `SnapshotOut`.
- `services/api/app/services/snapshots.py` — `_source_feed()`, extend `to_out()`, add `add_tag()`/`remove_tag()`.
- `services/api/app/services/library.py` — add `feed_titles_for()`.
- `services/api/app/routers/library.py` — batch feed titles into `to_out`.
- `services/api/app/routers/capture.py` — `_owned_snapshot()` helper + `POST`/`DELETE /snapshots/{id}/tags`.

**Backend (test):**
- `services/api/tests/test_library.py` — extend (source_feed).
- `services/api/tests/test_snapshot_tags.py` — create.

**Contract:**
- `packages/api-client/src/index.ts` — add `addSnapshotTag`, `removeSnapshotTag` (regenerate `schema.gen.ts` first).

**Web (create):**
- `apps/web/lib/libraryFacets.ts` (+ `libraryFacets.test.ts`)
- `apps/web/components/library/LibraryTagSidebar.tsx` (+ `.module.css`, `.test.tsx`)
- `apps/web/components/library/RowTags.tsx` (+ `.module.css`, `.test.tsx`)

**Web (modify):**
- `apps/web/components/library/LibraryList.tsx` — two-pane, state, facets.
- `apps/web/components/library/LibraryList.module.css` — `.layout`, `.listCol`.
- `apps/web/components/library/LibraryList.test.tsx` — sidebar-based filter tests.
- `apps/web/app/library/page.module.css` — widen page.

**Docs:** `docs/01-interaction-spec.md §F3`, `docs/03-ui-system.md §7.3`, `docs/02-data-model.md §4.3`.

---

## Task 1: Backend — expose `source_feed` on the Library contract

**Files:**
- Modify: `services/api/app/schemas/capture.py`
- Modify: `services/api/app/services/snapshots.py`
- Modify: `services/api/app/services/library.py`
- Modify: `services/api/app/routers/library.py`
- Test: `services/api/tests/test_library.py`

**Interfaces:**
- Produces: `SourceFeedOut(id: uuid.UUID, title: str)`; `SnapshotOut.source_feed: SourceFeedOut | None`; `to_out(db, source, feed_titles: dict[uuid.UUID, str] | None = None) -> SnapshotOut`; `feed_titles_for(db, sources: list[Source]) -> dict[uuid.UUID, str]`.

- [ ] **Step 1: Write the failing test** — append to `services/api/tests/test_library.py`:

```python
def _subscription(db, title: str):  # type: ignore[no-untyped-def]
    sub = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.subscription,
        title=title,
        status=SnapshotStatus.ready,  # constant for subscriptions; health is derived
    )
    db.add(sub)
    db.flush()
    return sub


def test_library_item_carries_source_feed(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    sub = _subscription(db, "HuggingFace Paper Daily")
    from_feed = _ready(db, "https://hf.co/papers/1")
    from_feed.emitted_by = sub.id
    db.commit()
    plain = _ready(db, "https://blog.example/1")

    items = {i["id"]: i for i in client.get("/library").json()["items"]}
    assert items[str(from_feed.id)]["source_feed"] == {
        "id": str(sub.id),
        "title": "HuggingFace Paper Daily",
    }
    assert items[str(plain.id)]["source_feed"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_library.py::test_library_item_carries_source_feed -v`
Expected: FAIL — `KeyError: 'source_feed'` (field not in the response yet).

- [ ] **Step 3: Add the schemas** — in `services/api/app/schemas/capture.py`, add `SourceFeedOut` above `SnapshotOut` and the `source_feed` field:

```python
class SourceFeedOut(BaseModel):
    """The subscription feed that produced a snapshot (derived from
    Source.emitted_by); null for ad-hoc captures."""

    id: uuid.UUID
    title: str


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: SourceKind
    title: str
    note: str | None
    status: SnapshotStatus
    media_type: MediaType | None
    genre: SourceGenre | None
    origin_url: str | None
    content_body: str | None
    captured_via: CapturedVia | None
    cards_status: CardsStatus | None
    tags: list[str]
    source_feed: SourceFeedOut | None = None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Populate it in `to_out`** — in `services/api/app/services/snapshots.py`, update the import and add `_source_feed`, extend `to_out`:

```python
from app.schemas.capture import SnapshotOut, SnapshotPatch, SourceFeedOut
```

```python
def _source_feed(
    db: Session,
    source: Source,
    feed_titles: dict[uuid.UUID, str] | None = None,
) -> SourceFeedOut | None:
    """The subscription that emitted this snapshot. Batch callers pass
    `feed_titles` (id -> title) to avoid an N+1; single-item callers fall back
    to a PK lookup."""
    if source.emitted_by is None:
        return None
    if feed_titles is not None:
        title = feed_titles.get(source.emitted_by)
        return SourceFeedOut(id=source.emitted_by, title=title) if title is not None else None
    sub = db.get(Source, source.emitted_by)
    return SourceFeedOut(id=sub.id, title=sub.title) if sub is not None else None


def to_out(
    db: Session,
    source: Source,
    feed_titles: dict[uuid.UUID, str] | None = None,
) -> SnapshotOut:
    return SnapshotOut(
        id=source.id,
        kind=source.kind,
        title=source.title,
        note=source.note,
        status=source.status,
        media_type=source.media_type,
        genre=source.genre,
        origin_url=source.origin_url,
        content_body=source.content_body,
        captured_via=source.captured_via,
        cards_status=source.cards_status,
        tags=_tags_for(db, source.id),
        source_feed=_source_feed(db, source, feed_titles),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )
```

- [ ] **Step 5: Add the batch helper** — in `services/api/app/services/library.py`, add:

```python
def feed_titles_for(db: Session, sources: list[Source]) -> dict[uuid.UUID, str]:
    """One query mapping emitted_by subscription ids -> titles for a batch of
    snapshots (avoids per-item lookups in the library serialization)."""
    ids = {s.emitted_by for s in sources if s.emitted_by is not None}
    if not ids:
        return {}
    rows = db.execute(select(Source.id, Source.title).where(Source.id.in_(ids))).all()
    return {row[0]: row[1] for row in rows}
```

- [ ] **Step 6: Wire the router** — replace the body of `get_library` in `services/api/app/routers/library.py`:

```python
from app.services.library import feed_titles_for, list_library
```

```python
    sources = list_library(db, user.id)
    feed_titles = feed_titles_for(db, sources)
    items = [to_out(db, s, feed_titles) for s in sources]
    return LibraryOut(items=items, count=len(items))
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd services/api && uv run pytest tests/test_library.py -v`
Expected: PASS (all library tests, including the new one).

- [ ] **Step 8: Commit**

```bash
git add services/api/app/schemas/capture.py services/api/app/services/snapshots.py services/api/app/services/library.py services/api/app/routers/library.py services/api/tests/test_library.py
git commit -m "feat(api): expose source_feed (from emitted_by) on the library contract"
```

---

## Task 2: Backend — user tag add/remove endpoints

**Files:**
- Modify: `services/api/app/schemas/capture.py`
- Modify: `services/api/app/services/snapshots.py`
- Modify: `services/api/app/routers/capture.py`
- Test: `services/api/tests/test_snapshot_tags.py` (create)

**Interfaces:**
- Consumes: `to_out` (Task 1).
- Produces: `TagCreate(tag: str)` (whitespace-stripped, min_length 1); `add_tag(db, source, tag) -> Source`; `remove_tag(db, source, tag) -> Source`; `POST /snapshots/{id}/tags` and `DELETE /snapshots/{id}/tags?tag=` → `SnapshotOut`.

- [ ] **Step 1: Write the failing test** — create `services/api/tests/test_snapshot_tags.py`:

```python
"""POST/DELETE /snapshots/{id}/tags — manual user-tag add/remove."""

import pytest
from app.deps import get_db
from app.main import app
from app.schemas.capture import CaptureRequest
from app.services.capture import create_snapshot
from fastapi.testclient import TestClient
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _snap(db):  # type: ignore[no-untyped-def]
    snap, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/1"))
    snap.status = SnapshotStatus.ready
    db.commit()
    return snap


def test_add_tag(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snap = _snap(db)
    r = client.post(f"/snapshots/{snap.id}/tags", json={"tag": "pretrain"})
    assert r.status_code == 200
    assert "pretrain" in r.json()["tags"]


def test_add_tag_is_idempotent(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snap = _snap(db)
    client.post(f"/snapshots/{snap.id}/tags", json={"tag": "rl"})
    r = client.post(f"/snapshots/{snap.id}/tags", json={"tag": "rl"})
    assert r.json()["tags"].count("rl") == 1


def test_remove_tag(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snap = _snap(db)
    client.post(f"/snapshots/{snap.id}/tags", json={"tag": "rl"})
    r = client.delete(f"/snapshots/{snap.id}/tags", params={"tag": "rl"})
    assert r.status_code == 200
    assert "rl" not in r.json()["tags"]


def test_empty_tag_rejected(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snap = _snap(db)
    r = client.post(f"/snapshots/{snap.id}/tags", json={"tag": "   "})
    assert r.status_code == 422


def test_tag_foreign_snapshot_404(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    other = User(display_name="Other")
    db.add(other)
    db.flush()
    foreign = Source(
        owner_id=other.id, kind=SourceKind.snapshot, title="x", status=SnapshotStatus.ready
    )
    db.add(foreign)
    db.commit()
    r = client.post(f"/snapshots/{foreign.id}/tags", json={"tag": "x"})
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_snapshot_tags.py -v`
Expected: FAIL — 404/405 (route not defined) on the add/remove calls.

- [ ] **Step 3: Add the request schema** — in `services/api/app/schemas/capture.py`, update the pydantic import and add `TagCreate` after `SnapshotPatch`:

```python
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator
```

```python
class TagCreate(BaseModel):
    tag: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
```

- [ ] **Step 4: Add the services** — in `services/api/app/services/snapshots.py`, add below `_tags_for`:

```python
def add_tag(db: Session, source: Source, tag: str) -> Source:
    """Idempotent: no-op if a live row already exists for (source, tag)."""
    live = db.scalar(
        select(SourceTag.id).where(
            SourceTag.source_id == source.id,
            SourceTag.tag == tag,
            SourceTag.deleted_at.is_(None),
        )
    )
    if live is None:
        db.add(SourceTag(source_id=source.id, tag=tag))
        db.commit()
    return source


def remove_tag(db: Session, source: Source, tag: str) -> Source:
    """Soft-delete every live row for (source, tag). No-op if none match."""
    db.execute(
        update(SourceTag)
        .where(
            SourceTag.source_id == source.id,
            SourceTag.tag == tag,
            SourceTag.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.now(UTC))
    )
    db.commit()
    return source
```

- [ ] **Step 5: Add the routes** — in `services/api/app/routers/capture.py`, update imports and add a shared owner-check helper plus the two endpoints. Update imports:

```python
from app.schemas.capture import (
    CaptureRequest,
    CaptureResponse,
    SnapshotOut,
    SnapshotPatch,
    TagCreate,
)
from app.services.snapshots import add_tag, delete_snapshot, remove_tag, to_out, update_snapshot
```

Add the helper (place above `get_snapshot`) and refactor the existing 404 checks in `get_snapshot`/`patch_snapshot`/`delete_snapshot_route` to use it:

```python
def _owned_snapshot(db: Session, snapshot_id: uuid.UUID, user: User) -> Source:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return source
```

Then the existing handlers become e.g. `source = _owned_snapshot(db, snapshot_id, user)`. Add the two new endpoints after `delete_snapshot_route`:

```python
@router.post("/snapshots/{snapshot_id}/tags", response_model=SnapshotOut)
def add_snapshot_tag(
    snapshot_id: uuid.UUID,
    body: TagCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SnapshotOut:
    source = _owned_snapshot(db, snapshot_id, user)
    return to_out(db, add_tag(db, source, body.tag))


@router.delete("/snapshots/{snapshot_id}/tags", response_model=SnapshotOut)
def remove_snapshot_tag(
    snapshot_id: uuid.UUID,
    tag: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SnapshotOut:
    source = _owned_snapshot(db, snapshot_id, user)
    return to_out(db, remove_tag(db, source, tag))
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd services/api && uv run pytest tests/test_snapshot_tags.py tests/test_capture.py tests/test_delete_snapshot.py -v`
Expected: PASS (new tag tests + existing capture/delete tests still green after the `_owned_snapshot` refactor).

- [ ] **Step 7: Commit**

```bash
git add services/api/app/schemas/capture.py services/api/app/services/snapshots.py services/api/app/routers/capture.py services/api/tests/test_snapshot_tags.py
git commit -m "feat(api): add/remove user tags on a snapshot"
```

---

## Task 3: Regenerate the api-client + TS tag helpers

**Files:**
- Modify (generated): `packages/api-client/openapi.json`, `packages/api-client/src/schema.gen.ts`
- Modify: `packages/api-client/src/index.ts`

**Interfaces:**
- Consumes: the Task 1/2 contract (`source_feed`, `/snapshots/{id}/tags`).
- Produces: `Snapshot["source_feed"]: { id: string; title: string } | null`; `addSnapshotTag(id, tag) => Promise<SnapshotOut>`; `removeSnapshotTag(id, tag) => Promise<SnapshotOut>`.

- [ ] **Step 1: Regenerate the client from the API schema**

Run: `just gen-client`
Expected: `packages/api-client/schema.gen.ts` now contains `source_feed` on the snapshot type and a `/snapshots/{snapshot_id}/tags` path. (Ignore the 2 pre-existing dup-identifier `tsc` warnings.)

- [ ] **Step 2: Verify the generated types**

Run: `grep -n "source_feed\|snapshot_id}/tags" packages/api-client/src/schema.gen.ts | head`
Expected: at least one match for each.

- [ ] **Step 3: Add the typed helpers** — in `packages/api-client/src/index.ts`, after `deleteSnapshot` (~line 87):

```typescript
export async function addSnapshotTag(id: string, tag: string): Promise<SnapshotOut> {
  const { data, error } = await client.POST("/snapshots/{snapshot_id}/tags", {
    params: { path: { snapshot_id: id } },
    body: { tag },
  });
  if (error || !data) throw new Error("add tag failed");
  return data;
}

export async function removeSnapshotTag(id: string, tag: string): Promise<SnapshotOut> {
  const { data, error } = await client.DELETE("/snapshots/{snapshot_id}/tags", {
    params: { path: { snapshot_id: id }, query: { tag } },
  });
  if (error || !data) throw new Error("remove tag failed");
  return data;
}
```

- [ ] **Step 4: Typecheck the client package**

Run: `pnpm --filter @gulp/api-client build` (or `pnpm --filter @gulp/api-client lint`)
Expected: succeeds — the new helpers typecheck against the regenerated paths.

- [ ] **Step 5: Commit**

```bash
git add packages/api-client
git commit -m "feat(api-client): regenerate + addSnapshotTag/removeSnapshotTag helpers"
```

---

## Task 4: Web — library facet helpers

**Files:**
- Create: `apps/web/lib/libraryFacets.ts`
- Test: `apps/web/lib/libraryFacets.test.ts`

**Interfaces:**
- Consumes: `Snapshot` (with `source_feed`, `tags`) from `@gulp/api-client`.
- Produces: `type FacetEntry = { value: string; count: number }`; `type LibraryFacets = { sources: FacetEntry[]; tags: FacetEntry[] }`; `type ActiveFilter = { kind: "source" | "tag"; value: string } | null`; `computeFacets(items) => LibraryFacets`; `filterItems(items, active) => Snapshot[]`.

- [ ] **Step 1: Write the failing test** — create `apps/web/lib/libraryFacets.test.ts` (JSX-free — **no** `import React`):

```typescript
import { describe, expect, it } from "vitest";
import type { Snapshot } from "@gulp/api-client";
import { computeFacets, filterItems } from "./libraryFacets";

function item(o: Partial<Snapshot> = {}): Snapshot {
  return {
    id: "s1", kind: "snapshot", title: "T", note: null, status: "ready",
    media_type: "article", genre: null, origin_url: "https://a.com", content_body: null,
    captured_via: "feed", cards_status: null, tags: [], source_feed: null,
    created_at: "", updated_at: "", ...o,
  } as Snapshot;
}

describe("computeFacets", () => {
  it("groups sources and tags with counts, sorted by name", () => {
    const items = [
      item({ id: "1", source_feed: { id: "f1", title: "HF Paper Daily" }, tags: ["pretrain"] }),
      item({ id: "2", source_feed: { id: "f1", title: "HF Paper Daily" }, tags: [] }),
      item({ id: "3", source_feed: null, tags: ["pretrain", "rl"] }),
    ];
    const f = computeFacets(items);
    expect(f.sources).toEqual([{ value: "HF Paper Daily", count: 2 }]);
    expect(f.tags).toEqual([{ value: "pretrain", count: 2 }, { value: "rl", count: 1 }]);
  });
});

describe("filterItems", () => {
  const items = [
    item({ id: "1", source_feed: { id: "f1", title: "HF Paper Daily" }, tags: ["pretrain"] }),
    item({ id: "2", source_feed: null, tags: ["rl"] }),
  ];
  it("returns all when no filter is active", () => {
    expect(filterItems(items, null)).toHaveLength(2);
  });
  it("filters by source", () => {
    expect(filterItems(items, { kind: "source", value: "HF Paper Daily" }).map((i) => i.id)).toEqual(["1"]);
  });
  it("filters by tag", () => {
    expect(filterItems(items, { kind: "tag", value: "rl" }).map((i) => i.id)).toEqual(["2"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web test -- libraryFacets`
Expected: FAIL — cannot resolve `./libraryFacets`.

- [ ] **Step 3: Implement** — create `apps/web/lib/libraryFacets.ts` (JSX-free — **no** `import React`):

```typescript
import type { Snapshot } from "@gulp/api-client";

export type FacetEntry = { value: string; count: number };
export type LibraryFacets = { sources: FacetEntry[]; tags: FacetEntry[] };
export type ActiveFilter = { kind: "source" | "tag"; value: string } | null;

function toEntries(counts: Map<string, number>): FacetEntry[] {
  return Array.from(counts, ([value, count]) => ({ value, count })).sort((a, b) =>
    a.value.localeCompare(b.value),
  );
}

export function computeFacets(items: Snapshot[]): LibraryFacets {
  const sources = new Map<string, number>();
  const tags = new Map<string, number>();
  for (const it of items) {
    if (it.source_feed) {
      sources.set(it.source_feed.title, (sources.get(it.source_feed.title) ?? 0) + 1);
    }
    for (const t of it.tags) {
      tags.set(t, (tags.get(t) ?? 0) + 1);
    }
  }
  return { sources: toEntries(sources), tags: toEntries(tags) };
}

export function filterItems(items: Snapshot[], active: ActiveFilter): Snapshot[] {
  if (!active) return items;
  if (active.kind === "source") {
    return items.filter((i) => i.source_feed?.title === active.value);
  }
  return items.filter((i) => i.tags.includes(active.value));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter @gulp/web test -- libraryFacets`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/libraryFacets.ts apps/web/lib/libraryFacets.test.ts
git commit -m "feat(web): library facet helpers (compute/filter by source + tag)"
```

---

## Task 5: Web — LibraryTagSidebar component

**Files:**
- Create: `apps/web/components/library/LibraryTagSidebar.tsx`, `apps/web/components/library/LibraryTagSidebar.module.css`
- Test: `apps/web/components/library/LibraryTagSidebar.test.tsx`

**Interfaces:**
- Consumes: `LibraryFacets`, `ActiveFilter`, `FacetEntry` (Task 4).
- Produces: `<LibraryTagSidebar facets={...} active={...} onSelect={(f: ActiveFilter) => void} />` (an `<aside aria-label="Filter library">`, role `complementary`).

- [ ] **Step 1: Write the failing test** — create `apps/web/components/library/LibraryTagSidebar.test.tsx` (**`import React`** — JSX):

```tsx
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { LibraryFacets } from "@/lib/libraryFacets";
import { LibraryTagSidebar } from "./LibraryTagSidebar";

afterEach(cleanup);

const facets: LibraryFacets = {
  sources: [{ value: "HF Paper Daily", count: 2 }],
  tags: [{ value: "pretrain", count: 3 }],
};

describe("LibraryTagSidebar", () => {
  it("renders Sources, Mine, and a disabled Topics placeholder", () => {
    render(<LibraryTagSidebar facets={facets} active={null} onSelect={() => {}} />);
    expect(screen.getByText("Sources")).toBeTruthy();
    expect(screen.getByText("Mine")).toBeTruthy();
    expect(screen.getByText("Topics")).toBeTruthy();
    expect(screen.getByText("coming soon")).toBeTruthy();
    expect(screen.getByText("HF Paper Daily")).toBeTruthy();
  });

  it("selects a source filter on click", async () => {
    const onSelect = vi.fn();
    render(<LibraryTagSidebar facets={facets} active={null} onSelect={onSelect} />);
    await userEvent.click(screen.getByText("HF Paper Daily"));
    expect(onSelect).toHaveBeenCalledWith({ kind: "source", value: "HF Paper Daily" });
  });

  it("toggles the active filter off when re-clicked", async () => {
    const onSelect = vi.fn();
    render(
      <LibraryTagSidebar
        facets={facets}
        active={{ kind: "tag", value: "pretrain" }}
        onSelect={onSelect}
      />,
    );
    await userEvent.click(screen.getByText("pretrain"));
    expect(onSelect).toHaveBeenCalledWith(null);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web test -- LibraryTagSidebar`
Expected: FAIL — cannot resolve `./LibraryTagSidebar`.

- [ ] **Step 3: Implement the component** — create `apps/web/components/library/LibraryTagSidebar.tsx` (**`import React`**):

```tsx
import React from "react";
import type { ActiveFilter, FacetEntry, LibraryFacets } from "@/lib/libraryFacets";
import styles from "./LibraryTagSidebar.module.css";

function Group({
  title,
  kind,
  entries,
  active,
  onSelect,
}: {
  title: string;
  kind: "source" | "tag";
  entries: FacetEntry[];
  active: ActiveFilter;
  onSelect: (f: ActiveFilter) => void;
}) {
  if (entries.length === 0) return null;
  return (
    <div className={styles.group}>
      <div className={styles.groupTitle}>{title}</div>
      {entries.map((e) => {
        const on = active?.kind === kind && active.value === e.value;
        return (
          <button
            key={e.value}
            type="button"
            className={`${styles.entry} ${on ? styles.entryActive : ""}`}
            onClick={() => onSelect(on ? null : { kind, value: e.value })}
          >
            <span className={styles.entryLabel}>{e.value}</span>
            <span className={styles.entryCount}>{e.count}</span>
          </button>
        );
      })}
    </div>
  );
}

export function LibraryTagSidebar({
  facets,
  active,
  onSelect,
}: {
  facets: LibraryFacets;
  active: ActiveFilter;
  onSelect: (f: ActiveFilter) => void;
}) {
  return (
    <aside className={styles.sidebar} aria-label="Filter library">
      <button
        type="button"
        className={`${styles.entry} ${active === null ? styles.entryActive : ""}`}
        onClick={() => onSelect(null)}
      >
        <span className={styles.entryLabel}>All</span>
      </button>
      <Group title="Sources" kind="source" entries={facets.sources} active={active} onSelect={onSelect} />
      <Group title="Mine" kind="tag" entries={facets.tags} active={active} onSelect={onSelect} />
      <div className={styles.group}>
        <div className={styles.groupTitle}>Topics</div>
        <div className={styles.comingSoon}>coming soon</div>
      </div>
    </aside>
  );
}
```

- [ ] **Step 4: Add the styles** — create `apps/web/components/library/LibraryTagSidebar.module.css`:

```css
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 2px;
  position: sticky;
  top: 24px;
}

.group {
  margin-top: 12px;
}

.groupTitle {
  font-size: 0.72em;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted, #777);
  padding: 4px 8px;
}

.entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  font: inherit;
  font-size: 0.9em;
  text-align: left;
  padding: 5px 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: none;
  cursor: pointer;
}

.entry:hover {
  background: var(--surface, #fffdf6);
}

.entryActive {
  background: var(--blue-50, #fff4c2);
  color: var(--blue-700, #16130b);
  border-color: var(--border-strong, #d8cca8);
}

.entryLabel {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entryCount {
  color: var(--text-muted, #777);
  font-size: 0.85em;
  flex: none;
}

.comingSoon {
  font-size: 0.82em;
  color: var(--text-muted, #777);
  padding: 5px 8px;
  font-style: italic;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm --filter @gulp/web test -- LibraryTagSidebar`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/library/LibraryTagSidebar.tsx apps/web/components/library/LibraryTagSidebar.module.css apps/web/components/library/LibraryTagSidebar.test.tsx
git commit -m "feat(web): LibraryTagSidebar (Sources/Mine facets + Topics placeholder)"
```

---

## Task 6: Web — RowTags component (source chip + editable user tags)

**Files:**
- Create: `apps/web/components/library/RowTags.tsx`, `apps/web/components/library/RowTags.module.css`
- Test: `apps/web/components/library/RowTags.test.tsx`

**Interfaces:**
- Consumes: `addSnapshotTag`, `removeSnapshotTag`, `Snapshot["source_feed"]` from `@gulp/api-client`.
- Produces: `<RowTags snapshotId sourceFeed tags onTagsChange onSourceClick />` — optimistic add/remove with rollback.

- [ ] **Step 1: Write the failing test** — create `apps/web/components/library/RowTags.test.tsx` (**`import React`**):

```tsx
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RowTags } from "./RowTags";

const addSnapshotTag = vi.fn().mockResolvedValue({});
const removeSnapshotTag = vi.fn().mockResolvedValue({});
vi.mock("@gulp/api-client", () => ({
  addSnapshotTag: (...a: unknown[]) => addSnapshotTag(...a),
  removeSnapshotTag: (...a: unknown[]) => removeSnapshotTag(...a),
}));

afterEach(() => {
  cleanup();
  addSnapshotTag.mockClear();
  removeSnapshotTag.mockClear();
});

describe("RowTags", () => {
  it("renders the source chip and filters on click", async () => {
    const onSourceClick = vi.fn();
    render(
      <RowTags
        snapshotId="s1"
        sourceFeed={{ id: "f1", title: "HF Paper Daily" }}
        tags={[]}
        onTagsChange={() => {}}
        onSourceClick={onSourceClick}
      />,
    );
    await userEvent.click(screen.getByText("HF Paper Daily"));
    expect(onSourceClick).toHaveBeenCalledWith("HF Paper Daily");
  });

  it("removes a tag optimistically and calls the API", async () => {
    const onTagsChange = vi.fn();
    render(
      <RowTags snapshotId="s1" sourceFeed={null} tags={["pretrain"]} onTagsChange={onTagsChange} onSourceClick={() => {}} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Remove tag pretrain" }));
    expect(onTagsChange).toHaveBeenCalledWith([]);
    await waitFor(() => expect(removeSnapshotTag).toHaveBeenCalledWith("s1", "pretrain"));
  });

  it("adds a tag via the + control", async () => {
    const onTagsChange = vi.fn();
    render(
      <RowTags snapshotId="s1" sourceFeed={null} tags={[]} onTagsChange={onTagsChange} onSourceClick={() => {}} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Add tag" }));
    await userEvent.type(screen.getByPlaceholderText("tag"), "rl{Enter}");
    expect(onTagsChange).toHaveBeenCalledWith(["rl"]);
    await waitFor(() => expect(addSnapshotTag).toHaveBeenCalledWith("s1", "rl"));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web test -- RowTags`
Expected: FAIL — cannot resolve `./RowTags`.

- [ ] **Step 3: Implement the component** — create `apps/web/components/library/RowTags.tsx` (**`import React`**):

```tsx
"use client";

import React, { useState } from "react";
import type { Snapshot } from "@gulp/api-client";
import { addSnapshotTag, removeSnapshotTag } from "@gulp/api-client";
import styles from "./RowTags.module.css";

export function RowTags({
  snapshotId,
  sourceFeed,
  tags,
  onTagsChange,
  onSourceClick,
}: {
  snapshotId: string;
  sourceFeed: Snapshot["source_feed"];
  tags: string[];
  onTagsChange: (tags: string[]) => void;
  onSourceClick: (title: string) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [value, setValue] = useState("");

  async function commitAdd() {
    const t = value.trim();
    setAdding(false);
    setValue("");
    if (!t || tags.includes(t)) return;
    const prev = tags;
    onTagsChange([...tags, t]); // optimistic
    try {
      await addSnapshotTag(snapshotId, t);
    } catch {
      onTagsChange(prev); // rollback
    }
  }

  async function removeTag(t: string) {
    const prev = tags;
    onTagsChange(tags.filter((x) => x !== t)); // optimistic
    try {
      await removeSnapshotTag(snapshotId, t);
    } catch {
      onTagsChange(prev); // rollback
    }
  }

  return (
    <span className={styles.tags}>
      {sourceFeed && (
        <button
          type="button"
          className={styles.source}
          onClick={() => onSourceClick(sourceFeed.title)}
          title={`Filter by ${sourceFeed.title}`}
        >
          {sourceFeed.title}
        </button>
      )}
      {tags.map((t) => (
        <span key={t} className={styles.tag}>
          {t}
          <button
            type="button"
            className={styles.remove}
            aria-label={`Remove tag ${t}`}
            onClick={() => removeTag(t)}
          >
            ×
          </button>
        </span>
      ))}
      {adding ? (
        <input
          className={styles.input}
          autoFocus
          value={value}
          placeholder="tag"
          onChange={(e) => setValue(e.target.value)}
          onBlur={commitAdd}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitAdd();
            if (e.key === "Escape") {
              setAdding(false);
              setValue("");
            }
          }}
        />
      ) : (
        <button
          type="button"
          className={styles.add}
          aria-label="Add tag"
          onClick={() => setAdding(true)}
        >
          +
        </button>
      )}
    </span>
  );
}
```

- [ ] **Step 4: Add the styles** — create `apps/web/components/library/RowTags.module.css`:

```css
.tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}

.source {
  font: inherit;
  font-size: 0.78em;
  padding: 2px 8px;
  border: 1px solid var(--border-strong, #d8cca8);
  border-radius: 999px;
  background: var(--blue-50, #fff4c2);
  color: var(--blue-700, #16130b);
  cursor: pointer;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.78em;
  padding: 2px 4px 2px 8px;
  border: 1px solid var(--border, #e7dfc8);
  border-radius: 999px;
  color: var(--text-muted, #777);
}

.remove {
  font: inherit;
  line-height: 1;
  border: none;
  background: none;
  cursor: pointer;
  color: var(--text-muted, #777);
  padding: 0 2px;
}

.remove:hover {
  color: var(--blue-700, #16130b);
}

.add {
  font: inherit;
  font-size: 0.9em;
  line-height: 1;
  width: 20px;
  height: 20px;
  border: 1px dashed var(--border-strong, #d8cca8);
  border-radius: 999px;
  background: none;
  cursor: pointer;
  color: var(--text-muted, #777);
}

.input {
  font: inherit;
  font-size: 0.78em;
  width: 90px;
  padding: 2px 8px;
  border: 1px solid var(--border-strong, #d8cca8);
  border-radius: 999px;
  background: var(--surface, #fffdf6);
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm --filter @gulp/web test -- RowTags`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/library/RowTags.tsx apps/web/components/library/RowTags.module.css apps/web/components/library/RowTags.test.tsx
git commit -m "feat(web): RowTags — source chip + optimistic user-tag edit"
```

---

## Task 7: Web — two-pane LibraryList wiring

**Files:**
- Modify: `apps/web/components/library/LibraryList.tsx`
- Modify: `apps/web/components/library/LibraryList.module.css`
- Modify: `apps/web/components/library/LibraryList.test.tsx`
- Modify: `apps/web/app/library/page.module.css`

**Interfaces:**
- Consumes: `computeFacets`, `filterItems`, `ActiveFilter` (Task 4); `LibraryTagSidebar` (Task 5); `RowTags` (Task 6).
- Produces: the assembled Library view (sidebar + filtered list, optimistic tag state).

- [ ] **Step 1: Rewrite the filter tests** — replace `apps/web/components/library/LibraryList.test.tsx` with (**`import React`**):

```tsx
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Snapshot } from "@gulp/api-client";
import { LibraryList } from "./LibraryList";

// Rows carry <DeleteSnapshotButton> (useRouter) and <RowTags> (api-client).
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));
vi.mock("@gulp/api-client", () => ({
  addSnapshotTag: vi.fn().mockResolvedValue({}),
  removeSnapshotTag: vi.fn().mockResolvedValue({}),
  deleteSnapshot: vi.fn().mockResolvedValue(undefined),
}));

afterEach(cleanup);

const sidebar = () => screen.getByRole("complementary", { name: "Filter library" });

function item(overrides: Partial<Snapshot> = {}): Snapshot {
  return {
    id: "s1", kind: "snapshot", title: "ABot-M0.5", note: null, status: "ready",
    media_type: "pdf", genre: null, origin_url: "https://arxiv.org/abs/1", content_body: null,
    captured_via: "paste", cards_status: null, tags: ["robotics"], source_feed: null,
    created_at: "", updated_at: "", ...overrides,
  } as Snapshot;
}

describe("LibraryList", () => {
  it("renders shelved snapshots with links", () => {
    render(<LibraryList items={[item(), item({ id: "s2", title: "BERT", tags: ["nlp"] })]} />);
    expect(screen.getByRole("link", { name: "ABot-M0.5" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "BERT" })).toBeTruthy();
  });

  it("filters by a Mine tag entry and resets with All", async () => {
    render(<LibraryList items={[item(), item({ id: "s2", title: "BERT", tags: ["nlp"] })]} />);
    await userEvent.click(within(sidebar()).getByRole("button", { name: /nlp/ }));
    expect(screen.queryByRole("link", { name: "ABot-M0.5" })).toBeNull();
    expect(screen.getByRole("link", { name: "BERT" })).toBeTruthy();
    await userEvent.click(within(sidebar()).getByRole("button", { name: "All" }));
    expect(screen.getByRole("link", { name: "ABot-M0.5" })).toBeTruthy();
  });

  it("filters by a Source entry", async () => {
    render(
      <LibraryList
        items={[
          item({ id: "s1", title: "Paper A", source_feed: { id: "f1", title: "HF Paper Daily" }, tags: [] }),
          item({ id: "s2", title: "Blog B", source_feed: null, tags: [] }),
        ]}
      />,
    );
    await userEvent.click(within(sidebar()).getByRole("button", { name: /HF Paper Daily/ }));
    expect(screen.getByRole("link", { name: "Paper A" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Blog B" })).toBeNull();
  });

  it("shows the empty state", () => {
    render(<LibraryList items={[]} />);
    expect(screen.getByText(/Nothing here yet/)).toBeTruthy();
  });

  it("shows per-row badges (media_type + cards status)", () => {
    render(<LibraryList items={[item({ media_type: "video", cards_status: "generating" })]} />);
    expect(screen.getByText("Video")).toBeTruthy();
    expect(screen.getByText("Cards…")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter @gulp/web test -- LibraryList`
Expected: FAIL — the old component has no `complementary` sidebar (`getByRole("complementary", …)` throws).

- [ ] **Step 3: Rewrite the component** — replace `apps/web/components/library/LibraryList.tsx` with:

```tsx
"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Snapshot } from "@gulp/api-client";
import { ObjectGlyph } from "@/components/ui/ObjectGlyph";
import { DeleteSnapshotButton } from "@/components/snapshot/DeleteSnapshotButton";
import { RowBadges } from "./RowBadges";
import { RowTags } from "./RowTags";
import { LibraryTagSidebar } from "./LibraryTagSidebar";
import { computeFacets, filterItems, type ActiveFilter } from "@/lib/libraryFacets";
import { safeHost } from "@/lib/pack";
import styles from "./LibraryList.module.css";

export function LibraryList({ items }: { items: Snapshot[] }) {
  // Local copy so tag edits are optimistic; re-sync when the server re-fetches
  // (e.g. after a delete calls router.refresh()).
  const [rows, setRows] = useState<Snapshot[]>(items);
  useEffect(() => setRows(items), [items]);
  const [active, setActive] = useState<ActiveFilter>(null);

  const facets = useMemo(() => computeFacets(rows), [rows]);
  const shown = useMemo(() => filterItems(rows, active), [rows, active]);

  if (items.length === 0) {
    return <p className={styles.empty}>Nothing here yet — capture something and run it.</p>;
  }

  function setTags(id: string, tags: string[]) {
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, tags } : r)));
  }

  return (
    <div className={styles.layout}>
      <LibraryTagSidebar facets={facets} active={active} onSelect={setActive} />
      <div className={styles.listCol}>
        {shown.length === 0 ? (
          <p className={styles.empty}>Nothing under “{active?.value}”.</p>
        ) : (
          <ul className={styles.list}>
            {shown.map((item) => (
              <li key={item.id} className={styles.row}>
                <ObjectGlyph type="snapshot" />
                <div className={styles.text}>
                  <Link href={`/snapshots/${item.id}`} className={styles.title}>
                    {item.title}
                  </Link>
                  <span className={`t-data ${styles.meta}`}>{safeHost(item.origin_url)}</span>
                  <RowTags
                    snapshotId={item.id}
                    sourceFeed={item.source_feed}
                    tags={item.tags}
                    onTagsChange={(t) => setTags(item.id, t)}
                    onSourceClick={(title) => setActive({ kind: "source", value: title })}
                  />
                </div>
                <RowBadges mediaType={item.media_type} cardsStatus={item.cards_status} />
                <DeleteSnapshotButton id={item.id} confirm />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add the two-pane layout styles** — in `apps/web/components/library/LibraryList.module.css`, remove the now-unused `.chips`, `.chip`, `.chipActive` rules and add at the top:

```css
.layout {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 24px;
  align-items: start;
  padding-top: 12px;
}

.listCol {
  min-width: 0;
  max-width: var(--measure, 720px);
}

@media (max-width: 720px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 5: Widen the page** — in `apps/web/app/library/page.module.css`, change `.page` max-width:

```css
.page {
  max-width: 1040px;
  margin: 0 auto;
  padding: 32px 24px;
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pnpm --filter @gulp/web test -- LibraryList`
Expected: PASS (all five cases).

- [ ] **Step 7: Commit**

```bash
git add apps/web/components/library/LibraryList.tsx apps/web/components/library/LibraryList.module.css apps/web/components/library/LibraryList.test.tsx apps/web/app/library/page.module.css
git commit -m "feat(web): two-pane Library — tag sidebar + source chips + tag editing"
```

---

## Task 8: Docs — amend the product specs

**Files:**
- Modify: `docs/01-interaction-spec.md` (§F3)
- Modify: `docs/03-ui-system.md` (§7.3)
- Modify: `docs/02-data-model.md` (§4.3)

**Interfaces:** none (documentation).

- [ ] **Step 1: Amend `docs/01-interaction-spec.md §F3`** — in the "Library & knowledge base browsing" paragraph, change the browse axes to add source, and note the sidebar. Add this sentence to the section:

> Browsing is via a left **tag sidebar** grouped by **Sources** (the feed each item was forwarded from, derived from `Source.emitted_by`), **Mine** (user `SourceTag`s, editable inline), and a reserved **Topics** group (AI topic tags — placeholder until AI tagging ships). Filtering is single-select; the Knowledge-base entity stays parked.

- [ ] **Step 2: Amend `docs/03-ui-system.md §7.3`** — under "Filter chips (web Library)", add:

> The web Library realizes these facets as a **left tag sidebar** (grouped Sources / Mine / Topics with per-entry counts), not a single chip row. Each object card's metadata row carries a read-only **source chip** (the feed it came from) plus its editable user tags. Selected entry style follows the chip rule: `--blue-50` fill + `--blue-700` text + border. The **Topics** group is rendered disabled ("coming soon") until AI topic tagging exists.

- [ ] **Step 3: Amend `docs/02-data-model.md §4.3`** — next to the `emitted_by` line, add:

> The Library's **Sources** facet is *derived* from `emitted_by` (join to the subscription's `title`) and surfaced on the contract as `SnapshotOut.source_feed` — no materialized source tag and no tag-`origin` column yet; that column arrives with AI topic tagging.

- [ ] **Step 4: Commit**

```bash
git add docs/01-interaction-spec.md docs/03-ui-system.md docs/02-data-model.md
git commit -m "docs: Library source facet + tag sidebar + reserved Topics"
```

---

## Task 9: Full-stack verification gate

**Files:** none (verification only).

- [ ] **Step 1: Regenerate the client is a no-op (contract unchanged since Task 3)**

Run: `just gen-client && git status --porcelain packages/api-client`
Expected: no new diff (confirms the committed client matches the API schema).

- [ ] **Step 2: Run the API test suite**

Run: `cd services/api && uv run pytest -q`
Expected: PASS (no regressions).

- [ ] **Step 3: Run the web test suite**

Run: `pnpm --filter @gulp/web test`
Expected: PASS (libraryFacets, LibraryTagSidebar, RowTags, LibraryList).

- [ ] **Step 4: Run the full lint gate**

Run: `just lint`
Expected: green (eslint via turbo, ruff, mypy for shared/api/worker).

- [ ] **Step 5: Manual smoke** (requires local infra + `just dev`)

- Open `/library`. Confirm: left sidebar shows **Sources** (feed titles with counts) for any feed-forwarded items, **Mine** (your tags), and a disabled **Topics — coming soon**.
- Click a Source entry → list narrows to that feed; click **All** → resets.
- On a row, click **+**, type a tag, press Enter → chip appears immediately; reload → it persists.
- Click a tag chip's **×** → it disappears; reload → still gone.
- Click a row's source chip → list filters to that feed.

- [ ] **Step 6: Final commit (if any lint/format fixups were needed)**

```bash
git add -A && git commit -m "chore: lint/format fixups for library redesign"
```

---

## Self-Review

**Spec coverage:**
- Source tags on feed items → Task 1 (`source_feed` derived from `emitted_by`), rendered as source chip (Task 6) + Sources facet (Tasks 4/5/7). ✓
- Categorize by tags (sidebar) → Tasks 4/5/7 (single-select). ✓
- Add/remove user tags → Task 2 (endpoints) + Task 6 (RowTags). ✓
- AI topics reserved, no model/migration → Task 5 (disabled Topics group); no `origin` column anywhere. ✓
- Docs-first amendments → Task 8. ✓
- Testing (vitest classic-JSX, pytest per-package) + gates → per-task tests + Task 9. ✓
- Out of scope (AI logic, multi-select, grouped view, reader, KB) → not present. ✓

**Placeholder scan:** no TBD/TODO; every code step shows complete code; docs steps quote the exact sentences to insert. ✓

**Type consistency:** `to_out(db, source, feed_titles=None)`, `feed_titles_for`, `_source_feed`, `SourceFeedOut{id,title}`, `TagCreate{tag}`, `addSnapshotTag/removeSnapshotTag`, `ActiveFilter{kind,value}`, `computeFacets/filterItems`, `LibraryTagSidebar`/`RowTags` props — names/signatures match across tasks. ✓
