# Inbox & Library Delete — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user delete an inbox or library snapshot, cascading a soft-delete to all its derivatives (pack + sections/blocks/messages, cards, figures, tags, concepts).

**Architecture:** One `DELETE /snapshots/{id}` endpoint (both pages are the same `Source`). A `delete_snapshot` service stamps `deleted_at` across the snapshot and its derivative rows in one transaction. The web client calls a generated-contract wrapper `deleteSnapshot(id)` via a shared `DeleteSnapshotButton` island — immediate on inbox, two-step confirm on library — then `router.refresh()`.

**Tech Stack:** FastAPI + SQLAlchemy (services/api, services/shared), Next.js App Router + TypeScript (apps/web), openapi-fetch generated client (packages/api-client), pytest, vitest.

## Global Constraints

- Soft-delete only: stamp `deleted_at = datetime.now(UTC)`; never physical `DELETE`. Every read path already filters `deleted_at IS NULL`.
- API is the contract source: after adding the route, run `just gen-client`. Components talk to the backend only through `@gulp/api-client`.
- Conventional layering: routers thin, logic in `app/services`, persistence models in `gulp_shared`.
- Ownership: 404 (not 403) on missing / foreign-owner / already-deleted, mirroring `get_snapshot` in `capture.py`.
- Per-package Python tests: run from `services/api` (`cd services/api && uv run pytest`).
- Web vitest uses the classic JSX transform: any JSX-bearing file needs `import React`.

---

### Task 1: Backend — `delete_snapshot` service + `DELETE /snapshots/{id}` route

**Files:**
- Modify: `services/api/app/services/snapshots.py` (add `delete_snapshot`)
- Modify: `services/api/app/routers/capture.py` (add the DELETE route)
- Test: `services/api/tests/test_delete_snapshot.py` (create)

**Interfaces:**
- Produces: `delete_snapshot(db: Session, source: Source) -> None` — cascade soft-delete.
- Produces HTTP: `DELETE /snapshots/{snapshot_id}` → `204`, `404` on missing/foreign/deleted.

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_delete_snapshot.py`:

```python
"""DELETE /snapshots/{id} — cascade soft-delete of a snapshot and its derivatives."""

import uuid
from datetime import UTC, datetime

import pytest
from app.deps import get_db, get_enqueue
from app.main import app
from fastapi.testclient import TestClient
from gulp_shared.models.card import Card, CardOrigin, CardType
from gulp_shared.models.concept import Concept, SourceConcept
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.pack_block_message import ChatRole, PackBlockMessage
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.source_tag import SourceTag
from gulp_shared.models.user import DEV_USER_ID


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: None)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _library_snapshot_with_derivatives(db) -> Source:  # type: ignore[no-untyped-def]
    """A `ready` snapshot wired up with one of every derivative."""
    src = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="S",
        status=SnapshotStatus.ready,
    )
    db.add(src)
    db.flush()

    pack = KnowledgePack(
        snapshot_id=src.id,
        title="T",
        key_insight="k",
        core_contributions=["c"],
        references=[],
        status=PackStatus.ready,
    )
    db.add(pack)
    db.flush()
    section = PackSection(pack_id=pack.id, heading="H", position=0)
    db.add(section)
    db.flush()
    block = PackBlock(section_id=section.id, block_type=PackBlockType.prose, data={}, position=0)
    db.add(block)
    db.flush()
    db.add(PackBlockMessage(block_id=block.id, role=ChatRole.user, content="hi"))

    db.add(Card(source_id=src.id, card_type=CardType.flashcard, prompt="Q", answer="A",
                origin=CardOrigin.imported))
    db.add(SourceFigure(source_id=src.id, ordinal=0, ref="f", caption="c"))
    db.add(SourceTag(source_id=src.id, label="t"))
    concept = Concept(label="c")
    db.add(concept)
    db.flush()
    db.add(SourceConcept(source_id=src.id, concept_id=concept.id))
    db.commit()
    return src


def test_delete_library_snapshot_cascades(client, db) -> None:  # type: ignore[no-untyped-def]
    src = _library_snapshot_with_derivatives(db)
    sid = str(src.id)

    r = client.delete(f"/snapshots/{sid}")
    assert r.status_code == 204

    # Gone from every read path.
    assert client.get(f"/snapshots/{sid}").status_code == 404
    assert client.get(f"/snapshots/{sid}/pack").status_code == 404
    assert sid not in [i["id"] for i in client.get("/library").json()["items"]]

    # Every derivative carries deleted_at.
    db.expire_all()
    for model, where in [
        (Card, Card.source_id == src.id),
        (SourceFigure, SourceFigure.source_id == src.id),
        (SourceTag, SourceTag.source_id == src.id),
        (SourceConcept, SourceConcept.source_id == src.id),
        (KnowledgePack, KnowledgePack.snapshot_id == src.id),
    ]:
        from sqlalchemy import select

        rows = list(db.scalars(select(model).where(where)))
        assert rows and all(row.deleted_at is not None for row in rows), model.__name__


