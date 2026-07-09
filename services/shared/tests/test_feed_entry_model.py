import pytest
from gulp_shared.db import Base
from gulp_shared.models import CapturedVia, FeedEntry, SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    s.commit()
    yield s
    s.close()


def _subscription(db):
    sub = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.subscription,
        title="rsshub://github/activity/DIYgod",
        status=SnapshotStatus.ready,
        feed_url="rsshub://github/activity/DIYgod",
        muted=False,
    )
    db.add(sub)
    db.commit()
    return sub


def test_subscription_row_carries_feed_fields(db):
    sub = _subscription(db)
    assert sub.feed_url and sub.muted is False and sub.last_fetch_error is None


def test_feed_entry_unique_per_subscription_guid(db):
    sub = _subscription(db)
    db.add(FeedEntry(subscription_id=sub.id, guid="g1", title="A"))
    db.commit()
    db.add(FeedEntry(subscription_id=sub.id, guid="g1", title="A again"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_snapshot_emitted_by_points_at_subscription(db):
    sub = _subscription(db)
    snap = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="promoted",
        status=SnapshotStatus.unprocessed,
        captured_via=CapturedVia.feed,
        emitted_by=sub.id,
    )
    db.add(snap)
    db.commit()
    assert snap.emitted_by == sub.id
