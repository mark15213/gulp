"""Today rollup — read-only aggregate of cards + library + inbox."""

import uuid
from datetime import UTC, datetime

from gulp_shared.domain import mastery
from gulp_shared.models.card import Card, CardStatus
from gulp_shared.models.source import Source
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.schemas.today import MasteryTally, TodayDigestItem, TodayOut
from app.services.gulp import _accepted_cards, _aware
from app.services.inbox import list_inbox
from app.services.library import list_library
from app.services.snapshots import to_out

DIGEST_LIMIT = 3
RECENT_LIMIT = 3


def _accepted_counts(db: Session, owner_id: uuid.UUID) -> dict[uuid.UUID, int]:
    stmt = (
        select(Card.source_id, func.count(Card.id))
        .join(Source, Card.source_id == Source.id)
        .where(
            Source.owner_id == owner_id,
            Source.deleted_at.is_(None),
            Card.deleted_at.is_(None),
            Card.status == CardStatus.accepted,
        )
        .group_by(Card.source_id)
    )
    return {sid: n for sid, n in db.execute(stmt)}


def _gulp_counts(db: Session, owner_id: uuid.UUID) -> tuple[int, int, dict[str, int]]:
    now = datetime.now(UTC)
    tally = {"new": 0, "learning": 0, "known": 0, "at_risk": 0}
    due = new = 0
    for c in _accepted_cards(db, owner_id):
        ladder = c.ladder.value if c.ladder else "read"
        tally[mastery.daily_state(ladder)] += 1
        if c.reps == 0:
            new += 1
        elif mastery.is_due(_aware(c.next_review_at), now):
            due += 1
        if mastery.is_at_risk(_aware(c.next_review_at), c.interval_days, now):
            tally["at_risk"] += 1
    return due, new, tally


def today_summary(db: Session, owner_id: uuid.UUID) -> TodayOut:
    counts = _accepted_counts(db, owner_id)
    ready = list_library(db, owner_id)
    inbox = list_inbox(db, owner_id)
    due_count, new_count, tally = _gulp_counts(db, owner_id)
    return TodayOut(
        accepted_cards=sum(counts.values()),
        card_sources=len(counts),
        ready_count=len(ready),
        digest=[
            TodayDigestItem(snapshot=to_out(db, s), accepted_cards=counts.get(s.id, 0))
            for s in ready[:DIGEST_LIMIT]
        ],
        inbox_count=len(inbox),
        recent=[to_out(db, s) for s in inbox[:RECENT_LIMIT]],
        due_count=due_count,
        new_count=new_count,
        mastery=MasteryTally(**tally),
    )
