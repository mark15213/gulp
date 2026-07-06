"""Cards request/response schemas — these become the OpenAPI contract (docs/05 §4).

The import body is the shared `CardsPayload` contract (gulp_shared.contracts) —
the same schema the worker's generation turn emits.
"""

import uuid
from datetime import datetime
from typing import Literal

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
    # 3-state daily badge (S4 §7, docs/03 §7.2), derived from `ladder` at
    # response time — None until a card is accepted onto the ladder.
    daily: Literal["new", "learning", "known"] | None = None


class CardPatch(BaseModel):
    """Partial update; provided content fields are re-validated per card type."""

    status: CardStatus | None = None
    prompt: str | None = None
    answer: str | None = None
    explanation: str | None = None
    options: list[str] | None = None
