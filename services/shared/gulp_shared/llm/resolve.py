"""Resolve which model + key a call should use (spec 2026-07-13 §5.1). The
single entry point for API and worker: the user's default provider/model plus
their stored BYOK credential; the env key is a dev-only fallback."""

import uuid

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from gulp_shared.llm.base import ChatMessage, LLMNotConfiguredError, ModelConfig
from gulp_shared.llm.catalog import get_spec
from gulp_shared.llm.crypto import decrypt_key
from gulp_shared.models.user import User
from gulp_shared.models.user_llm_credential import UserLLMCredential
from gulp_shared.settings import settings


def resolve_model_config(db: Session, user_id: uuid.UUID) -> ModelConfig:
    user = db.get(User, user_id)
    if user is not None and user.llm_provider and user.llm_model:
        cred = db.scalar(
            select(UserLLMCredential).where(
                UserLLMCredential.user_id == user_id,
                UserLLMCredential.provider == user.llm_provider,
                UserLLMCredential.deleted_at.is_(None),
            )
        )
        if cred is not None:
            spec = get_spec(user.llm_provider)
            return ModelConfig(
                provider=spec.name,
                model=user.llm_model,
                api_key=SecretStr(decrypt_key(cred.api_key_encrypted)),
                base_url=spec.base_url,
            )
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


async def ping_credential(provider_name: str, api_key: str) -> None:
    """Cheapest possible live call; raises LLMAuthError when the key is bad."""
    spec = get_spec(provider_name)
    cfg = ModelConfig(
        provider=spec.name,
        model=spec.models[0].id,
        api_key=SecretStr(api_key),
        base_url=spec.base_url,
        max_tokens=1,
    )
    events = spec.adapter.stream_chat(
        system=None,
        messages=[ChatMessage(role="user", content="ping")],
        tools=None,
        config=cfg,
    )
    async for _ in events:
        break
