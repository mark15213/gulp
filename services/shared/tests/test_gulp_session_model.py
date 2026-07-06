import uuid

from gulp_shared.models import GulpSession, SessionScope, SessionStatus, User


def test_session_enums():
    assert [s.value for s in SessionScope] == [
        "daily", "knowledge_base", "concept", "free_explore", "at_risk",
    ]
    assert [s.value for s in SessionStatus] == [
        "building", "active", "complete", "abandoned",
    ]


def test_session_construct():
    s = GulpSession(
        owner_id=uuid.uuid4(), scope_type=SessionScope.daily,
        target_minutes=5, planned_card_ids=[], status=SessionStatus.building,
    )
    assert s.planned_card_ids == []
    assert s.scope_ref is None


def test_user_gulp_minutes_default():
    # mapped_column(default=5) applies at FLUSH, not construction — assert via flush.
    from gulp_shared.db import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as sess:
        u = User()
        sess.add(u)
        sess.flush()
        sess.refresh(u)
        assert u.gulp_session_minutes == 5
