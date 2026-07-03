"""CORS must accept the localhost <-> 127.0.0.1 twin of web_origin.

Browsers treat `localhost` and `127.0.0.1` as distinct origins, and CORS is
exact-match. If only one is allowed, a capture POST from the other origin is
blocked in the browser and silently lost — the bug this guards against.
"""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _preflight(origin: str):
    return client.options(
        "/capture",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_preflight_allows_localhost() -> None:
    r = _preflight("http://localhost:3000")
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_preflight_allows_127_0_0_1_twin() -> None:
    r = _preflight("http://127.0.0.1:3000")
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
