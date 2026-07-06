from datetime import UTC, datetime, timedelta

from gulp_shared.domain.mastery import (
    advance_ladder,
    daily_state,
    is_at_risk,
    is_due,
)
from gulp_shared.domain.scheduling import Scheduling


def test_daily_map():
    assert daily_state("read") == "new"
    assert daily_state("can_recall") == "learning"
    assert daily_state("can_distinguish") == "learning"
    assert daily_state("can_apply") == "known"
    assert daily_state("mastered") == "known"


def test_first_pass_reaches_can_recall():
    out = advance_ladder("read", Scheduling(reps=1, interval_days=1.0),
                         "got_it", is_mcq=False, recent_lapse=False)
    assert out == "can_recall"


def test_mcq_got_it_reaches_distinguish():
    out = advance_ladder("can_recall", Scheduling(reps=1, interval_days=1.0),
                         "got_it", is_mcq=True, recent_lapse=False)
    assert out == "can_distinguish"


def test_long_interval_reaches_apply_then_mastered():
    apply = advance_ladder("can_distinguish", Scheduling(reps=3, interval_days=21.0),
                           "got_it", is_mcq=False, recent_lapse=False)
    assert apply == "can_apply"
    mastered = advance_ladder("can_apply", Scheduling(reps=4, interval_days=60.0),
                              "got_it", is_mcq=False, recent_lapse=False)
    assert mastered == "mastered"


def test_missed_drops_one_rung_floor_read():
    assert advance_ladder("can_apply", Scheduling(), "missed",
                          is_mcq=False, recent_lapse=True) == "can_distinguish"
    assert advance_ladder("read", Scheduling(), "missed",
                          is_mcq=False, recent_lapse=True) == "read"


def test_non_miss_never_regresses():
    out = advance_ladder("can_apply", Scheduling(reps=1, interval_days=1.0),
                         "fuzzy", is_mcq=False, recent_lapse=False)
    assert out == "can_apply"  # stays; a good-enough grade never demotes


def test_due_and_at_risk():
    now = datetime(2026, 7, 6, tzinfo=UTC)
    assert is_due(now - timedelta(hours=1), now) is True
    assert is_due(now + timedelta(hours=1), now) is False
    # overdue by >= 1x interval (10d card, 10+ days late)
    assert is_at_risk(now - timedelta(days=10), 10.0, now) is True
    assert is_at_risk(now - timedelta(days=3), 10.0, now) is False
