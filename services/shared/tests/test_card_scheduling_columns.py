from gulp_shared.models import Card, CardOrigin, CardStatus, CardType, MasteryLadder


def test_card_has_scheduling_defaults():
    from gulp_shared.db import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        c = Card(card_type=CardType.flashcard, prompt="q", origin=CardOrigin.pack)
        s.add(c)
        s.flush()
        s.refresh(c)
        assert c.interval_days == 0.0
        assert c.ease == 2.3
        assert c.reps == 0
        assert c.lapses == 0
        assert c.next_review_at is None
        assert c.ladder is None  # set to `read` on accept, not at construction
        assert c.status is CardStatus.draft  # flush-time default


def test_mastery_ladder_values():
    assert [m.value for m in MasteryLadder] == [
        "unread", "read", "summarized",
        "can_recall", "can_distinguish", "can_apply", "mastered",
    ]
