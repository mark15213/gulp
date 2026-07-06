from app.services.gulp import compose_session, next_card_id, record_review
from gulp_shared.models import MasteryLadder, ReviewEvent, SessionScope


def test_got_it_advances_and_schedules(db, owner, make_accepted_card):
    card = make_accepted_card(db, owner)
    s = compose_session(db, owner.id, target_minutes=5, scope_type=SessionScope.daily)
    updated = record_review(db, s.id, owner.id, card.id, "got_it", None)
    assert updated.reps == 1
    assert updated.interval_days == 1.0
    assert updated.ladder is MasteryLadder.can_recall
    events = db.query(ReviewEvent).filter_by(card_id=card.id).all()
    assert len(events) == 1 and events[0].grade.value == "got_it"


def test_missed_requeues_as_retest(db, owner, make_accepted_card):
    card = make_accepted_card(db, owner)
    s = compose_session(db, owner.id, target_minutes=5, scope_type=SessionScope.daily)
    record_review(db, s.id, owner.id, card.id, "missed", None)
    # the missed card is the next card again (live retest)
    assert next_card_id(db, s.id, owner.id) == str(card.id)


def test_fold_equals_replay(db, owner, make_accepted_card):
    from gulp_shared.domain.scheduling import Scheduling, apply_review

    card = make_accepted_card(db, owner)
    s = compose_session(db, owner.id, target_minutes=5, scope_type=SessionScope.daily)
    for g in ["got_it", "got_it", "missed", "got_it"]:
        record_review(db, s.id, owner.id, card.id, g, None)
    replay = Scheduling()
    for g in ["got_it", "got_it", "missed", "got_it"]:
        replay = apply_review(replay, g)
    assert card.reps == replay.reps
    assert card.interval_days == replay.interval_days
    assert card.lapses == replay.lapses
