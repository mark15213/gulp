"""Batch Start — the Inbox `Start N` bar (spec 2026-08-01 §3.2)."""

import uuid

from app.deps import get_enqueue
from app.main import app
from app.schemas.capture import CaptureRequest
from app.services.capture import create_snapshot
from gulp_shared.models import Source, SourceKind
from gulp_shared.models.source import SnapshotStatus
from gulp_shared.models.user import DEV_USER_ID


def test_batch_starts_many_at_once(client, db):
    calls: list[tuple] = []
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: calls.append(a))
    a, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/1"))
    b, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/2"))

    r = client.post("/snapshots/process-batch", json={"ids": [str(a.id), str(b.id)]})
    assert r.status_code == 200
    body = r.json()
    assert set(body["started"]) == {str(a.id), str(b.id)}
    assert body["skipped"] == []
    assert sorted(calls) == sorted(
        [("process_snapshot", str(a.id)), ("process_snapshot", str(b.id))]
    )


def test_one_bad_id_does_not_fail_the_batch(client, db):
    ok, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/ok"))
    stuck, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/stuck"))
    stuck.status = SnapshotStatus.exported  # not startable
    db.commit()
    missing = uuid.uuid4()

    body = client.post(
        "/snapshots/process-batch",
        json={"ids": [str(ok.id), str(stuck.id), str(missing)]},
    ).json()

    assert body["started"] == [str(ok.id)]
    reasons = {s["id"]: s["reason"] for s in body["skipped"]}
    assert set(reasons) == {str(stuck.id), str(missing)}
    assert "not startable" in reasons[str(stuck.id)]
    assert "not found" in reasons[str(missing)]


def test_batch_is_scoped_to_the_owner(client, db):
    theirs = Source(
        owner_id=uuid.uuid4(),
        kind=SourceKind.snapshot,
        title="Not yours",
        status=SnapshotStatus.unprocessed,
        origin_url="https://elsewhere.example/1",
    )
    db.add(theirs)
    db.commit()

    body = client.post("/snapshots/process-batch", json={"ids": [str(theirs.id)]}).json()
    assert body["started"] == []
    assert body["skipped"][0]["reason"] == "snapshot not found"
    db.refresh(theirs)
    assert theirs.status == SnapshotStatus.unprocessed  # untouched
