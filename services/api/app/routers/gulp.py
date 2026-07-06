"""Gulp session endpoints — thin (docs/05 D4): parse, guard, call service, return.

Transactions commit in the *service* layer (cf. capture.py / cards.py) — every
mutating `app.services.gulp` function ends with `db.commit()`, so the router
never calls `db.commit()` itself.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from gulp_shared.domain import mastery
from gulp_shared.models import Card, GulpSession, ReviewEvent, SessionScope, User
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.gulp import (
    CardMasteryOut,
    NextUp,
    ReviewIn,
    ReviewOut,
    SessionOut,
    SessionStartIn,
    SnoozeIn,
    SummaryOut,
)
from app.services import gulp as svc

router = APIRouter(prefix="/gulp")


@router.post("/sessions", response_model=SessionOut)
def start_session(
    body: SessionStartIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut:
    try:
        sess = svc.compose_session(
            db, user.id, target_minutes=body.target_minutes,
            scope_type=SessionScope(body.scope_type),
        )
    except ValueError as exc:
        raise HTTPException(400, "scope unavailable in v1") from exc
    return svc.to_session_out(db, sess)


@router.get("/sessions/current", response_model=SessionOut | None)
def get_current(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut | None:
    sess = svc.current_session(db, user.id)
    return svc.to_session_out(db, sess) if sess else None


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut:
    sess = db.get(GulpSession, session_id)
    if sess is None or sess.owner_id != user.id:
        raise HTTPException(404, "session not found")
    return svc.to_session_out(db, sess)


@router.post("/sessions/{session_id}/reviews", response_model=ReviewOut)
def review(
    session_id: uuid.UUID,
    body: ReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewOut:
    _require_session_card(db, session_id, user.id, body.card_id)  # owner + membership guard
    try:
        card = svc.record_review(
            db, session_id, user.id, body.card_id, body.grade, body.response
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    nxt_id = svc.next_card_id(db, session_id, user.id)
    ladder = card.ladder.value if card.ladder else mastery.INITIAL_LADDER
    nxt = None
    if nxt_id:
        nc = db.get(Card, uuid.UUID(nxt_id))
        if nc is not None:  # tolerate a card deleted mid-session (C6)
            reason: Literal["retest"] | None = (
                "retest" if _is_retest(db, session_id, nc.id) else None
            )
            nxt = svc.to_session_card_out(db, nc, reason=reason)
    return ReviewOut(
        mastery=CardMasteryOut(
            ladder=ladder, daily=mastery.daily_state(ladder),
            next_review_at=card.next_review_at, interval_days=card.interval_days,
        ),
        next_card=nxt, done=nxt is None,
    )


@router.post("/sessions/{session_id}/snooze", response_model=ReviewOut)
def snooze(
    session_id: uuid.UUID,
    body: SnoozeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewOut:
    _require_session_card(db, session_id, user.id, body.card_id)  # owner + membership guard
    try:
        svc.snooze(db, user.id, body.card_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    nxt_id = svc.next_card_id(db, session_id, user.id)
    nxt = None
    if nxt_id:
        nc = db.get(Card, uuid.UUID(nxt_id))
        if nc is not None:  # tolerate a card deleted mid-session (C6)
            nxt = svc.to_session_card_out(db, nc)
    # snooze doesn't change mastery; echo the snoozed card's current state
    snoozed = db.get(Card, body.card_id)
    ladder = snoozed.ladder.value if snoozed and snoozed.ladder else mastery.INITIAL_LADDER
    return ReviewOut(
        mastery=CardMasteryOut(
            ladder=ladder, daily=mastery.daily_state(ladder),
            next_review_at=snoozed.next_review_at if snoozed else None,
            interval_days=snoozed.interval_days if snoozed else 0.0,
        ),
        next_card=nxt, done=nxt is None,
    )


@router.post("/sessions/{session_id}/complete", response_model=SummaryOut)
def complete(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SummaryOut:
    try:
        svc.complete_session(db, session_id, user.id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    out = svc.summarize(db, session_id, user.id)
    return _summary_out(out)


@router.get("/sessions/{session_id}/summary", response_model=SummaryOut)
def summary(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SummaryOut:
    try:
        out = svc.summarize(db, session_id, user.id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _summary_out(out)


def _summary_out(d: dict[str, int]) -> SummaryOut:
    return SummaryOut(
        reviewed_count=d["reviewed_count"], newly_mastered=d["newly_mastered"],
        still_fuzzy=d["still_fuzzy"], streak_days=d["streak_days"],
        next_up=NextUp(due_count=d["due_count"], inbox_count=d["inbox_count"]),
    )


def _is_retest(db: Session, session_id: uuid.UUID, card_id: uuid.UUID) -> bool:
    stmt = (
        select(ReviewEvent.grade)
        .where(ReviewEvent.session_id == session_id, ReviewEvent.card_id == card_id)
        .order_by(ReviewEvent.at.desc())
        .limit(1)
    )
    row = db.execute(stmt).first()
    return bool(row and row[0].value == "missed")


def _require_session_card(
    db: Session, session_id: uuid.UUID, user_id: uuid.UUID, card_id: uuid.UUID
) -> None:
    """Ownership + membership guard (closes the Task-9 review finding): the
    session must belong to the user, and the card must be a member of that
    session's frozen composition. Repo convention enforces ownership at the
    router boundary (cf. capture.py's / cards.py's `_owned_snapshot`). Raises
    404 (not 403 — don't reveal whether the id exists for another owner)."""
    sess = db.get(GulpSession, session_id)
    if sess is None or sess.owner_id != user_id:
        raise HTTPException(404, "session not found")
    if str(card_id) not in sess.planned_card_ids:
        raise HTTPException(404, "card not in session")
