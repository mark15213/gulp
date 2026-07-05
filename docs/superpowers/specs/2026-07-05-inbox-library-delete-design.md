# Inbox & Library — delete a snapshot

**Date:** 2026-07-05
**Status:** approved (design)
**Scope:** delete only — no add/create. Capture + processing remain the only way items enter the system.

## Problem

Inbox and library rows are both `Source` snapshots, but there is no way to remove one. The
user needs to delete:

- **Inbox** — any snapshot that hasn't landed in the library yet: the `_TODO` set
  (`queued` / `unprocessed` / `processing` / `exported` / `needs_attention`). Once a snapshot
  reaches `ready` it leaves the inbox for the library, so the inbox offers delete on
  pending/in-flight/failed/exported work — typically with few or no derivatives.
- **Library** — a finished `ready` snapshot **together with its full derivative trail**: the
  knowledge pack/report (sections → blocks → block-messages), cards, figures, tags, concepts.

## Approach: cascade soft-delete

Soft-delete is the house pattern — every model carries `deleted_at` (`TimestampedBase`) and every
read path already filters `deleted_at IS NULL`. Deleting a snapshot stamps `deleted_at = now()` on
the snapshot **and** its derivatives, in **one transaction**. The whole tree disappears from every
list atomically, and it stays recoverable at the DB level.

**Why not hard delete:** a physical `DELETE` of the `sources` row fails today — `Card`,
`SourceTag`, `SourceConcept`, and `KnowledgePack` FKs have no `ON DELETE CASCADE` (only
`SourceFigure` does). Hard delete would need new migrations, be irreversible, and break the
codebase's soft-delete convention. Rejected.

One `DELETE /snapshots/{id}` endpoint serves **both** pages — inbox and library are the same
`Source` type; an inbox item simply has fewer (often zero) derivatives to sweep up.

## Backend

### Service — `services/api/app/services/snapshots.py`

Add `delete_snapshot(db, source)`. It stamps `deleted_at = datetime.now(UTC)` on, in one
transaction (skipping rows already soft-deleted):

1. the `Source` (snapshot) itself
2. `Card` where `source_id == source.id`
3. `SourceFigure` where `source_id == source.id`
4. `SourceTag` where `source_id == source.id`
5. `SourceConcept` where `source_id == source.id`
6. `KnowledgePack` where `snapshot_id == source.id`, and its nested tree:
   `PackSection` (by `pack_id`) → `PackBlock` (by `section_id`) → `PackBlockMessage` (by `block_id`)

Implemented as bulk `update().where(...).values(deleted_at=now)` statements (resolve the pack →
section → block id sets first, then stamp), all before a single `db.commit()`. Idempotent: the
`deleted_at IS NULL` guard means re-running is a no-op.

> The pack row alone already gates read access to its nested tree, so stamping the nested rows is
> hygiene rather than strictly required — but we do it so "delete all derivatives" is literally
> true and no live rows dangle off a deleted snapshot.

### Router — `services/api/app/routers/capture.py`

Add alongside the existing `GET /snapshots/{snapshot_id}`:

```python
@router.delete("/snapshots/{snapshot_id}", status_code=204)
def delete_snapshot_route(snapshot_id, db=Depends(get_db), user=Depends(get_current_user)):
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    delete_snapshot(db, source)
    return Response(status_code=204)
```

Same ownership pattern the co-located `get_snapshot` uses: 404 (not 403) on missing / foreign /
already-deleted, so existence isn't leaked. Returns 204.

### Regenerate the contract

`app/schemas` → OpenAPI → `packages/api-client`. After adding the route, run `just gen-client` so
`deleteSnapshot(id)` is generated. No new Pydantic schema is needed (empty request/response).

## Frontend

The api-client is generated, so the web client calls `deleteSnapshot(id)` (a hand-written wrapper
in `packages/api-client/src/index.ts`, alongside `deleteCard`) — never hand-written fetch in
components.

**One shared client island** — `components/snapshot/DeleteSnapshotButton.tsx` — serves both pages,
following the existing `StartButton` pattern (call the api-client, then `router.refresh()` to
re-render the server-fed list). Both lists are server-rendered (inbox rows are server components;
`LibraryList` is a client component fed by a server page), so `router.refresh()` — not local
optimistic state — is the idiomatic way to reflect the deletion, matching how `StartButton` /
`ExportActions` already work in the inbox. The button owns its own `pending`/`error` state and
shows an inline `role="alert"` message if the delete fails.

Props: `{ id: string; confirm?: boolean }`.

### Library — confirm before delete

`components/library/LibraryList.tsx` — add `<DeleteSnapshotButton id={item.id} confirm />` per row
(after `RowBadges`). `confirm` makes the danger button a two-step inline confirm ("Delete?" →
Yes / Cancel) rather than a modal, because deletion destroys the report + cards.

### Inbox — immediate delete

`components/inbox/InboxRow.tsx` — add `<DeleteSnapshotButton id={item.id} />` (no `confirm`) into
the row's action group. Nothing valuable is lost (task hasn't reached the library), so a single
click deletes, matching the existing card-delete feel.

## Testing

Backend (`services/api/tests/`, mirroring `test_cards_api.py` / `test_pack_mutations.py`):

- `DELETE /snapshots/{id}` on an inbox item → 204; item gone from `GET /inbox`.
- `DELETE /snapshots/{id}` on a library item with a pack + cards + figures + tags + concepts →
  204; gone from `GET /library`; `GET /snapshots/{id}` → 404; `GET /snapshots/{id}/cards` and
  `GET /snapshots/{id}/pack` → 404; the derivative rows carry `deleted_at`.
- Foreign-owner snapshot → 404 (no delete).
- Already-deleted snapshot → 404 (idempotent).

Frontend: exercise the optimistic-removal + rollback-on-error path per the web app's vitest
convention (classic JSX transform — `import React` where JSX is present).

## Out of scope / notes

- **No undo endpoint.** Recovery is DB-level only (soft-delete). If an in-UI Undo is wanted later,
  it's an un-delete endpoint on top of the same `deleted_at` mechanism.
- **Worker mid-flight:** deleting a `processing` snapshot doesn't cancel the worker; any late
  write lands on a soft-deleted (hidden) row. Harmless, accepted.
- **Known smell (not fixed here):** `_owned_snapshot` is duplicated across `pack.py`, `cards.py`,
  `figures.py`. Out of scope; the new route reuses `capture.py`'s inline check to avoid touching
  those files.
