"""Resolve which model + key a call should use (spec 2026-07-13 §5.1). The
single entry point for API and worker; per-user BYOK credentials land here in
the BYOK slice — until then the env key is the only (dev) path."""

import uuid

from pydantic import SecretStr
from sqlalchemy.orm import Session

from gulp_shared.llm.base import LLMNotConfiguredError, ModelConfig
from gulp_shared.llm.catalog import get_spec
from gulp_shared.settings import settings


def resolve_model_config(db: Session, user_id: uuid.UUID) -> ModelConfig:
    return _env_fallback()


def _env_fallback() -> ModelConfig:
    if not settings.anthropic_api_key:
        raise LLMNotConfiguredError("no LLM credentials configured")
    spec = get_spec(settings.llm_provider)
    return ModelConfig(
        provider=spec.name,
        model=settings.llm_model,
        api_key=SecretStr(settings.anthropic_api_key),
        base_url=spec.base_url,
    )
