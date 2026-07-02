import pytest
from app.deps import get_db, get_enqueue
from app.main import app
from fastapi.testclient import TestClient


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
    client.enqueue_calls.clear()  # type: ignore[attr-defined]  # drop capture's resolve_metadata enqueue
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


def test_reprocessing_a_processing_snapshot_is_allowed(client: TestClient) -> None:
    """Re-starting a `processing` snapshot must succeed (dead-worker recovery)."""
    sid = _capture(client)
    r1 = client.post(f"/snapshots/{sid}/process")  # -> processing
    assert r1.status_code == 200
    assert r1.json()["status"] == "processing"
    r2 = client.post(f"/snapshots/{sid}/process")  # re-enqueue stranded job
    assert r2.status_code == 200
    assert len(client.enqueue_calls) == 2  # type: ignore[attr-defined]


def test_committed_snapshot_is_not_startable(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    """A snapshot in a non-startable state (e.g. exported, awaiting upload) must 409."""
    import uuid

    from gulp_shared.models.source import SnapshotStatus, Source

    sid = _capture(client)
    # Directly mutate the row so the client sees a non-startable status.
    # `sid` is a string; the ORM Uuid column requires a uuid.UUID object.
    source = db.query(Source).filter_by(id=uuid.UUID(sid)).one()
    source.status = SnapshotStatus.exported
    db.commit()
    r = client.post(f"/snapshots/{sid}/process")
    assert r.status_code == 409
