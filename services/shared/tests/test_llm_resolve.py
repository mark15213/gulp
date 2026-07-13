"""Key resolution: BYOK credential first, env fallback second, else error."""

import uuid

import pytest
from gulp_shared.db import Base
from gulp_shared.llm import catalog
from gulp_shared.llm.base import LLMNotConfiguredError, TextDelta
from gulp_shared.llm.crypto import encrypt_key
from gulp_shared.llm.resolve import ping_credential, resolve_model_config
from gulp_shared.models.user import User
from gulp_shared.models.user_llm_credential import UserLLMCredential
from gulp_shared.settings import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_env_fallback_builds_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-env")
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "llm_model", "claude-sonnet-4-6")
    cfg = resolve_model_config(_session(), uuid.uuid4())
    assert cfg.provider == "anthropic" and cfg.model == "claude-sonnet-4-6"
    assert cfg.api_key.get_secret_value() == "sk-env"


def test_no_key_raises_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(LLMNotConfiguredError):
        resolve_model_config(_session(), uuid.uuid4())


def test_byok_credential_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _session()
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-env")
    user = User(display_name="C", llm_provider="deepseek", llm_model="deepseek-chat")
    s.add(user)
    s.flush()
    s.add(
        UserLLMCredential(
            user_id=user.id, provider="deepseek", api_key_encrypted=encrypt_key("sk-user")
        )
    )
    s.flush()
    cfg = resolve_model_config(s, user.id)
    assert cfg.provider == "deepseek" and cfg.model == "deepseek-chat"
    assert cfg.api_key.get_secret_value() == "sk-user"
    assert cfg.base_url == "https://api.deepseek.com"
    s.close()


def test_default_without_credential_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _session()
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-env")
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    user = User(display_name="D", llm_provider="qwen", llm_model="qwen-plus")  # no key row
    s.add(user)
    s.flush()
    assert resolve_model_config(s, user.id).api_key.get_secret_value() == "sk-env"
    s.close()


async def test_ping_credential_hits_stream_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class PingFake:
        async def complete_json(self, **kw):  # type: ignore[no-untyped-def]
            raise AssertionError("ping must stream")

        async def stream_chat(self, *, system, messages, tools, config):  # type: ignore[no-untyped-def]
            calls.append(config.api_key.get_secret_value())
            yield TextDelta(text="ok")

    spec = catalog.PROVIDERS["deepseek"]
    fake_spec = catalog.ProviderSpec(
        name=spec.name,
        adapter=PingFake(),
        base_url=spec.base_url,
        capabilities=spec.capabilities,
        models=spec.models,
    )
    monkeypatch.setitem(catalog.PROVIDERS, "deepseek", fake_spec)
    await ping_credential("deepseek", "sk-ping")
    assert calls == ["sk-ping"]
