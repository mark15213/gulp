"""Card-supply model additions: CardOrigin.imported + Source.cards_status."""

import gulp_shared.models  # noqa: F401  (registers tables)
from gulp_shared.db import Base
from gulp_shared.models.card import Card, CardOrigin, CardType
from gulp_shared.models.source import CardsStatus, SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _snapshot(s):
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="Example",
        status=SnapshotStatus.ready,
    )
    s.add(snap)
    s.flush()
    return snap


def test_imported_card_persists():
    s = _session()
    snap = _snapshot(s)
    s.add(
        Card(
            source_id=snap.id,
            card_type=CardType.short_answer,
            prompt="Q?",
            answer="A",
            origin=CardOrigin.imported,
        )
    )
    s.commit()
    got = s.scalar(select(Card).where(Card.source_id == snap.id))
    assert got is not None
    assert got.origin == CardOrigin.imported


def test_cards_status_defaults_to_none_and_is_settable():
    s = _session()
    snap = _snapshot(s)
    assert snap.cards_status is None
    snap.cards_status = CardsStatus.generating
    s.commit()
    got = s.get(Source, snap.id)
    assert got.cards_status == CardsStatus.generating
