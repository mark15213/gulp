"""Regression tests for the ownership-audit sweep (spec 2026-07-10 §7): with real
multi-user, every user-facing read/write must be scoped to the current user."""


def _register(auth_client, email):  # type: ignore[no-untyped-def]
    auth_client.cookies.clear()
    auth_client.post("/auth/register", json={"email": email, "password": "hunter2hunter"})


def test_inbox_is_per_user(auth_client) -> None:  # type: ignore[no-untyped-def]
    _register(auth_client, "a@example.com")
    auth_client.post("/capture", json={"url": "https://example.com/x", "captured_via": "in_app"})
    assert auth_client.get("/inbox").json()["count"] == 1  # A sees own capture
    _register(auth_client, "b@example.com")
    assert auth_client.get("/inbox").json()["count"] == 0  # B sees none of A's


def test_library_is_owner_scoped(auth_client) -> None:  # type: ignore[no-untyped-def]
    _register(auth_client, "libA@example.com")
    auth_client.post("/capture", json={"url": "https://example.com/lib", "captured_via": "in_app"})
    _register(auth_client, "libB@example.com")
    assert auth_client.get("/library").json()["count"] == 0


def test_cards_of_foreign_snapshot_404(auth_client) -> None:  # type: ignore[no-untyped-def]
    _register(auth_client, "cardsA@example.com")
    cap = auth_client.post(
        "/capture", json={"url": "https://example.com/y", "captured_via": "in_app"}
    )
    snap_id = cap.json()["snapshot"]["id"]
    assert auth_client.get(f"/snapshots/{snap_id}/cards").status_code == 200  # owner: 200
    _register(auth_client, "cardsB@example.com")
    assert auth_client.get(f"/snapshots/{snap_id}/cards").status_code == 404  # foreign: 404


def test_pack_of_foreign_snapshot_404(auth_client) -> None:  # type: ignore[no-untyped-def]
    _register(auth_client, "packA@example.com")
    cap = auth_client.post(
        "/capture", json={"url": "https://example.com/z", "captured_via": "in_app"}
    )
    snap_id = cap.json()["snapshot"]["id"]
    _register(auth_client, "packB@example.com")
    assert auth_client.get(f"/snapshots/{snap_id}/pack").status_code == 404
