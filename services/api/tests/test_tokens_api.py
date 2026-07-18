import uuid

from app.core.pat import TOKEN_PREFIX, resolve_pat
from gulp_shared.models.user import DEV_USER_ID


def test_create_token_returns_plaintext_once(client):  # type: ignore[no-untyped-def]
    r = client.post("/me/tokens", json={"name": "laptop"})
    assert r.status_code == 201
    body = r.json()
    assert body["token"].startswith(TOKEN_PREFIX)
    assert body["prefix"] == body["token"][: len(body["prefix"])]
    assert body["name"] == "laptop"
    # list never re-exposes the plaintext or the hash
    listed = client.get("/me/tokens").json()
    assert len(listed) == 1
    assert "token" not in listed[0] and "token_hash" not in listed[0]


def test_revoke_token(client):  # type: ignore[no-untyped-def]
    tid = client.post("/me/tokens", json={"name": "x"}).json()["id"]
    assert client.delete(f"/me/tokens/{tid}").status_code == 204
    assert client.get("/me/tokens").json() == []
    assert client.delete(f"/me/tokens/{uuid.uuid4()}").status_code == 404


def test_resolve_pat(client, db):  # type: ignore[no-untyped-def]
    token = client.post("/me/tokens", json={"name": "x"}).json()["token"]
    user = resolve_pat(db, token)
    assert user is not None and user.id == DEV_USER_ID
    assert resolve_pat(db, TOKEN_PREFIX + "nope") is None
    assert resolve_pat(db, "not-a-pat") is None
    # revoked → None
    tid = client.get("/me/tokens").json()[0]["id"]
    client.delete(f"/me/tokens/{tid}")
    assert resolve_pat(db, token) is None


def test_resolve_pat_rejects_wrong_scope(client, db):  # type: ignore[no-untyped-def]
    # /mcp only accepts scope "agent"; a token minted with a future scope must not
    # resolve through this middleware-facing path.
    from app.core.pat import hash_token
    from gulp_shared.models.api_token import ApiToken

    token = TOKEN_PREFIX + "someforeignscopetoken"
    db.add(ApiToken(user_id=DEV_USER_ID, name="other", token_hash=hash_token(token),
                    prefix=token[:16], scope="other"))
    db.commit()
    assert resolve_pat(db, token) is None


def test_resolve_pat_touches_last_used(client, db):  # type: ignore[no-untyped-def]
    token = client.post("/me/tokens", json={"name": "x"}).json()["token"]
    resolve_pat(db, token)
    assert client.get("/me/tokens").json()[0]["last_used_at"] is not None
