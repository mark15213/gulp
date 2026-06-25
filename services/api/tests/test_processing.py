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
