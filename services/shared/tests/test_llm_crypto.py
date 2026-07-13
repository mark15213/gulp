"""Fernet round-trip + masking for stored provider keys."""

import pytest
from gulp_shared.llm.base import LLMError
from gulp_shared.llm.crypto import decrypt_key, encrypt_key, mask_key


def test_encrypt_decrypt_round_trip() -> None:
    token = encrypt_key("sk-secret-1234")
    assert isinstance(token, bytes) and b"sk-secret" not in token
    assert decrypt_key(token) == "sk-secret-1234"


def test_decrypt_garbage_raises_llm_error() -> None:
    with pytest.raises(LLMError):
        decrypt_key(b"not-a-fernet-token")


def test_mask_key_shows_last_four_only() -> None:
    assert mask_key("sk-abcdefgh1234") == "…1234"
    assert mask_key("abc") == "…"  # too short to reveal anything