def test_delete_inbox_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/capture", json={"url": "https://a.com/x"})
    sid = r.json()["snapshot"]["id"]
    assert client.delete(f"/snapshots/{sid}").status_code == 204
    assert sid not in [i["id"] for i in client.get("/inbox").json()["items"]]


def test_delete_foreign_snapshot_404(client, db) -> None:  # type: ignore[no-untyped-def]
    foreign = Source(owner_id=uuid.uuid4(), kind=SourceKind.snapshot, title="F",
                     status=SnapshotStatus.ready)
    db.add(foreign)
    db.commit()
    assert client.delete(f"/snapshots/{foreign.id}").status_code == 404


def test_delete_is_idempotent_404(client, db) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/capture", json={"url": "https://b.com/y"})
    sid = r.json()["snapshot"]["id"]
    assert client.delete(f"/snapshots/{sid}").status_code == 204
    assert client.delete(f"/snapshots/{sid}").status_code == 404
```

> Note: `SourceFigure` / `Concept` / `SourceConcept` / `Card` constructor kwargs may differ slightly
> — during implementation, open each model and match its required columns (adjust the fixture, not
> the assertions).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_delete_snapshot.py -v`
Expected: FAIL — `405 Method Not Allowed` (no DELETE route) / `ImportError` for `delete_snapshot`.

- [ ] **Step 3: Add `delete_snapshot` to `services/api/app/services/snapshots.py`**

Add imports at the top and the function:

```python
from datetime import UTC, datetime

from gulp_shared.models.card import Card
from gulp_shared.models.concept import SourceConcept
from gulp_shared.models.knowledge_pack import KnowledgePack, PackBlock, PackSection
from gulp_shared.models.pack_block_message import PackBlockMessage
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.source_tag import SourceTag
from sqlalchemy import select, update


def delete_snapshot(db: Session, source: Source) -> None:
    """Cascade soft-delete: the snapshot + every derivative, in one transaction."""
    now = datetime.now(UTC)

    def _stamp(model: type, *conditions: object) -> None:
        db.execute(
            update(model)
            .where(*conditions, model.deleted_at.is_(None))
            .values(deleted_at=now)
        )

    # Resolve the pack tree top-down while its rows are still live.
    pack_ids = list(db.scalars(select(KnowledgePack.id).where(KnowledgePack.snapshot_id == source.id)))
    section_ids = (
        list(db.scalars(select(PackSection.id).where(PackSection.pack_id.in_(pack_ids))))
        if pack_ids else []
    )
    block_ids = (
        list(db.scalars(select(PackBlock.id).where(PackBlock.section_id.in_(section_ids))))
        if section_ids else []
    )

    if block_ids:
        _stamp(PackBlockMessage, PackBlockMessage.block_id.in_(block_ids))
        _stamp(PackBlock, PackBlock.id.in_(block_ids))
    if section_ids:
        _stamp(PackSection, PackSection.id.in_(section_ids))
    if pack_ids:
        _stamp(KnowledgePack, KnowledgePack.id.in_(pack_ids))

    _stamp(Card, Card.source_id == source.id)
    _stamp(SourceFigure, SourceFigure.source_id == source.id)
    _stamp(SourceTag, SourceTag.source_id == source.id)
    _stamp(SourceConcept, SourceConcept.source_id == source.id)

    source.deleted_at = now
    db.commit()
```

- [ ] **Step 4: Add the route to `services/api/app/routers/capture.py`**

Import the service (extend the existing import line) and add the route after `get_snapshot`:

```python
from app.services.snapshots import delete_snapshot, to_out
```

```python
@router.delete("/snapshots/{snapshot_id}", status_code=204)
def delete_snapshot_route(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    delete_snapshot(db, source)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd services/api && uv run pytest tests/test_delete_snapshot.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Run the full api suite + lint (no regressions)**

Run: `cd services/api && uv run pytest -q` then `just lint`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add services/api/app/services/snapshots.py services/api/app/routers/capture.py services/api/tests/test_delete_snapshot.py
git commit -m "feat(api): DELETE /snapshots/{id} — cascade soft-delete snapshot + derivatives"
```

---

### Task 2: Contract — regenerate schema + add `deleteSnapshot` wrapper

**Files:**
- Modify: `packages/api-client/openapi.json` + `packages/api-client/src/schema.gen.ts` (regenerated by `just gen-client`)
- Modify: `packages/api-client/src/index.ts` (add `deleteSnapshot`)

**Interfaces:**
- Produces: `deleteSnapshot(id: string): Promise<void>`.

- [ ] **Step 1: Regenerate the generated contract**

Run: `just gen-client`
Expected: `packages/api-client/src/schema.gen.ts` now shows a `delete` operation under
`"/snapshots/{snapshot_id}"`. (Task 1 must be committed/importable first — the recipe imports the API app.)

- [ ] **Step 2: Add the wrapper to `packages/api-client/src/index.ts`**

After `getSnapshot` (mirrors `deleteCard`):

```typescript
export async function deleteSnapshot(id: string): Promise<void> {
  const { error } = await client.DELETE("/snapshots/{snapshot_id}", {
    params: { path: { snapshot_id: id } },
  });
  if (error) throw new Error("delete snapshot failed");
}
```

