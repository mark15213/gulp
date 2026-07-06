"""Card supply + review logic (spec §④/§⑤): generate trigger, import, list, patch, delete."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, cast

from gulp_shared.contracts.cards import CardDraft, CardsPayload
from gulp_shared.domain import mastery
from gulp_shared.models.card import Card, CardOrigin, CardStatus
from gulp_shared.models.knowledge_pack import KnowledgePack, PackStatus
from gulp_shared.models.source import CardsStatus, Source
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.cards import CardOut, CardPatch
from app.services.gulp import init_scheduling_on_accept

_Daily = Literal["new", "learning", "known"]


class NoReadyPackError(Exception):
    """Generation needs a ready pack to draft from."""


class GenerationInFlightError(Exception):
    """A generation job is already running for this source."""


def to_card_out(card: Card) -> CardOut:
    """Build the response schema, deriving the daily badge from `ladder`
    (S4 §7) — None until the card is accepted onto the mastery ladder."""
    out = CardOut.model_validate(card)
    out.daily = cast(_Daily, mastery.daily_state(card.ladder.value)) if card.ladder else None
    return out


def start_card_generation(db: Session, source: Source, enqueue: Callable[..., None]) -> None:
    pack = db.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == source.id))
    if pack is None or pack.status is not PackStatus.ready:
        raise NoReadyPackError("no ready pack to draft cards from — run Start first")
    if source.cards_status is CardsStatus.generating:
        raise GenerationInFlightError("card generation is already running")
    source.cards_status = CardsStatus.generating
    db.commit()
    enqueue("generate_cards", str(source.id))


def start_cards_export(db: Session, source: Source, enqueue: Callable[..., None]) -> None:
    """Enqueue building a card-generation job archive (needs a ready pack)."""
    pack = db.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == source.id))
    if pack is None or pack.status is not PackStatus.ready:
        raise NoReadyPackError("no ready pack to build a cards job from — run Start first")
    enqueue("build_cards_export", str(source.id))


def import_cards(db: Session, source: Source, payload: CardsPayload) -> list[Card]:
    rows = [
        Card(
            source_id=source.id,
            card_type=draft.card_type,
            prompt=draft.prompt,
            answer=draft.answer,
            explanation=draft.explanation,
            options=draft.options,
            origin=CardOrigin.imported,
        )
        for draft in payload.cards
    ]
    db.add_all(rows)
    db.commit()
    return rows


def list_cards(db: Session, source: Source) -> list[Card]:
    return list(
        db.scalars(
            select(Card)
            .where(Card.source_id == source.id, Card.deleted_at.is_(None))
            .order_by(Card.created_at, Card.id)
        )
    )


def get_card(db: Session, source: Source, card_id: uuid.UUID) -> Card:
    card = db.get(Card, card_id)
    if card is None or card.source_id != source.id or card.deleted_at is not None:
        raise LookupError("card not found")
    return card


def update_card(db: Session, card: Card, patch: CardPatch) -> Card:
    provided = patch.model_fields_set
    if provided & {"prompt", "answer", "explanation", "options"}:
        merged = CardDraft.model_validate(  # raises ValidationError -> 422
            {
                "card_type": card.card_type,
                "prompt": patch.prompt if "prompt" in provided else card.prompt,
                "answer": patch.answer if "answer" in provided else card.answer,
                "explanation": (
                    patch.explanation if "explanation" in provided else card.explanation
                ),
                "options": patch.options if "options" in provided else card.options,
            }
        )
        card.prompt = merged.prompt
        card.answer = merged.answer
        card.explanation = merged.explanation
        card.options = merged.options
    if patch.status is not None:
        card.status = patch.status
        if patch.status is CardStatus.accepted:
            init_scheduling_on_accept(card)
    db.commit()
    return card


def delete_card(db: Session, card: Card) -> None:
    card.deleted_at = datetime.now(UTC)
    db.commit()
