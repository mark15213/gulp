"""BYOK credential + default-model management (spec 2026-07-13 §4). The
plaintext key is validated with a live ping, encrypted at rest, and only ever
surfaced masked."""

from gulp_shared.llm.catalog import PROVIDERS, get_spec
from gulp_shared.llm.crypto import decrypt_key, encrypt_key, mask_key
from gulp_shared.llm.resolve import ping_credential
from gulp_shared.models.user import User
from gulp_shared.models.user_llm_credential import UserLLMCredential
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.llm import CredentialOut, LLMSettingsOut, ModelInfoOut, ProviderCatalogOut


def _catalog() -> list[ProviderCatalogOut]:
    return [
        ProviderCatalogOut(
            provider=spec.name,
            capabilities=sorted(spec.capabilities),
            models=[ModelInfoOut(id=m.id, label=m.label) for m in spec.models],
        )
        for spec in PROVIDERS.values()
    ]


def _find(db: Session, user: User, provider: str) -> UserLLMCredential | None:
    return db.scalar(
        select(UserLLMCredential).where(
            UserLLMCredential.user_id == user.id,
            UserLLMCredential.provider == provider,
            UserLLMCredential.deleted_at.is_(None),
        )
    )


def get_llm_settings(db: Session, user: User) -> LLMSettingsOut:
    rows = db.scalars(
        select(UserLLMCredential)
        .where(UserLLMCredential.user_id == user.id, UserLLMCredential.deleted_at.is_(None))
        .order_by(UserLLMCredential.provider)
    )
    return LLMSettingsOut(
        default_provider=user.llm_provider,
        default_model=user.llm_model,
        credentials=[
            CredentialOut(
                provider=c.provider, masked_key=mask_key(decrypt_key(c.api_key_encrypted))
            )
            for c in rows
        ],
        catalog=_catalog(),
    )


async def set_credential(db: Session, user: User, provider: str, api_key: str) -> CredentialOut:
    get_spec(provider)  # unknown provider -> LLMError -> 404 in the router
    await ping_credential(provider, api_key)  # bad key -> LLMAuthError -> 400
    cred = _find(db, user, provider)
    if cred is None:
        db.add(
            UserLLMCredential(
                user_id=user.id, provider=provider, api_key_encrypted=encrypt_key(api_key)
            )
        )
    else:
        cred.api_key_encrypted = encrypt_key(api_key)
    db.commit()
    return CredentialOut(provider=provider, masked_key=mask_key(api_key))


def delete_credential(db: Session, user: User, provider: str) -> None:
    cred = _find(db, user, provider)
    if cred is None:
        raise LookupError("credential not found")
    db.delete(cred)
    if user.llm_provider == provider:
        user.llm_provider = None
        user.llm_model = None
    db.commit()


def set_default(db: Session, user: User, provider: str, model: str) -> None:
    spec = get_spec(provider)  # unknown provider -> LLMError -> 404
    if model not in {m.id for m in spec.models}:
        raise ValueError(f"unknown model {model!r} for {provider}")
    if _find(db, user, provider) is None:
        raise LookupError(f"no credential stored for {provider}")
    user.llm_provider = provider
    user.llm_model = model
    db.commit()
