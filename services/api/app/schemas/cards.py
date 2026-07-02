"""Cards request/response schemas — these become the OpenAPI contract (docs/05 §4).

The import body is the shared `CardsPayload` contract (gulp_shared.contracts) —
the same schema the worker's generation turn emits.
"""

import uuid
from datetime import datetime

from gulp_shared.models.card import CardOrigin, CardStatus, CardType
from pydantic import BaseModel, ConfigDict


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    card_type: CardType
    prompt: str
    answer: str | None
    explanation: str | None
    options: list[str] | None
    origin: CardOrigin
    status: CardStatus
    created_at: datetime
    updated_at: datetime


class CardPatch(BaseModel):
    """Partial update; provided content fields are re-validated per card type."""

    status: CardStatus | None = None
    prompt: str | None = None
    answer: str | None = None
    explanation: str | None = None
    options: list[str] | None = None
