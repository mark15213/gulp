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


def test_capturing_a_link_enqueues_resolve_metadata(client):  # type: ignore[no-untyped-def]
    r = client.post("/capture", json={"url": "https://arxiv.org/pdf/2606.27377"})
    assert r.status_code == 200
    sid = r.json()["snapshot"]["id"]
    assert ("resolve_metadata", sid) in client.enqueue_calls


def test_capturing_a_note_does_not_enqueue(client):  # type: ignore[no-untyped-def]
    r = client.post("/capture", json={"text": "just a note"})
    assert r.status_code == 200
    assert client.enqueue_calls == []
