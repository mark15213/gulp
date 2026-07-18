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


def test_tools_list(mcp_client, pat):  # type: ignore[no-untyped-def]
    r = mcp_client.post(
        "/mcp", json=_rpc("tools/list"),
        headers={**HEADERS, "Authorization": f"Bearer {pat}"},
    )
    assert r.status_code == 200
    for name in ("list_jobs", "claim_job", "submit_result", "report_failure"):
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


def test_unknown_path_still_404(mcp_client, pat):  # type: ignore[no-untyped-def]
    # the root mount must not shadow normal 404 semantics for non-/mcp paths
    r = mcp_client.get("/definitely-not-a-route")
    assert r.status_code == 404


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
