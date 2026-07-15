"""Article-chat contract — becomes the OpenAPI types the web client reads."""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    block_refs: list[uuid.UUID]
    created_at: datetime.datetime


class MessageCreate(BaseModel):
    content: str
    block_refs: list[uuid.UUID] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None

    @model_validator(mode="after")
    def provider_and_model_are_a_pair(self) -> "MessageCreate":
        if (self.provider is None) != (self.model is None):
            raise ValueError("provider and model must be selected together")
        return self
