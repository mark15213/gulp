import asyncio

import pytest
from app.deps import get_db
from app.main import app
from app.mcp import deps as mcp_deps
from fastapi.testclient import TestClient
from gulp_shared.models import (
    AgentJob,
    AgentJobKind,
    AgentJobState,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.user import DEV_USER_ID

HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def _rpc(method: str, params: dict | None = None) -> dict:
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}


def _tool_result(response):  # type: ignore[no-untyped-def]
    """The tool's own return value, out of the JSON-RPC + MCP envelope. FastMCP
    puts a dict-annotated return straight into structuredContent but wraps a
    non-object one (list_jobs' list) under a "result" key — and repeats either as
    serialized text in `content`, so assert on this rather than on r.text."""
    structured = response.json()["result"]["structuredContent"]
    return structured["result"] if list(structured) == ["result"] else structured


@pytest.fixture
def pat(db, owner):  # type: ignore[no-untyped-def]
    from app.services.tokens import create_token

    _, plaintext = create_token(db, owner, "test")
    return plaintext


@pytest.fixture
def mcp_client(db, monkeypatch):  # type: ignore[no-untyped-def]
    # MCP tools bypass FastAPI DI; swap their seams instead.
    monkeypatch.setattr(mcp_deps, "session_factory", lambda: db)
    monkeypatch.setattr(mcp_deps, "enqueue", lambda *a: None)
    app.dependency_overrides[get_db] = lambda: db
    # lifespan MUST run (it starts the MCP session manager) → context-managed client
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_mcp_requires_pat(mcp_client):  # type: ignore[no-untyped-def]
    r = mcp_client.post("/mcp", json=_rpc("tools/list"), headers=HEADERS)
    assert r.status_code == 401
    r = mcp_client.post(
        "/mcp", json=_rpc("tools/list"),
        headers={**HEADERS, "Authorization": "Bearer gulp_pat_bogus"},
    )
    assert r.status_code == 401


def test_mcp_rejects_oversized_body(mcp_client, pat):  # type: ignore[no-untyped-def]
    r = mcp_client.post(
        "/mcp", content=b"x",
        headers={**HEADERS, "Authorization": f"Bearer {pat}",
                 "Content-Length": str(6 * 1024 * 1024)},
    )
    assert r.status_code == 413


def test_mcp_rejects_oversized_chunked_body(mcp_client, pat):  # type: ignore[no-untyped-def]
    # No Content-Length (streamed/chunked), so the fast-path can't help — the
    # wrapped `receive` must count cumulative body bytes and abort past the cap.
    def _chunks():  # type: ignore[no-untyped-def]
        for _ in range(6):
            yield b"x" * (1024 * 1024)  # 6 MB total, > 5 MB cap

    r = mcp_client.post(
        "/mcp", content=_chunks(),
        headers={**HEADERS, "Authorization": f"Bearer {pat}"},
    )
    assert r.status_code == 413


def test_tools_list(mcp_client, pat):  # type: ignore[no-untyped-def]
    r = mcp_client.post(
        "/mcp", json=_rpc("tools/list"),
        headers={**HEADERS, "Authorization": f"Bearer {pat}"},
    )
    assert r.status_code == 200
    for name in ("list_jobs", "publish_job", "claim_job", "submit_result", "report_failure"):
        assert name in r.text


def test_list_jobs_tool_scoped_to_pat_owner(mcp_client, pat, db):  # type: ignore[no-untyped-def]
    s = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="MCP Paper",
               status=SnapshotStatus.exported, content_body="b")
    db.add(s)
    db.commit()
    db.add(AgentJob(owner_id=DEV_USER_ID, snapshot_id=s.id,
                    kind=AgentJobKind.digest, state=AgentJobState.pending))
    db.commit()
    r = mcp_client.post(
        "/mcp", json=_rpc("tools/call", {"name": "list_jobs", "arguments": {}}),
        headers={**HEADERS, "Authorization": f"Bearer {pat}"},
    )
    assert r.status_code == 200
    assert "MCP Paper" in r.text


