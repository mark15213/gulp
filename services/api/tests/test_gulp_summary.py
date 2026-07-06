from app.services.gulp import complete_session, compose_session, record_review, summarize
from gulp_shared.models import SessionScope, SessionStatus


def test_summary_counts(db, owner, make_accepted_card):
    a = make_accepted_card(db, owner)
    b = make_accepted_card(db, owner)
    s = compose_session(db, owner.id, target_minutes=5, scope_type=SessionScope.daily)
    record_review(db, s.id, owner.id, a.id, "got_it", None)
    record_review(db, s.id, owner.id, b.id, "fuzzy", None)
    complete_session(db, s.id, owner.id)
    out = summarize(db, s.id, owner.id)
    assert out["reviewed_count"] == 2
    assert out["still_fuzzy"] == 1
    assert db.get(type(s), s.id).status is SessionStatus.complete
