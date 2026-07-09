import pathlib

import httpx
import pytest
from app.pipeline.feeds import run_fetch_feed
from gulp_shared.db import Base
from gulp_shared.models import FeedEntry, SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(User(id=DEV_USER_ID, display_name="Dev"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _sub(db, feed_url="https://example.com/feed.xml", title=None):
    sub = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.subscription,
        title=title or feed_url,
        status=SnapshotStatus.ready,
        feed_url=feed_url,
        muted=False,
    )
    db.add(sub)
    db.commit()
    return sub


def _responder(body: bytes, status=200, headers=None):
    async def http_get(url, hdrs):
        return httpx.Response(
            status, content=body, headers=headers or {},
            request=httpx.Request("GET", url),
        )

    return http_get


async def test_fetch_inserts_entries_and_backfills_title(db):
    sub = _sub(db)
    body = (FIXTURES / "feed_rss2.xml").read_bytes()
    n = await run_fetch_feed(db, sub, http_get=_responder(body, headers={"ETag": 'W/"abc"'}))
    assert n == 2
    assert sub.title == "Test RSS Feed"  # placeholder backfilled
    assert sub.feed_etag == 'W/"abc"' and sub.last_fetch_error is None
    entries = db.query(FeedEntry).filter_by(subscription_id=sub.id).all()
    by_title = {e.title: e for e in entries}
    assert by_title["First post"].guid == "https://example.com/1"
    assert by_title["Second post"].guid.startswith("sha256:")
    assert "<b>world</b>" in by_title["First post"].content_html


async def test_fetch_is_idempotent_on_guid(db):
    sub = _sub(db)
    body = (FIXTURES / "feed_rss2.xml").read_bytes()
    await run_fetch_feed(db, sub, http_get=_responder(body))
    n2 = await run_fetch_feed(db, sub, http_get=_responder(body))
    assert n2 == 0
    assert db.query(FeedEntry).filter_by(subscription_id=sub.id).count() == 2


async def test_fetch_atom_prefers_content_over_summary(db):
    sub = _sub(db, feed_url="https://example.org/atom.xml")
    body = (FIXTURES / "feed_atom.xml").read_bytes()
    await run_fetch_feed(db, sub, http_get=_responder(body))
    e = db.query(FeedEntry).filter_by(subscription_id=sub.id).one()
    assert e.content_html == "<p>full body</p>" and e.published_at is not None


async def test_fetch_304_touches_and_skips(db):
    sub = _sub(db)
    await run_fetch_feed(db, sub, http_get=_responder(b"", status=304))
    assert sub.last_fetch_at is not None and sub.last_fetch_error is None
    assert db.query(FeedEntry).count() == 0


async def test_fetch_error_recorded_not_raised(db):
    sub = _sub(db)
    await run_fetch_feed(db, sub, http_get=_responder(b"nope", status=500))
    assert "500" in sub.last_fetch_error
    assert sub.consecutive_failures == 1
    # a later success clears the error state
    body = (FIXTURES / "feed_rss2.xml").read_bytes()
    await run_fetch_feed(db, sub, http_get=_responder(body))
    assert sub.last_fetch_error is None and sub.consecutive_failures == 0


async def test_user_title_never_overwritten(db):
    sub = _sub(db, title="My name")
    body = (FIXTURES / "feed_rss2.xml").read_bytes()
    await run_fetch_feed(db, sub, http_get=_responder(body))
    assert sub.title == "My name"
