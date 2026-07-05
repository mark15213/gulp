"""DELETE /snapshots/{id} — cascade soft-delete of a snapshot and its derivatives."""

import uuid

import pytest
from app.deps import get_db, get_enqueue
from app.main import app
from fastapi.testclient import TestClient
from gulp_shared.models.card import Card, CardOrigin, CardType
from gulp_shared.models.concept import Concept, ConceptType, SourceConcept
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.pack_block_message import ChatRole, PackBlockMessage
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.source_tag import SourceTag
from gulp_shared.models.user import DEV_USER_ID
from sqlalchemy import select


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: None)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _library_snapshot_with_derivatives(db) -> Source:  # type: ignore[no-untyped-def]
    """A `ready` snapshot wired up with one of every derivative."""
    src = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="S",
        status=SnapshotStatus.ready,
    )
    db.add(src)
    db.flush()

    pack = KnowledgePack(
        snapshot_id=src.id,
        title="T",
        key_insight="k",
        core_contributions=["c"],
        references=[],
        status=PackStatus.ready,
    )
    db.add(pack)
    db.flush()
    section = PackSection(pack_id=pack.id, heading="H", position=0)
    db.add(section)
    db.flush()
    block = PackBlock(section_id=section.id, block_type=PackBlockType.prose, data={}, position=0)
    db.add(block)
    db.flush()
    db.add(PackBlockMessage(block_id=block.id, role=ChatRole.user, content="hi"))

    db.add(
        Card(
            source_id=src.id,
            card_type=CardType.flashcard,
            prompt="Q",
            answer="A",
            origin=CardOrigin.imported,
        )
    )
    db.add(SourceFigure(source_id=src.id, ext="png", mime_type="image/png"))
    db.add(SourceTag(source_id=src.id, tag="t"))
    concept = Concept(concept_type=ConceptType.term, name="c")
    db.add(concept)
    db.flush()
    db.add(SourceConcept(source_id=src.id, concept_id=concept.id))
    db.commit()
    return src


def test_delete_library_snapshot_cascades(client, db) -> None:  # type: ignore[no-untyped-def]
    src = _library_snapshot_with_derivatives(db)
    sid = str(src.id)

    r = client.delete(f"/snapshots/{sid}")
    assert r.status_code == 204

    # Gone from every read path.
    assert client.get(f"/snapshots/{sid}").status_code == 404
    assert client.get(f"/snapshots/{sid}/pack").status_code == 404
    assert sid not in [i["id"] for i in client.get("/library").json()["items"]]

    # Direct derivatives carry deleted_at.
    db.expire_all()
    for model, where in [
        (Card, Card.source_id == src.id),
        (SourceFigure, SourceFigure.source_id == src.id),
        (SourceTag, SourceTag.source_id == src.id),
        (SourceConcept, SourceConcept.source_id == src.id),
        (KnowledgePack, KnowledgePack.snapshot_id == src.id),
    ]:
        rows = list(db.scalars(select(model).where(where)))
        assert rows and all(row.deleted_at is not None for row in rows), model.__name__

    # The whole pack tree is stamped too — no live section/block/message left behind.
    for tree_model in (PackSection, PackBlock, PackBlockMessage):
        live = list(db.scalars(select(tree_model).where(tree_model.deleted_at.is_(None))))
        assert live == [], tree_model.__name__


def test_delete_inbox_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/capture", json={"url": "https://a.com/x"})
    sid = r.json()["snapshot"]["id"]
    assert client.delete(f"/snapshots/{sid}").status_code == 204
    assert sid not in [i["id"] for i in client.get("/inbox").json()["items"]]


def test_delete_foreign_snapshot_404(client, db) -> None:  # type: ignore[no-untyped-def]
    foreign = Source(
        owner_id=uuid.uuid4(),
        kind=SourceKind.snapshot,
        title="F",
        status=SnapshotStatus.ready,
    )
    db.add(foreign)
    db.commit()
    assert client.delete(f"/snapshots/{foreign.id}").status_code == 404


def test_delete_is_idempotent_404(client, db) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/capture", json={"url": "https://b.com/y"})
    sid = r.json()["snapshot"]["id"]
    assert client.delete(f"/snapshots/{sid}").status_code == 204
    assert client.delete(f"/snapshots/{sid}").status_code == 404
