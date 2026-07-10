import gulp_shared.models  # noqa: F401  (registers tables)
from gulp_shared.db import Base
from gulp_shared.models.card import Card, CardOrigin, CardType
from gulp_shared.models.concept import (
    CardConcept,
    Concept,
    ConceptEdge,
    ConceptRelation,
    ConceptType,
    SourceConcept,
)
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_concept_graph_and_links_persist():
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

    a = Concept(
        owner_id=DEV_USER_ID, concept_type=ConceptType.term, name="Transformer", aliases=["xformer"]
    )
    b = Concept(owner_id=DEV_USER_ID, concept_type=ConceptType.idea, name="Attention")
    s.add_all([a, b])
    s.flush()
    s.add(
        ConceptEdge(
            owner_id=DEV_USER_ID,
            from_concept_id=a.id,
            to_concept_id=b.id,
            relation=ConceptRelation.part_of,
        )
    )

    card = Card(source_id=snap.id, card_type=CardType.cloze, prompt="___", origin=CardOrigin.pack)
    s.add(card)
    s.flush()
    s.add(CardConcept(card_id=card.id, concept_id=a.id, role="tests"))
    s.add(SourceConcept(source_id=snap.id, concept_id=a.id, role="about"))
    s.commit()

    got = s.scalar(select(Concept).where(Concept.name == "Transformer"))
    assert got is not None and got.aliases == ["xformer"]
    edge = s.scalar(select(ConceptEdge))
    assert edge.relation == ConceptRelation.part_of
    assert s.scalar(select(CardConcept)).role == "tests"
    assert s.scalar(select(SourceConcept)).role == "about"
