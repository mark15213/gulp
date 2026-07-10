"""Auth request/response schemas — these become the OpenAPI contract."""

import uuid
from datetime import datetime

from gulp_shared.models.user import Locale
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str | None = None
    locale: Locale = Locale.en


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    locale: Locale
    gulp_session_minutes: int
    created_at: datetime
