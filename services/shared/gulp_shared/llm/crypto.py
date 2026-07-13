"""Fernet encryption for stored provider keys (spec 2026-07-13 §4.2). Keyed by
`settings.credential_secret` — independent of `auth_secret` so they rotate
independently. Plaintext exists in memory only at call time."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from gulp_shared.llm.base import LLMError
from gulp_shared.settings import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.credential_secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_key(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt_key(token: bytes) -> str:
    try:
        return _fernet().decrypt(token).decode()
    except InvalidToken as exc:
        raise LLMError("stored credential cannot be decrypted") from exc


def mask_key(plaintext: str) -> str:
    if len(plaintext) <= 4:
        return "…"
    return f"…{plaintext[-4:]}"
