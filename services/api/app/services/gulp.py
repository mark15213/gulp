"""Gulp session orchestration (S4 design §4, §6). Thin-router callable."""

import random
import uuid
from datetime import UTC, datetime, timedelta

from gulp_shared.domain import mastery
from gulp_shared.domain import session as compose
from gulp_shared.domain.scheduling import Scheduling, apply_review
from gulp_shared.models import (
    Card,
    CardStatus,
    GulpSession,
    MasteryLadder,
    ReviewEvent,
    ReviewGrade,
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


def _recent_lapse(db: Session, card_id: uuid.UUID) -> bool:
    stmt = (
        select(ReviewEvent.grade)
        .where(ReviewEvent.card_id == card_id)
        .order_by(ReviewEvent.at.desc())
        .limit(2)
    )
    grades = [g for (g,) in db.execute(stmt)]
    return any(g == ReviewGrade.missed for g in grades)


def advance_from_current(
    db: Session, card: Card, sched: Scheduling, grade: str, is_mcq: bool,
) -> str:
    current = card.ladder.value if card.ladder else mastery.INITIAL_LADDER
    return mastery.advance_ladder(
        current, sched, grade, is_mcq=is_mcq,
        recent_lapse=_recent_lapse(db, card.id),
    )


def record_review(
    db: Session, session_id: uuid.UUID, owner_id: uuid.UUID, card_id: uuid.UUID,
    grade: str, response: str | None,
) -> Card:
    card = db.get(Card, card_id)
    if card is None:
        raise ValueError("card_not_found")
    sess = db.get(GulpSession, session_id)
    if sess is None or sess.owner_id != owner_id:
        raise ValueError("session_not_found")
    now = _now()
    db.add(ReviewEvent(
        owner_id=owner_id, session_id=session_id, card_id=card_id,
        grade=ReviewGrade(grade), response=response, at=now,
    ))
    is_mcq = card.card_type.value == "mcq"
    sched = apply_review(
        Scheduling(card.interval_days, card.ease, card.reps, card.lapses),
        grade, is_mcq=is_mcq,
    )
    card.interval_days = sched.interval_days
    card.ease = sched.ease
    card.reps = sched.reps
    card.lapses = sched.lapses
    jitter = random.uniform(-1.0, 1.0)  # ±1-day de-sync (C7)
    card.next_review_at = now + timedelta(days=max(0.0, sched.interval_days + jitter))
    card.last_reviewed_at = now
    card.ladder = MasteryLadder(advance_from_current(db, card, sched, grade, is_mcq))
    card.mastery_updated_at = now
    db.flush()
    return card


def next_card_id(db: Session, session_id: uuid.UUID, owner_id: uuid.UUID) -> str | None:
    sess = db.get(GulpSession, session_id)
    if sess is None:
        return None
    # events this session, by card
    stmt = select(ReviewEvent.card_id, ReviewEvent.grade).where(
        ReviewEvent.session_id == session_id
    ).order_by(ReviewEvent.at)
    last: dict[str, str] = {}
    for cid, g in db.execute(stmt):
        last[str(cid)] = g.value
    # 1) planned cards with no passing event yet
    for cid in sess.planned_card_ids:
        if last.get(cid) in (None, "missed"):
            return cid
    # 2) any missed card (live retest) not yet recovered
    for cid, g in last.items():
        if g == "missed":
            return cid
    return None


def snooze(db: Session, owner_id: uuid.UUID, card_id: uuid.UUID) -> None:
    card = db.get(Card, card_id)
    if card is None:
        raise ValueError("card_not_found")
    card.next_review_at = _now() + timedelta(days=1)
    db.flush()


def complete_session(db: Session, session_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    sess = db.get(GulpSession, session_id)
    if sess is None or sess.owner_id != owner_id:
        raise ValueError("session_not_found")
    sess.status = SessionStatus.complete
    sess.completed_at = _now()
    db.flush()


def _streak_days(db: Session, owner_id: uuid.UUID) -> int:
    stmt = select(GulpSession.completed_at).where(
        GulpSession.owner_id == owner_id,
        GulpSession.status == SessionStatus.complete,
        GulpSession.completed_at.is_not(None),
    ).order_by(GulpSession.completed_at.desc())
    days = sorted({c.date() for (c,) in db.execute(stmt)}, reverse=True)
    if not days:
        return 0
    streak, cursor = 0, _now().date()
    for d in days:
        if d == cursor or (cursor - d).days == 1:
            streak += 1
            cursor = d
        else:
            break
    return streak


def summarize(db: Session, session_id: uuid.UUID, owner_id: uuid.UUID) -> dict[str, int]:
    stmt = select(ReviewEvent.card_id, ReviewEvent.grade).where(
        ReviewEvent.session_id == session_id
    ).order_by(ReviewEvent.at)
    last: dict[str, str] = {}
    for cid, g in db.execute(stmt):
        last[str(cid)] = g.value
    reviewed = len(last)
    still_fuzzy = sum(1 for g in last.values() if g in ("fuzzy", "missed"))
    mastered = 0
    for cid in last:
        c = db.get(Card, uuid.UUID(cid))
        if c and c.ladder and c.ladder.value == "mastered":
            mastered += 1
    now = _now()
    due_count = sum(
        1 for c in _accepted_cards(db, owner_id)
        if c.reps > 0 and mastery.is_due(c.next_review_at, now)
    )
    from app.services.inbox import list_inbox
    return {
        "reviewed_count": reviewed,
        "newly_mastered": mastered,
        "still_fuzzy": still_fuzzy,
        "streak_days": _streak_days(db, owner_id),
        "due_count": due_count,
        "inbox_count": len(list_inbox(db, owner_id)),
    }
