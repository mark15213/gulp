# services/api/tests/test_gulp_compose.py
# Uses conftest fixtures: `db`, `owner` (seeded DEV_USER), `make_accepted_card`.
from app.services.gulp import compose_session, current_session, init_scheduling_on_accept
from gulp_shared.models import (
    Card,
    CardOrigin,
    CardStatus,
    CardType,
    MasteryLadder,
    SessionScope,
    SessionStatus,
    SnapshotStatus,
    Source,
    SourceKind,
)


def _src(db, owner):
    s = Source(
        owner_id=owner.id, kind=SourceKind.snapshot, title="src",
        status=SnapshotStatus.ready,
    )
    db.add(s)
    db.flush()
    return s


def _accept(db, source, **kw):
    c = Card(source_id=source.id, card_type=CardType.flashcard, prompt="q",
             origin=CardOrigin.pack, status=CardStatus.accepted, **kw)
    db.add(c)
    db.flush()
    init_scheduling_on_accept(c)
    db.flush()
    return c


def test_init_on_accept_sets_read_and_due(db, owner):
    src = _src(db, owner)
    c = _accept(db, src)
    assert c.ladder is MasteryLadder.read
    assert c.next_review_at is not None  # due now → practiceable
    assert c.reps == 0


def test_compose_builds_active_session_with_due_and_new(db, owner):
    src = _src(db, owner)
    _accept(db, src)  # new (reps 0)
    out = compose_session(db, owner.id, target_minutes=5, scope_type=SessionScope.daily)
    assert out.status is SessionStatus.active
    assert out.started_at is not None
    assert len(out.planned_card_ids) >= 1


def test_scoped_session_rejected(db, owner):
    import pytest
    with pytest.raises(ValueError, match="scope_unavailable"):
        compose_session(db, owner.id, target_minutes=5, scope_type=SessionScope.concept)


def test_current_session_returns_active(db, owner):
    src = _src(db, owner)
    _accept(db, src)
    s = compose_session(db, owner.id, target_minutes=5, scope_type=SessionScope.daily)
    assert current_session(db, owner.id).id == s.id
