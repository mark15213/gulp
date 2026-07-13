"""Key resolution: env fallback path (BYOK DB path arrives with its own tests)."""

import uuid

import pytest
from gulp_shared.llm.base import LLMNotConfiguredError
from gulp_shared.llm.resolve import resolve_model_config
from gulp_shared.settings import settings


def test_env_fallback_builds_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-env")
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "llm_model", "claude-sonnet-4-6")
    cfg = resolve_model_config(None, uuid.uuid4())  # type: ignore[arg-type]  # db unused for now
    assert cfg.provider == "anthropic" and cfg.model == "claude-sonnet-4-6"
    assert cfg.api_key.get_secret_value() == "sk-env"


def test_no_key_raises_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(LLMNotConfiguredError):
        resolve_model_config(None, uuid.uuid4())  # type: ignore[arg-type]
