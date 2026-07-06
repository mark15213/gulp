"""7-rung mastery ladder: advance rules + derived views (S4 design §3.3, C4).
`ladder` is stored; daily/due/at_risk derive from it + scheduling and are never
stored. Per-card upper rungs (distinguish/apply) approximate Concept-level
mastery until S3's Concept rollups supersede them."""

from __future__ import annotations

from datetime import datetime, timedelta

from gulp_shared.domain.scheduling import Scheduling

LADDER = [
    "unread", "read", "summarized",
    "can_recall", "can_distinguish", "can_apply", "mastered",
]
INITIAL_LADDER = "read"  # a card enters here on accept (the pack was read)

_DAILY = {
    "unread": "new", "read": "new",
    "summarized": "learning", "can_recall": "learning", "can_distinguish": "learning",
    "can_apply": "known", "mastered": "known",
}
_READ_FLOOR = LADDER.index("read")  # 1


def daily_state(ladder: str) -> str:
    return _DAILY[ladder]


def advance_ladder(
    current: str, sched: Scheduling, grade: str, *,
    is_mcq: bool, recent_lapse: bool,
) -> str:
    if grade == "missed":
        return LADDER[max(_READ_FLOOR, LADDER.index(current) - 1)]
    rung = "read"
    if sched.reps >= 1:
        rung = "can_recall"
    if (grade == "got_it" and is_mcq) or sched.interval_days >= 7:
        rung = "can_distinguish"
    if sched.interval_days >= 21 and sched.reps >= 3:
        rung = "can_apply"
    if sched.interval_days >= 60 and sched.reps >= 4 and not recent_lapse:
        rung = "mastered"
    # a good-enough grade never demotes below where the card already is
    return rung if LADDER.index(rung) >= LADDER.index(current) else current


def is_due(next_review_at: datetime | None, now: datetime) -> bool:
    return next_review_at is not None and next_review_at <= now


def is_at_risk(next_review_at: datetime | None, interval_days: float, now: datetime) -> bool:
    if next_review_at is None:
        return False
    return now >= next_review_at + timedelta(days=interval_days)
