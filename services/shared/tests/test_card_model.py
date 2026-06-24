import gulp_shared.models  # noqa: F401  (registers tables)
from gulp_shared.db import Base
from gulp_shared.models.card import Card, CardOrigin, CardStatus, CardType
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_draft_mcq_card_persists_with_options_and_defaults():
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="Example",
        status=SnapshotStatus.ready,
    )
    s.add(snap)
    s.flush()
    card = Card(
        source_id=snap.id,
        card_type=CardType.mcq,
        prompt="What is X?",
        answer="A",
        explanation="Because the source says so.",
        options=["A", "B", "C", "D"],
        origin=CardOrigin.pack,
    )
    s.add(card)
    s.commit()

    got = s.scalar(select(Card).where(Card.source_id == snap.id))
    assert got is not None
    assert got.status == CardStatus.draft  # default
    assert got.options == ["A", "B", "C", "D"]
    assert got.explanation == "Because the source says so."
