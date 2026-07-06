import pytest
from gulp_shared.domain.scheduling import Scheduling, apply_review


def test_first_got_it_is_one_day():
    s = apply_review(Scheduling(), "got_it")
    assert s.reps == 1 and s.interval_days == 1.0


def test_second_got_it_is_three_days():
    s = apply_review(apply_review(Scheduling(), "got_it"), "got_it")
    assert s.reps == 2 and s.interval_days == 3.0


def test_third_got_it_scales_by_ease():
    s = Scheduling(interval_days=3.0, ease=2.3, reps=2)
    out = apply_review(s, "got_it")
    assert out.reps == 3 and out.interval_days == round(3.0 * 2.3)  # 7


def test_fuzzy_barely_grows_and_lowers_ease():
    s = Scheduling(interval_days=10.0, ease=2.3, reps=3)
    out = apply_review(s, "fuzzy")
    assert out.interval_days == pytest.approx(12.0)
    assert out.ease == pytest.approx(2.25)
    assert out.reps == 4


def test_fuzzy_on_new_card_is_one_day():
    out = apply_review(Scheduling(), "fuzzy")
    assert out.interval_days == 1.0


def test_missed_resets_and_lapses():
    s = Scheduling(interval_days=30.0, ease=2.3, reps=5, lapses=0)
    out = apply_review(s, "missed")
    assert out.interval_days == 1.0 and out.reps == 0 and out.lapses == 1
    assert out.ease == pytest.approx(2.1)


def test_ease_floor():
    s = Scheduling(ease=1.35)
    assert apply_review(s, "missed").ease == 1.3


def test_unknown_grade_raises():
    with pytest.raises(ValueError):
        apply_review(Scheduling(), "sorta")
