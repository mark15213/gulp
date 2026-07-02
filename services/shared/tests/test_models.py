import uuid

import gulp_shared.models  # noqa: F401  (registers tables)
from gulp_shared.db import Base
from gulp_shared.models.source import (
    CapturedVia,
    MediaType,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.source_tag import SourceTag
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_can_persist_a_snapshot_with_a_tag():
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="Example",
        status=SnapshotStatus.processing,
        media_type=MediaType.webpage,
        origin_url="https://example.com/x",
        captured_via=CapturedVia.paste,
    )
    s.add(snap)
    s.flush()
    s.add(SourceTag(source_id=snap.id, tag="ml"))
    s.commit()

    got = s.scalar(select(Source).where(Source.owner_id == DEV_USER_ID))
    assert got is not None
    assert got.kind == SourceKind.snapshot
    assert got.status == SnapshotStatus.processing
    tag = s.scalar(select(SourceTag).where(SourceTag.source_id == snap.id))
    assert tag.tag == "ml"


def test_snapshot_can_be_unprocessed():
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="Example",
        status=SnapshotStatus.unprocessed,
    )
    s.add(snap)
    s.commit()
    assert SnapshotStatus.unprocessed.value == "unprocessed"


def test_dev_user_id_is_the_fixed_uuid():
    assert DEV_USER_ID == uuid.UUID("00000000-0000-0000-0000-000000000001")


def test_snapshot_can_be_exported():
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="X",
        status=SnapshotStatus.exported,
    )
    s.add(snap)
    s.commit()
    assert SnapshotStatus.exported.value == "exported"