- [ ] **Step 3: Typecheck the package**

Run: `pnpm --filter @gulp/api-client exec tsc --noEmit`
Expected: PASS (the `DELETE "/snapshots/{snapshot_id}"` call type-resolves against the new schema).

- [ ] **Step 4: Commit**

```bash
git add packages/api-client/openapi.json packages/api-client/src/schema.gen.ts packages/api-client/src/index.ts
git commit -m "feat(api-client): deleteSnapshot wrapper + regenerated schema"
```

---

### Task 3: Web — `DeleteSnapshotButton` island, wired into inbox + library

**Files:**
- Create: `apps/web/components/snapshot/DeleteSnapshotButton.tsx`
- Modify: `apps/web/components/inbox/InboxRow.tsx`
- Modify: `apps/web/components/library/LibraryList.tsx`

**Interfaces:**
- Consumes: `deleteSnapshot(id)` from `@gulp/api-client` (Task 2).
- Produces: `<DeleteSnapshotButton id={string} confirm?={boolean} />`.

- [ ] **Step 1: Create the shared island**

`apps/web/components/snapshot/DeleteSnapshotButton.tsx`:

```tsx
"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { deleteSnapshot } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";

/** Delete a snapshot (inbox or library). `confirm` gates it behind a two-step inline prompt. */
export function DeleteSnapshotButton({ id, confirm = false }: { id: string; confirm?: boolean }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState(false);

  async function doDelete() {
    setPending(true);
    setError(false);
    try {
      await deleteSnapshot(id);
      router.refresh();
    } catch {
      setError(true);
      setPending(false);
      setConfirming(false);
    }
  }

  const wrap = { display: "inline-flex", gap: 8, alignItems: "center" } as const;

  if (confirming) {
    return (
      <span style={wrap}>
        <span className="t-data">Delete?</span>
        <Button variant="danger" onClick={doDelete} disabled={pending}>
          {pending ? "Deleting…" : "Yes"}
        </Button>
        <Button variant="ghost" onClick={() => setConfirming(false)} disabled={pending}>
          Cancel
        </Button>
      </span>
    );
  }

  return (
    <span style={wrap}>
      <Button
        variant="danger"
        onClick={confirm ? () => setConfirming(true) : doDelete}
        disabled={pending}
        aria-label="Delete"
      >
        {pending ? "Deleting…" : "Delete"}
      </Button>
      {error && (
        <span className="t-data" role="alert" style={{ color: "var(--danger, #c00)" }}>
          Couldn’t delete — try again.
        </span>
      )}
    </span>
  );
}
```

- [ ] **Step 2: Wire into the inbox — immediate delete**

In `apps/web/components/inbox/InboxRow.tsx`, add the import and place the button inside the row's
action group so every row gets it. Replace the action block (lines ~20–29) with:

```tsx
      <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
        {startable ? (
          <>
            <StartButton id={item.id} label="▶ Start" />
            <ExportActions id={item.id} status={item.status} />
          </>
        ) : exportable ? (
          <ExportActions id={item.id} status={item.status} />
        ) : (
          <span className={styles.status}>{statusLabel(item.status)}</span>
        )}
        <DeleteSnapshotButton id={item.id} />
      </span>
```

Add near the other imports:

```tsx
import { DeleteSnapshotButton } from "@/components/snapshot/DeleteSnapshotButton";
```

- [ ] **Step 3: Wire into the library — confirm before delete**

In `apps/web/components/library/LibraryList.tsx`, add the import and the button after `RowBadges`
(line ~59):

```tsx
import { DeleteSnapshotButton } from "@/components/snapshot/DeleteSnapshotButton";
```

```tsx
            <RowBadges mediaType={item.media_type} cardsStatus={item.cards_status} />
            <DeleteSnapshotButton id={item.id} confirm />
```

- [ ] **Step 4: Typecheck + lint the web app**

Run: `just lint`
Expected: PASS (eslint + tsc clean). If a running `next dev` shows unstyled/404 CSS afterward, that's
the known build-clobbers-dev issue (`rm -rf apps/web/.next` + restart) — unrelated to these edits.

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/snapshot/DeleteSnapshotButton.tsx apps/web/components/inbox/InboxRow.tsx apps/web/components/library/LibraryList.tsx
git commit -m "feat(web): delete snapshots from inbox (immediate) and library (confirm)"
```

---

## Self-Review

- **Spec coverage:** service cascade (Task 1 §Step 3), endpoint + ownership/404/idempotent (Task 1 route + tests), `gen-client` + wrapper (Task 2), shared island with confirm-split inbox/library (Task 3). No undo endpoint (out of scope, honored). ✓
- **Placeholders:** none — every step has real code/commands. The fixture-kwargs note in Task 1 is a verify-against-model instruction, not a placeholder.
- **Type consistency:** `delete_snapshot(db, source)` name/signature identical across service, route, and plan prose; `deleteSnapshot(id)` identical across Task 2 and Task 3; `DeleteSnapshotButton` props `{id, confirm?}` consistent between definition and both call sites. ✓
