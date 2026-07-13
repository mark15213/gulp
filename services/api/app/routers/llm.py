"""BYOK LLM settings routes — thin over services.llm_settings."""

from fastapi import APIRouter, Depends, HTTPException
from gulp_shared.llm.base import LLMAuthError, LLMError
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.llm import CredentialIn, CredentialOut, DefaultIn, LLMSettingsOut
from app.services.llm_settings import (
    delete_credential,
    get_llm_settings,
    set_credential,
    set_default,
)

router = APIRouter(prefix="/me/llm")


@router.get("", response_model=LLMSettingsOut)
def get_settings_route(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LLMSettingsOut:
    return get_llm_settings(db, user)


@router.put("/credentials/{provider}", response_model=CredentialOut)
async def put_credential_route(
    provider: str,
    body: CredentialIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CredentialOut:
    try:
        return await set_credential(db, user, provider, body.api_key)
    except LLMAuthError:
        raise HTTPException(status_code=400, detail="invalid_key") from None
    except LLMError:
        raise HTTPException(status_code=404, detail="unknown provider") from None


@router.delete("/credentials/{provider}", status_code=204)
def delete_credential_route(
    provider: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        delete_credential(db, user, provider)
    except LookupError:
        raise HTTPException(status_code=404, detail="credential not found") from None


@router.put("/default", status_code=204)
def put_default_route(
    body: DefaultIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        set_default(db, user, body.provider, body.model)
    except LLMError:
        raise HTTPException(status_code=404, detail="unknown provider") from None
    except ValueError:
        raise HTTPException(status_code=422, detail="unknown model") from None
    except LookupError:
        raise HTTPException(status_code=409, detail="no_credential") from None
