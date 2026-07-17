"""PAT schemas — the plaintext appears exactly once, on the create response."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None


class TokenCreatedOut(TokenOut):
    token: str