def test_publish_job_tool_turns_a_capture_into_a_job(mcp_client, pat, db):  # type: ignore[no-untyped-def]
    """The zero-click path: an agent discovers an unrouted capture and publishes
    it itself. Exercised end-to-end because the tool wrappers pass their args
    positionally through _offload — a service signature this layer disagrees with
    is invisible to the service-level tests."""
    s = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="Unrouted Paper",
               status=SnapshotStatus.unprocessed)
    db.add(s)
    db.commit()
    listed = mcp_client.post(
        "/mcp",
        json=_rpc("tools/call",
                  {"name": "list_jobs", "arguments": {"include_candidates": True}}),
        headers={**HEADERS, "Authorization": f"Bearer {pat}"},
    )
    assert [(c["state"], c["title"], c["job_id"]) for c in _tool_result(listed)] == [
        ("unpublished", "Unrouted Paper", None)
    ]
    r = mcp_client.post(
        "/mcp",
        json=_rpc("tools/call",
                  {"name": "publish_job", "arguments": {"snapshot_id": str(s.id)}}),
        headers={**HEADERS, "Authorization": f"Bearer {pat}"},
    )
    assert r.status_code == 200
    published = _tool_result(r)
    assert published["state"] == "building" and published["retry_after_s"] == 30
    # …and it is a real job now, listed without asking for candidates.
    plain = mcp_client.post(
        "/mcp", json=_rpc("tools/call", {"name": "list_jobs", "arguments": {}}),
        headers={**HEADERS, "Authorization": f"Bearer {pat}"},
    )
    assert [(j["job_id"], j["state"]) for j in _tool_result(plain)] == [
        (published["job_id"], "building")
    ]


def test_unknown_path_still_404(mcp_client, pat):  # type: ignore[no-untyped-def]
    # the root mount must not shadow normal 404 semantics for non-/mcp paths
    r = mcp_client.get("/definitely-not-a-route")
    assert r.status_code == 404


def test_enqueueing_tool_runs_off_the_event_loop(mcp_client, pat, db, monkeypatch):  # type: ignore[no-untyped-def]
    """The real `enqueue` (app/core/queue.py) drives arq through asyncio.run(),
    which raises inside a running event loop. FastMCP calls a *sync* tool fn
    inline on the ASGI loop, so the tool body must be pushed off it — this is
    the live-e2e failure (every digest submit + every archive rebuild) that the
    no-op enqueue double in the other tests hides. The stub below mirrors the
    real enqueue's one relevant property: it calls asyncio.run."""

    def enqueue_like_arq(*args: object) -> None:
        async def _go() -> None:
            return None

        asyncio.run(_go())

    monkeypatch.setattr(mcp_deps, "enqueue", enqueue_like_arq)
    s = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="No Archive",
               status=SnapshotStatus.exported, content_body="b")
    db.add(s)
    db.commit()
    job = AgentJob(owner_id=DEV_USER_ID, snapshot_id=s.id,
                   kind=AgentJobKind.digest, state=AgentJobState.pending)
    db.add(job)
    db.commit()
    # No archive on disk → claim falls into _rebuild, which enqueues.
    r = mcp_client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": "claim_job", "arguments": {"job_id": str(job.id)}}),
        headers={**HEADERS, "Authorization": f"Bearer {pat}"},
    )
    assert r.status_code == 200
    assert "rebuilding" in r.text
    assert "running event loop" not in r.text


def test_get_stream_does_not_break_the_logging_middleware(mcp_client, pat):  # type: ignore[no-untyped-def]
    """An MCP client opens `GET /mcp` for the server→client stream during its
    handshake. Starlette's BaseHTTPMiddleware (which `log_requests` is) cannot
    wrap that streaming response — it raises "No response returned." and turns
    every real client connection into a logged 500. curl-based tests never see
    it because curl only POSTs."""
    r = mcp_client.get(
        "/mcp",
        headers={"Accept": "text/event-stream", "Authorization": f"Bearer {pat}"},
    )
    assert r.status_code < 500


def test_tool_returns_structured_error_envelope(mcp_client, pat):  # type: ignore[no-untyped-def]
    # An AgentJobUnavailable is a protocol rejection, not a transport failure:
    # the tool must return {"error": {code, message}} at HTTP 200 (exercises the
    # tool's except-branch + _error mapping), not raise through the RPC layer.
    r = mcp_client.post(
        "/mcp",
        json=_rpc("tools/call", {"name": "claim_job", "arguments": {"job_id": "nope"}}),
        headers={**HEADERS, "Authorization": f"Bearer {pat}"},
    )
    assert r.status_code == 200
    assert "not_found" in r.text
