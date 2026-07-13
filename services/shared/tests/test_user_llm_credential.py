"""BYOK credential rows + the user's default provider/model columns."""

import pytest
from gulp_shared.db import Base
from gulp_shared.models.user import User
from gulp_shared.models.user_llm_credential import UserLLMCredential
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_credential_row_and_user_defaults() -> None:
    s = _session()
    user = User(display_name="A")
    s.add(user)
    s.flush()
    assert user.llm_provider is None and user.llm_model is None
    cred = UserLLMCredential(user_id=user.id, provider="deepseek", api_key_encrypted=b"tok")
    s.add(cred)
    s.flush()
    assert cred.id is not None and cred.created_at is not None
    user.llm_provider, user.llm_model = "deepseek", "deepseek-chat"
    s.flush()
    s.close()


def test_one_row_per_user_provider() -> None:
    s = _session()
    user = User(display_name="B")
    s.add(user)
    s.flush()
    s.add(UserLLMCredential(user_id=user.id, provider="openai", api_key_encrypted=b"a"))
    s.flush()
    s.add(UserLLMCredential(user_id=user.id, provider="openai", api_key_encrypted=b"b"))
    with pytest.raises(IntegrityError):
        s.flush()
    s.close()
