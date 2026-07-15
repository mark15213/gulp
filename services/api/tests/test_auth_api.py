from gulp_shared.settings import settings


def test_register_sets_cookie_and_returns_user(auth_client) -> None:  # type: ignore[no-untyped-def]
    resp = auth_client.post(
        "/auth/register",
        json={"email": "New@Example.com", "password": "hunter2hunter", "display_name": "New"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"  # lowercased
    assert "password_hash" not in body
    assert "gulp_session" in resp.cookies


def test_register_rejects_duplicate_email(auth_client) -> None:  # type: ignore[no-untyped-def]
    payload = {"email": "dup@example.com", "password": "hunter2hunter"}
    assert auth_client.post("/auth/register", json=payload).status_code == 201
    resp = auth_client.post("/auth/register", json=payload)
    assert resp.status_code == 409


def test_register_rejects_short_password(auth_client) -> None:  # type: ignore[no-untyped-def]
    resp = auth_client.post("/auth/register", json={"email": "a@b.com", "password": "short"})
    assert resp.status_code == 422


def test_login_then_me(auth_client) -> None:  # type: ignore[no-untyped-def]
    auth_client.post(
        "/auth/register", json={"email": "me@example.com", "password": "hunter2hunter"}
    )
    auth_client.cookies.clear()
    login = auth_client.post(
        "/auth/login", json={"email": "me@example.com", "password": "hunter2hunter"}
    )
    assert login.status_code == 200
    me = auth_client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "me@example.com"


def test_login_wrong_password_is_401_generic(auth_client) -> None:  # type: ignore[no-untyped-def]
    auth_client.post("/auth/register", json={"email": "x@example.com", "password": "hunter2hunter"})
    resp = auth_client.post("/auth/login", json={"email": "x@example.com", "password": "WRONG"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid email or password"


def test_logout_clears_session(auth_client) -> None:  # type: ignore[no-untyped-def]
    auth_client.post(
        "/auth/register", json={"email": "out@example.com", "password": "hunter2hunter"}
    )
    assert auth_client.get("/auth/me").status_code == 200
    auth_client.post("/auth/logout")
    auth_client.cookies.clear()  # server cleared it; drop any client copy
    assert auth_client.get("/auth/me").status_code == 401


def test_register_requires_invite_code_when_configured(auth_client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "invite_code", "5566")
    resp = auth_client.post(
        "/auth/register",
        json={"email": "no-invite@example.com", "password": "hunter2hunter"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invite_required"


def test_register_rejects_wrong_invite_code(auth_client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "invite_code", "5566")
    resp = auth_client.post(
        "/auth/register",
        json={
            "email": "bad-invite@example.com",
            "password": "hunter2hunter",
            "invite_code": "0000",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invite_required"


def test_register_accepts_correct_invite_code(auth_client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "invite_code", "5566")
    resp = auth_client.post(
        "/auth/register",
        json={
            "email": "good-invite@example.com",
            "password": "hunter2hunter",
            "invite_code": "5566",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "good-invite@example.com"


def test_register_open_when_invite_code_empty(auth_client) -> None:  # type: ignore[no-untyped-def]
    # Default settings.invite_code == "" -> registration stays open (no code needed).
    resp = auth_client.post(
        "/auth/register",
        json={"email": "open@example.com", "password": "hunter2hunter"},
    )
    assert resp.status_code == 201
