def test_unauthenticated_request_is_401(auth_client) -> None:  # type: ignore[no-untyped-def]
    assert auth_client.get("/inbox").status_code == 401


def test_users_cannot_see_each_others_snapshots(auth_client) -> None:  # type: ignore[no-untyped-def]
    # User A registers and captures a snapshot.
    auth_client.post("/auth/register", json={"email": "a@example.com", "password": "hunter2hunter"})
    cap = auth_client.post(
        "/capture", json={"url": "https://example.com/a", "captured_via": "in_app"}
    )
    assert cap.status_code == 200
    snap_id = cap.json()["snapshot"]["id"]

    # Switch to user B.
    auth_client.cookies.clear()
    auth_client.post("/auth/register", json={"email": "b@example.com", "password": "hunter2hunter"})

    # B cannot read A's snapshot.
    assert auth_client.get(f"/snapshots/{snap_id}").status_code == 404
    # B's inbox is empty.
    assert auth_client.get("/inbox").json()["count"] == 0
