from app.core.security import hash_password, new_session_token, verify_password


def test_hash_password_round_trips() -> None:
    h = hash_password("s3cret-password")
    assert h != "s3cret-password"
    assert h.startswith("$argon2id$")
    assert verify_password("s3cret-password", h) is True


def test_verify_rejects_wrong_password() -> None:
    h = hash_password("s3cret-password")
    assert verify_password("wrong", h) is False


def test_verify_rejects_malformed_hash() -> None:
    assert verify_password("anything", "not-a-hash") is False


def test_new_session_token_is_unique_and_long() -> None:
    a, b = new_session_token(), new_session_token()
    assert a != b
    assert len(a) >= 32
