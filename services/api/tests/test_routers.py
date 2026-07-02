import pytest
from app.deps import get_db, get_enqueue
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client(db):
    calls = []
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: calls.append(a))
    c = TestClient(app)
    c.enqueue_calls = calls  # type: ignore[attr-defined]
    yield c
    app.dependency_overrides.clear()


def test_post_capture_creates_an_unprocessed_snapshot(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/capture", json={"url": "https://a.com/x", "captured_via": "paste"})
    assert r.status_code == 200
    body = r.json()
    assert body["duplicate"] is False
    assert body["snapshot"]["status"] == "unprocessed"
    assert body["snapshot"]["media_type"] == "webpage"
    # capturing a link enqueues a metadata-resolution job (real title + media type)
    assert client.enqueue_calls == [("resolve_metadata", body["snapshot"]["id"])]


def test_post_capture_duplicate_url_flags_duplicate(client):
    client.post("/capture", json={"url": "https://a.com/dup"})
    r = client.post("/capture", json={"url": "https://a.com/dup?utm_x=1"})
    assert r.json()["duplicate"] is True


def test_get_inbox_lists_captures(client):
    client.post("/capture", json={"url": "https://a.com/1"})
    r = client.get("/inbox")
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_get_snapshot_404_for_unknown_id(client):
    r = client.get("/snapshots/00000000-0000-0000-0000-0000000000ff")
    assert r.status_code == 404
