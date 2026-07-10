"""Article-chat contract — becomes the OpenAPI types the web client reads."""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    block_refs: list[uuid.UUID]
    created_at: datetime.datetime


class MessageCreate(BaseModel):
    content: str
    block_refs: list[uuid.UUID] = []
