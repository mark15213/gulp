"""Gulp session orchestration (S4 design §4, §6). Thin-router callable."""

import uuid
from datetime import UTC, datetime

from gulp_shared.domain import mastery
from gulp_shared.domain import session as compose
from gulp_shared.models import (
    Card,
    CardStatus,
    GulpSession,
    MasteryLadder,
    SessionScope,
    SessionStatus,
    Source,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

_WIRED_SCOPES = {SessionScope.daily, SessionScope.at_risk, SessionScope.free_explore}


def _now() -> datetime:
    return datetime.now(UTC)


def init_scheduling_on_accept(card: Card) -> None:
    if card.ladder is not None:
        return
    now = _now()
    card.ladder = MasteryLadder.read
    card.interval_days = 0.0
    card.ease = 2.3
    card.reps = 0
    card.lapses = 0
    card.next_review_at = now
    card.mastery_updated_at = now


def _accepted_cards(db: Session, owner_id: uuid.UUID) -> list[Card]:
    stmt = (
        select(Card)
        .join(Source, Card.source_id == Source.id)
        .where(
            Source.owner_id == owner_id,
            Source.deleted_at.is_(None),
            Card.deleted_at.is_(None),
            Card.status == CardStatus.accepted,
        )
    )
    return list(db.scalars(stmt))


def compose_session(
    db: Session, owner_id: uuid.UUID, *,
    target_minutes: int | None, scope_type: SessionScope,
) -> GulpSession:
    if scope_type not in _WIRED_SCOPES:
        raise ValueError("scope_unavailable")
    minutes = target_minutes or 5
    now = _now()
    cards = _accepted_cards(db, owner_id)

    due_ar, due, new = [], [], []
    for c in cards:
        ref = compose.CardRef(card_id=str(c.id), source_id=str(c.source_id))
        if c.reps == 0:
            new.append(ref)
        elif mastery.is_due(c.next_review_at, now):
            if mastery.is_at_risk(c.next_review_at, c.interval_days, now):
                due_ar.append(ref)
            else:
                due.append(ref)

    planned = compose.prioritize(due_ar, due, new, [], compose.cap_for(minutes))

    sess = GulpSession(
        owner_id=owner_id, scope_type=scope_type, target_minutes=minutes,
        planned_card_ids=[r.card_id for r in planned],
        status=SessionStatus.active, started_at=now,
    )
    db.add(sess)
    db.flush()
    return sess


def current_session(db: Session, owner_id: uuid.UUID) -> GulpSession | None:
    stmt = (
        select(GulpSession)
        .where(
            GulpSession.owner_id == owner_id,
            GulpSession.status.in_([SessionStatus.active, SessionStatus.abandoned]),
        )
        .order_by(GulpSession.created_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()
