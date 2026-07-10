# Subscription System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** RSSHub/Folo-compatible subscription pipeline — follow `rsshub://` or plain RSS feeds, poll on a schedule, browse entries on a Feeds surface, explicitly promote ("gulp") entries into the existing snapshot pipeline.

**Architecture:** `Source(kind=subscription)` reuses the single-table discriminator; fetched items live in a new lightweight `feed_entries` table; promotion creates a `Source(kind=snapshot)` with `emitted_by` back-pointer and hands off to the existing genre-aware worker pipeline. RSSHub is self-hosted in docker-compose; the route catalog (`routes.json`) is cached in Redis and searched by the API.

**Tech Stack:** SQLAlchemy + Alembic, arq (jobs + cron), feedparser + httpx (worker), FastAPI, Redis cache (api), Next.js App Router + `@gulp/api-client`.

**Spec:** `docs/superpowers/specs/2026-07-09-subscription-system-design.md`

## Global Constraints

- All code, comments, commit messages in English (repo Rule 6).
- Routers thin; business logic in `app/services`; persistence in `gulp_shared` (repo Rule 3).
- No network I/O in API request handlers except the catalog fetch (cached); heavy work goes through arq (repo Rule 4).
- Python tests run per package: `cd services/<pkg> && uv run pytest`. Repo-root pytest breaks on the `app` namespace collision.
- Web tests: vitest with **classic JSX transform** — every JSX-bearing file (component AND test) needs `import React`; JSX-free files must not import it.
- After API schema changes: `just gen-client`.
- TS clients import types only from `@gulp/api-client` — never hand-written fetch types.
- `feed_url` canonical forms: `rsshub://ns/path` or `http(s)://…` (bare `/ns/path` input normalizes to `rsshub://`).
- Alembic head before this plan: `1e2f3a4b5c6d`.

---

### Task 1: Shared domain — feed address normalization

**Files:**
- Create: `services/shared/gulp_shared/domain/feeds.py`
- Test: `services/shared/tests/test_feeds_domain.py`

**Interfaces:**
- Produces: `normalize_feed_url(raw: str) -> str` (raises `ValueError`), `resolve_feed_url(feed_url: str, rsshub_base_url: str) -> str`, `entry_guid(entry_id: str | None, link: str | None, title: str | None) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# services/shared/tests/test_feeds_domain.py
import pytest
from gulp_shared.domain.feeds import entry_guid, normalize_feed_url, resolve_feed_url


def test_normalize_rsshub_url_passes_through():
    assert normalize_feed_url("rsshub://github/activity/DIYgod") == "rsshub://github/activity/DIYgod"


def test_normalize_strips_whitespace_and_slashes():
    assert normalize_feed_url("  rsshub://sspai/index/  ") == "rsshub://sspai/index"


def test_normalize_bare_route_path_becomes_rsshub():
    assert normalize_feed_url("/github/trending/daily") == "rsshub://github/trending/daily"


def test_normalize_https_passes_through():
    url = "https://www.ruanyifeng.com/blog/atom.xml"
    assert normalize_feed_url(url) == url


@pytest.mark.parametrize("bad", ["", "   ", "rsshub://", "/", "ftp://x", "not a url"])
def test_normalize_rejects_garbage(bad):
    with pytest.raises(ValueError):
        normalize_feed_url(bad)


def test_resolve_rsshub_against_instance():
    assert (
        resolve_feed_url("rsshub://github/activity/DIYgod", "http://localhost:1200")
        == "http://localhost:1200/github/activity/DIYgod"
    )


def test_resolve_plain_url_untouched():
    url = "https://hnrss.org/best"
    assert resolve_feed_url(url, "http://localhost:1200") == url


def test_entry_guid_prefers_feed_id():
    assert entry_guid(" tag:x,2026:1 ", "https://a", "T") == "tag:x,2026:1"


def test_entry_guid_falls_back_to_hash():
    g = entry_guid(None, "https://a/post", "Title")
    assert g.startswith("sha256:") and g == entry_guid("", "https://a/post", "Title")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/shared && uv run pytest tests/test_feeds_domain.py -v`
Expected: FAIL — `ModuleNotFoundError: gulp_shared.domain.feeds`

- [ ] **Step 3: Implement**

```python
# services/shared/gulp_shared/domain/feeds.py
"""Feed-address rules (spec 2026-07-09 §1.1/§2): canonical storage form is
Folo's instance-independent `rsshub://ns/path`, or a plain http(s) feed URL."""

import hashlib

RSSHUB_SCHEME = "rsshub://"


def normalize_feed_url(raw: str) -> str:
    """Canonicalize user input; raises ValueError on unusable addresses."""
    s = raw.strip()
    if s.startswith(RSSHUB_SCHEME):
        rest = s[len(RSSHUB_SCHEME) :].strip().strip("/")
        if not rest:
            raise ValueError("empty rsshub:// route")
        return RSSHUB_SCHEME + rest
    if s.startswith("/"):
        rest = s.strip("/")
        if not rest:
            raise ValueError("empty route path")
        return RSSHUB_SCHEME + rest
    if s.startswith(("http://", "https://")) and len(s) > 8:
        return s
    raise ValueError("feed address must be rsshub://…, /route/path, or http(s)://…")


def resolve_feed_url(feed_url: str, rsshub_base_url: str) -> str:
    """Turn the stored form into a fetchable URL against the configured instance."""
    if feed_url.startswith(RSSHUB_SCHEME):
        return rsshub_base_url.rstrip("/") + "/" + feed_url[len(RSSHUB_SCHEME) :]
    return feed_url


def entry_guid(entry_id: str | None, link: str | None, title: str | None) -> str:
    """Feed-provided id, else a stable hash of link+title (spec §1.4)."""
    if entry_id and entry_id.strip():
        return entry_id.strip()[:512]
    basis = f"{(link or '').strip()}|{(title or '').strip()}"
    return "sha256:" + hashlib.sha256(basis.encode()).hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd services/shared && uv run pytest tests/test_feeds_domain.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add services/shared/gulp_shared/domain/feeds.py services/shared/tests/test_feeds_domain.py
git commit -m "feat(shared): feed-address domain — rsshub:// normalization and resolution"
```

---

### Task 2: Shared model + settings + migration

**Files:**
- Modify: `services/shared/gulp_shared/models/source.py`
- Create: `services/shared/gulp_shared/models/feed_entry.py`
- Modify: `services/shared/gulp_shared/models/__init__.py`
- Modify: `services/shared/gulp_shared/settings.py`
- Create: `services/api/alembic/versions/f7a8b9c0d1e2_subscriptions.py`
- Test: `services/shared/tests/test_feed_entry_model.py`

**Interfaces:**
- Produces: `Source.feed_url/muted/last_fetch_at/last_fetch_error/feed_etag/feed_http_modified/consecutive_failures/emitted_by` (all nullable), `CapturedVia.feed`, `FeedEntry` model, settings `rsshub_base_url` / `rsshub_routes_url` / `feed_poll_interval_minutes` / `feed_entry_retention_days`.

- [ ] **Step 1: Write the failing test**

```python
# services/shared/tests/test_feed_entry_model.py
import uuid

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/shared && uv run pytest tests/test_feed_entry_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'FeedEntry'`

- [ ] **Step 3: Implement models + settings**

In `source.py`, add `feed` to `CapturedVia`:

```python
class CapturedVia(enum.StrEnum):
    share_sheet = "share_sheet"
    wechat = "wechat"
    email = "email"
    in_app = "in_app"
    paste = "paste"
    manual = "manual"
    screenshot = "screenshot"
    audio_memo = "audio_memo"
    feed = "feed"
```

At the bottom of the `Source` class (after `cards_status`), replace the closing comment line with:

```python
    # subscription-specific (spec 2026-07-09); nullable for other kinds.
    # Health is derived: muted flag + last_fetch_error (no stored status).
    feed_url: Mapped[str | None] = mapped_column(String, default=None, index=True)
    muted: Mapped[bool | None] = mapped_column(default=None)
    last_fetch_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_fetch_error: Mapped[str | None] = mapped_column(Text, default=None)
    feed_etag: Mapped[str | None] = mapped_column(String, default=None)
    feed_http_modified: Mapped[str | None] = mapped_column(String, default=None)
    consecutive_failures: Mapped[int | None] = mapped_column(default=None)
    # snapshot-side: the Subscription that produced it (docs/02 §4.3, live as of
    # spec 2026-07-09); null for ad-hoc captures.
    emitted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), default=None, index=True
    )
    # 1–1 KnowledgePack is modeled from KnowledgePack.snapshot_id (S2).
```

(add `from datetime import datetime` and `DateTime` to the sqlalchemy import.)

```python
# services/shared/gulp_shared/models/feed_entry.py
"""FeedEntry — lightweight, prunable feed items (spec 2026-07-09 §1.4).
Browsed on Feeds; an explicit gulp promotes one to a Source(snapshot)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class FeedEntry(TimestampedBase, Base):
    __tablename__ = "feed_entries"
    __table_args__ = (
        UniqueConstraint("subscription_id", "guid", name="uq_feed_entries_sub_guid"),
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    guid: Mapped[str] = mapped_column(String(512))
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(String, default=None)
    author: Mapped[str | None] = mapped_column(String, default=None)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    content_html: Mapped[str | None] = mapped_column(Text, default=None)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    promoted_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), default=None
    )
```

Register in `models/__init__.py` (import + `__all__ += ["FeedEntry"]`).

Settings additions (after `media_dir`):

```python
    rsshub_base_url: str = "http://localhost:1200"
    rsshub_routes_url: str = "https://docs.rsshub.app/routes.json"
    feed_poll_interval_minutes: int = 30
    feed_entry_retention_days: int = 90
```

- [ ] **Step 4: Write the migration (hand-rolled, matching repo style)**

```python
# services/api/alembic/versions/f7a8b9c0d1e2_subscriptions.py
"""subscriptions: Source feed columns + emitted_by + feed_entries table

Revision ID: f7a8b9c0d1e2
Revises: 1e2f3a4b5c6d
"""
import sqlalchemy as sa
from alembic import op

revision = 'f7a8b9c0d1e2'
down_revision = '1e2f3a4b5c6d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE captured_via ADD VALUE IF NOT EXISTS 'feed'")

    op.add_column('sources', sa.Column('feed_url', sa.String(), nullable=True))
    op.create_index(op.f('ix_sources_feed_url'), 'sources', ['feed_url'])
    op.add_column('sources', sa.Column('muted', sa.Boolean(), nullable=True))
    op.add_column('sources', sa.Column('last_fetch_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('sources', sa.Column('last_fetch_error', sa.Text(), nullable=True))
    op.add_column('sources', sa.Column('feed_etag', sa.String(), nullable=True))
    op.add_column('sources', sa.Column('feed_http_modified', sa.String(), nullable=True))
    op.add_column('sources', sa.Column('consecutive_failures', sa.Integer(), nullable=True))
    op.add_column('sources', sa.Column('emitted_by', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_sources_emitted_by'), 'sources', ['emitted_by'])
    op.create_foreign_key(
        'fk_sources_emitted_by', 'sources', 'sources',
        ['emitted_by'], ['id'], ondelete='SET NULL',
    )

    op.create_table(
        'feed_entries',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('subscription_id', sa.Uuid(), nullable=False),
        sa.Column('guid', sa.String(length=512), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('author', sa.String(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('content_html', sa.Text(), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('promoted_source_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['subscription_id'], ['sources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['promoted_source_id'], ['sources.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('subscription_id', 'guid', name='uq_feed_entries_sub_guid'),
    )
    op.create_index(
        op.f('ix_feed_entries_subscription_id'), 'feed_entries', ['subscription_id']
    )


def downgrade() -> None:
    op.drop_table('feed_entries')
    op.drop_constraint('fk_sources_emitted_by', 'sources', type_='foreignkey')
    op.drop_index(op.f('ix_sources_emitted_by'), table_name='sources')
    op.drop_column('sources', 'emitted_by')
    op.drop_column('sources', 'consecutive_failures')
    op.drop_column('sources', 'feed_http_modified')
    op.drop_column('sources', 'feed_etag')
    op.drop_column('sources', 'last_fetch_error')
    op.drop_column('sources', 'last_fetch_at')
    op.drop_column('sources', 'muted')
    op.drop_index(op.f('ix_sources_feed_url'), table_name='sources')
    op.drop_column('sources', 'feed_url')
    # 'feed' stays in captured_via — enum value removal needs a type rebuild
    # and no rows can carry it after feed_entries drops; tolerated leftover.
```

- [ ] **Step 5: Run tests + migration**

Run: `cd services/shared && uv run pytest tests/test_feed_entry_model.py -v` → PASS
Run: `just migrate-up` (requires `just up` postgres) → `Running upgrade 1e2f3a4b5c6d -> f7a8b9c0d1e2`

- [ ] **Step 6: Commit**

```bash
git add services/shared services/api/alembic
git commit -m "feat(shared): subscription feed columns, emitted_by, FeedEntry table + migration"
```

---

### Task 3: Worker — feed fetch pipeline

**Files:**
- Create: `services/worker/app/pipeline/feeds.py`
- Create: `services/worker/tests/fixtures/feed_rss2.xml`, `services/worker/tests/fixtures/feed_atom.xml`
- Modify: `services/worker/pyproject.toml` (add `feedparser>=6.0`)
- Test: `services/worker/tests/test_feeds_fetch.py`

**Interfaces:**
- Consumes: `resolve_feed_url`, `entry_guid` (Task 1); `Source` feed columns, `FeedEntry` (Task 2).
- Produces: `async run_fetch_feed(db: Session, sub: Source, *, http_get=None) -> int` (new-entry count; never raises — failures land on the subscription row). `http_get` is an injectable `async (url, headers) -> httpx.Response` for tests.

- [ ] **Step 1: Add dependency**

In `services/worker/pyproject.toml` dependencies, add `"feedparser>=6.0",` then run `uv sync`. feedparser ships no type stubs — add a mypy override in the worker's mypy config (`[[tool.mypy.overrides]] module = "feedparser.*"`, `ignore_missing_imports = true`; put it wherever the worker's mypy settings live so `just lint` stays green).

- [ ] **Step 2: Write fixtures + failing tests**

`feed_rss2.xml` — two items, one with guid, one without (tests hash fallback), feed title `Test RSS Feed`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Test RSS Feed</title><link>https://example.com</link>
  <item>
    <title>First post</title><link>https://example.com/1</link>
    <guid>https://example.com/1</guid>
    <author>alice@example.com (Alice)</author>
    <pubDate>Wed, 08 Jul 2026 10:00:00 GMT</pubDate>
    <description><![CDATA[<p>Hello <b>world</b></p>]]></description>
  </item>
  <item>
    <title>Second post</title><link>https://example.com/2</link>
    <description>plain summary</description>
  </item>
</channel></rss>
```

`feed_atom.xml` — one entry with `<content type="html">` (tests content preference over summary):

```xml
<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Atom Feed</title><id>tag:example.org,2026:feed</id>
  <updated>2026-07-08T10:00:00Z</updated>
  <entry>
    <title>Atom entry</title><id>tag:example.org,2026:1</id>
    <link href="https://example.org/1"/>
    <updated>2026-07-08T10:00:00Z</updated>
    <summary>short</summary>
    <content type="html">&lt;p&gt;full body&lt;/p&gt;</content>
  </entry>
</feed>
```

```python
# services/worker/tests/test_feeds_fetch.py
import pathlib
import uuid

import httpx
import pytest
from gulp_shared.models import FeedEntry, SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID

from app.pipeline.feeds import run_fetch_feed

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


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
        return httpx.Response(status, content=body, headers=headers or {},
                              request=httpx.Request("GET", url))
    return http_get


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_fetch_is_idempotent_on_guid(db):
    sub = _sub(db)
    body = (FIXTURES / "feed_rss2.xml").read_bytes()
    await run_fetch_feed(db, sub, http_get=_responder(body))
    n2 = await run_fetch_feed(db, sub, http_get=_responder(body))
    assert n2 == 0
    assert db.query(FeedEntry).filter_by(subscription_id=sub.id).count() == 2


@pytest.mark.anyio
async def test_fetch_atom_prefers_content_over_summary(db):
    sub = _sub(db, feed_url="https://example.org/atom.xml")
    body = (FIXTURES / "feed_atom.xml").read_bytes()
    await run_fetch_feed(db, sub, http_get=_responder(body))
    e = db.query(FeedEntry).filter_by(subscription_id=sub.id).one()
    assert e.content_html == "<p>full body</p>" and e.published_at is not None


@pytest.mark.anyio
async def test_fetch_304_touches_and_skips(db):
    sub = _sub(db)
    await run_fetch_feed(db, sub, http_get=_responder(b"", status=304))
    assert sub.last_fetch_at is not None and sub.last_fetch_error is None
    assert db.query(FeedEntry).count() == 0


@pytest.mark.anyio
async def test_fetch_error_recorded_not_raised(db):
    sub = _sub(db)
    await run_fetch_feed(db, sub, http_get=_responder(b"nope", status=500))
    assert "500" in sub.last_fetch_error
    assert sub.consecutive_failures == 1
    # a later success clears the error state
    body = (FIXTURES / "feed_rss2.xml").read_bytes()
    await run_fetch_feed(db, sub, http_get=_responder(body))
    assert sub.last_fetch_error is None and sub.consecutive_failures == 0


@pytest.mark.anyio
async def test_user_title_never_overwritten(db):
    sub = _sub(db, title="My name")
    body = (FIXTURES / "feed_rss2.xml").read_bytes()
    await run_fetch_feed(db, sub, http_get=_responder(body))
    assert sub.title == "My name"
```

(check `services/worker/tests/conftest.py` for the existing `db` fixture and anyio marker convention; add a `db` fixture mirroring the api conftest if the worker one lacks it.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd services/worker && uv run pytest tests/test_feeds_fetch.py -v`
Expected: FAIL — `ModuleNotFoundError: app.pipeline.feeds`

- [ ] **Step 4: Implement `run_fetch_feed`**

```python
# services/worker/app/pipeline/feeds.py
"""Feed polling (spec 2026-07-09 §2): resolve rsshub:// against the configured
instance, conditional GET, feedparser parse, upsert entries by (sub, guid).
Failures never raise — they land on the subscription row (derived health)."""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import feedparser
import httpx
from gulp_shared.domain.feeds import entry_guid, resolve_feed_url
from gulp_shared.models import FeedEntry, Source
from gulp_shared.settings import settings
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("gulp.worker")

HttpGet = Callable[[str, dict[str, str]], Awaitable[httpx.Response]]


async def _default_http_get(url: str, headers: dict[str, str]) -> httpx.Response:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        return await client.get(url, headers=headers)


def _entry_content(entry: feedparser.FeedParserDict) -> str | None:
    contents = entry.get("content") or []
    if contents and contents[0].get("value"):
        return contents[0]["value"]
    return entry.get("summary") or None


def _entry_published(entry: feedparser.FeedParserDict) -> datetime | None:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    return datetime(*t[:6], tzinfo=UTC) if t else None


async def run_fetch_feed(db: Session, sub: Source, *, http_get: HttpGet | None = None) -> int:
    get = http_get or _default_http_get
    now = datetime.now(UTC)
    sub.last_fetch_at = now
    headers: dict[str, str] = {}
    if sub.feed_etag:
        headers["If-None-Match"] = sub.feed_etag
    if sub.feed_http_modified:
        headers["If-Modified-Since"] = sub.feed_http_modified

    try:
        resp = await get(resolve_feed_url(sub.feed_url or "", settings.rsshub_base_url), headers)
        if resp.status_code == 304:
            _mark_ok(sub)
            db.commit()
            return 0
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
        if parsed.bozo and not parsed.entries:
            raise ValueError(f"unparseable feed: {parsed.bozo_exception}")
    except Exception as exc:  # noqa: BLE001 — derived health, never raise
        sub.last_fetch_error = str(exc)[:500]
        sub.consecutive_failures = (sub.consecutive_failures or 0) + 1
        db.commit()
        logger.warning("fetch_feed %s failed: %s", sub.id, exc)
        return 0

    if sub.title == sub.feed_url and parsed.feed.get("title"):
        sub.title = parsed.feed["title"]
    sub.feed_etag = resp.headers.get("ETag") or sub.feed_etag
    sub.feed_http_modified = resp.headers.get("Last-Modified") or sub.feed_http_modified

    guids = [
        entry_guid(e.get("id"), e.get("link"), e.get("title")) for e in parsed.entries
    ]
    known = set(
        db.scalars(
            select(FeedEntry.guid).where(
                FeedEntry.subscription_id == sub.id, FeedEntry.guid.in_(guids)
            )
        )
    )
    new = 0
    for e, guid in zip(parsed.entries, guids, strict=True):
        if guid in known:
            continue
        known.add(guid)  # feeds can repeat an id within one document
        db.add(
            FeedEntry(
                subscription_id=sub.id,
                guid=guid,
                title=e.get("title") or "(untitled)",
                url=e.get("link"),
                author=e.get("author"),
                published_at=_entry_published(e),
                content_html=_entry_content(e),
            )
        )
        new += 1
    _mark_ok(sub)
    db.commit()
    logger.info("fetch_feed %s: %d new entries", sub.id, new)
    return new


def _mark_ok(sub: Source) -> None:
    sub.last_fetch_error = None
    sub.consecutive_failures = 0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd services/worker && uv run pytest tests/test_feeds_fetch.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add services/worker
git commit -m "feat(worker): feed fetch pipeline — conditional GET, feedparser, guid upsert"
```

---

### Task 4: Worker — arq jobs + cron wiring

**Files:**
- Modify: `services/worker/app/tasks/__init__.py`
- Test: `services/worker/tests/test_feeds_jobs.py`

**Interfaces:**
- Consumes: `run_fetch_feed` (Task 3).
- Produces: arq jobs `fetch_feed(ctx, subscription_id: str)`, cron `poll_feeds(ctx)` (every 30 min, enqueues `fetch_feed` per due subscription), cron `prune_feed_entries(ctx)` (weekly); helper `_feed_due(sub: Source, now: datetime) -> bool`.

- [ ] **Step 1: Write failing tests**

```python
# services/worker/tests/test_feeds_jobs.py
from datetime import UTC, datetime, timedelta

from gulp_shared.models import Source

from app.tasks import _feed_due


def _sub(**kw) -> Source:
    defaults = dict(last_fetch_at=None, consecutive_failures=None)
    defaults.update(kw)
    s = Source.__new__(Source)
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


NOW = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)


def test_never_fetched_is_due():
    assert _feed_due(_sub(), NOW)


def test_recently_fetched_not_due():
    assert not _feed_due(_sub(last_fetch_at=NOW - timedelta(minutes=5)), NOW)


def test_stale_is_due():
    assert _feed_due(_sub(last_fetch_at=NOW - timedelta(minutes=31)), NOW)


def test_failing_feed_backs_off_to_daily():
    sub = _sub(last_fetch_at=NOW - timedelta(hours=2), consecutive_failures=5)
    assert not _feed_due(sub, NOW)
    assert _feed_due(_sub(last_fetch_at=NOW - timedelta(hours=25), consecutive_failures=5), NOW)


def test_naive_timestamp_tolerated():  # sqlite loses tzinfo
    assert _feed_due(_sub(last_fetch_at=(NOW - timedelta(hours=1)).replace(tzinfo=None)), NOW)
```

Run: `cd services/worker && uv run pytest tests/test_feeds_jobs.py -v` → FAIL (`_feed_due` not defined)

- [ ] **Step 2: Implement jobs**

In `services/worker/app/tasks/__init__.py` add:

```python
from datetime import UTC, datetime, timedelta

from arq import cron
from gulp_shared.models import FeedEntry
from gulp_shared.models.source import SourceKind
from sqlalchemy import delete, select

from app.pipeline.feeds import run_fetch_feed


async def fetch_feed(ctx: dict[str, Any], subscription_id: str) -> None:
    db = SessionLocal()
    try:
        sub = db.get(Source, uuid.UUID(subscription_id))
        if sub is None or sub.kind != SourceKind.subscription or sub.deleted_at is not None:
            logger.warning("fetch_feed: subscription %s not found", subscription_id)
            return
        await run_fetch_feed(db, sub)
    finally:
        db.close()


def _feed_due(sub: Source, now: datetime) -> bool:
    if sub.last_fetch_at is None:
        return True
    interval = (
        timedelta(hours=24)
        if (sub.consecutive_failures or 0) >= 5
        else timedelta(minutes=settings.feed_poll_interval_minutes)
    )
    last = sub.last_fetch_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return now - last >= interval


async def poll_feeds(ctx: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        subs = db.scalars(
            select(Source).where(
                Source.kind == SourceKind.subscription,
                Source.deleted_at.is_(None),
                Source.muted.isnot(True),
                Source.feed_url.isnot(None),
            )
        ).all()
        due = [s for s in subs if _feed_due(s, now)]
        for sub in due:
            await ctx["redis"].enqueue_job("fetch_feed", str(sub.id))
        logger.info("poll_feeds: %d/%d subscriptions due", len(due), len(subs))
    finally:
        db.close()


async def prune_feed_entries(ctx: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        cutoff = datetime.now(UTC) - timedelta(days=settings.feed_entry_retention_days)
        result = db.execute(
            delete(FeedEntry).where(
                FeedEntry.promoted_source_id.is_(None), FeedEntry.created_at < cutoff
            )
        )
        db.commit()
        logger.info("prune_feed_entries: removed %d", result.rowcount)
    finally:
        db.close()
```

Extend `WorkerSettings`:

```python
class WorkerSettings:
    functions = [
        process_snapshot,
        build_export,
        build_cards_export,
        import_result,
        resolve_metadata,
        generate_cards,
        fetch_feed,
    ]
    cron_jobs = [
        cron(poll_feeds, minute={0, 30}),
        cron(prune_feed_entries, weekday=6, hour=4, minute=10),  # Sunday
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
```

- [ ] **Step 3: Run the whole worker suite**

Run: `cd services/worker && uv run pytest -q`
Expected: PASS (existing + new)

- [ ] **Step 4: Commit**

```bash
git add services/worker
git commit -m "feat(worker): poll_feeds/prune crons + fetch_feed job with failure back-off"
```

---

### Task 5: API — subscriptions, entries, gulp

**Files:**
- Create: `services/api/app/schemas/feeds.py`, `services/api/app/services/feeds.py`, `services/api/app/routers/feeds.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_feeds_api.py`

**Interfaces:**
- Consumes: `normalize_feed_url` (Task 1), models (Task 2), `create_snapshot` (`app.services.capture`), `start_processing` (`app.services.processing`), `get_enqueue` seam.
- Produces (REST, all owner-scoped):
  - `POST /subscriptions` → `SubscriptionCreateResponse {subscription, duplicate}` (enqueues `fetch_feed` for new subs)
  - `GET /subscriptions` → `SubscriptionsOut {items, count}`
  - `PATCH /subscriptions/{id}` (`{title?, muted?}`) / `DELETE /subscriptions/{id}` (204)
  - `POST /subscriptions/{id}/refresh` (202) / `POST /subscriptions/{id}/read-all` (204)
  - `GET /subscriptions/{id}/entries`, `GET /feed-entries` (`unread_only`, `limit`, `offset`) → `FeedEntriesOut {items, count}`
  - `POST /feed-entries/{id}/read` / `.../unread` (204)
  - `POST /feed-entries/{id}/gulp` → `GulpEntryResponse {snapshot_id, duplicate}`

- [ ] **Step 1: Write failing tests** (uses existing `db`/`client` fixtures; enqueue override captures calls)

```python
# services/api/tests/test_feeds_api.py
import uuid
from datetime import UTC, datetime

from app.deps import get_enqueue
from app.main import app
from gulp_shared.models import FeedEntry, SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID


def _capture_enqueue(calls):
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: calls.append(a))


def _mk_sub(db, feed_url="rsshub://sspai/index"):
    sub = Source(owner_id=DEV_USER_ID, kind=SourceKind.subscription, title=feed_url,
                 status=SnapshotStatus.ready, feed_url=feed_url, muted=False)
    db.add(sub); db.commit()
    return sub


def _mk_entry(db, sub, **kw):
    e = FeedEntry(subscription_id=sub.id, guid=kw.pop("guid", str(uuid.uuid4())),
                  title=kw.pop("title", "An entry"), url=kw.pop("url", "https://example.com/p/1"),
                  **kw)
    db.add(e); db.commit()
    return e


def test_create_subscription_normalizes_and_enqueues(client, db):
    calls = []
    _capture_enqueue(calls)
    r = client.post("/subscriptions", json={"feed_url": "/github/trending/daily"})
    assert r.status_code == 200
    body = r.json()
    assert body["subscription"]["feed_url"] == "rsshub://github/trending/daily"
    assert body["duplicate"] is False
    assert calls == [("fetch_feed", body["subscription"]["id"])]


def test_create_subscription_idempotent(client, db):
    client.post("/subscriptions", json={"feed_url": "rsshub://sspai/index"})
    r = client.post("/subscriptions", json={"feed_url": "rsshub://sspai/index/"})
    assert r.json()["duplicate"] is True


def test_create_subscription_rejects_garbage(client):
    assert client.post("/subscriptions", json={"feed_url": "nope"}).status_code == 422


def test_list_subscriptions_health_and_unread(client, db):
    sub = _mk_sub(db)
    _mk_entry(db, sub)
    _mk_entry(db, sub, read_at=datetime.now(UTC))
    errored = _mk_sub(db, feed_url="https://bad.example/feed")
    errored.last_fetch_error = "boom"; db.commit()
    items = {i["feed_url"]: i for i in client.get("/subscriptions").json()["items"]}
    assert items["rsshub://sspai/index"]["unread_count"] == 1
    assert items["rsshub://sspai/index"]["health"] == "active"
    assert items["https://bad.example/feed"]["health"] == "error"


def test_mute_and_delete(client, db):
    sub = _mk_sub(db)
    _mk_entry(db, sub)
    r = client.patch(f"/subscriptions/{sub.id}", json={"muted": True})
    assert r.json()["health"] == "muted"
    assert client.delete(f"/subscriptions/{sub.id}").status_code == 204
    assert client.get("/subscriptions").json()["count"] == 0
    assert db.query(FeedEntry).count() == 0  # entries hard-deleted with the sub


def test_entries_listing_and_read_toggle(client, db):
    sub = _mk_sub(db)
    e = _mk_entry(db, sub)
    r = client.get(f"/subscriptions/{sub.id}/entries")
    assert r.json()["count"] == 1 and r.json()["items"][0]["read"] is False
    client.post(f"/feed-entries/{e.id}/read")
    assert client.get("/feed-entries", params={"unread_only": True}).json()["count"] == 0


def test_gulp_promotes_and_is_idempotent(client, db):
    calls = []
    _capture_enqueue(calls)
    sub = _mk_sub(db)
    e = _mk_entry(db, sub)
    r = client.post(f"/feed-entries/{e.id}/gulp")
    assert r.status_code == 200
    snap_id = r.json()["snapshot_id"]
    snap = db.get(Source, uuid.UUID(snap_id))
    assert snap.kind == SourceKind.snapshot and snap.emitted_by == sub.id
    assert snap.captured_via.value == "feed"
    assert ("process_snapshot", snap_id) in calls
    # idempotent second gulp
    assert client.post(f"/feed-entries/{e.id}/gulp").json()["snapshot_id"] == snap_id


def test_gulp_entry_without_url_is_422(client, db):
    sub = _mk_sub(db)
    e = _mk_entry(db, sub, url=None)
    assert client.post(f"/feed-entries/{e.id}/gulp").status_code == 422
```

Run: `cd services/api && uv run pytest tests/test_feeds_api.py -v` → FAIL (404s: router missing)

- [ ] **Step 2: Schemas**

```python
# services/api/app/schemas/feeds.py
"""Feeds contract (spec 2026-07-09 §3): subscriptions, entries, promotion."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SubscriptionHealth = Literal["active", "muted", "error"]


class SubscriptionCreate(BaseModel):
    feed_url: str
    title: str | None = None


class SubscriptionPatch(BaseModel):
    title: str | None = None
    muted: bool | None = None


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    title: str
    feed_url: str
    health: SubscriptionHealth
    muted: bool
    unread_count: int
    last_fetch_at: datetime | None
    last_fetch_error: str | None
    created_at: datetime


class SubscriptionCreateResponse(BaseModel):
    subscription: SubscriptionOut
    duplicate: bool


class SubscriptionsOut(BaseModel):
    items: list[SubscriptionOut]
    count: int


class FeedEntryOut(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID
    subscription_title: str
    title: str
    url: str | None
    author: str | None
    published_at: datetime | None
    content_html: str | None
    read: bool
    promoted_source_id: uuid.UUID | None
    created_at: datetime


class FeedEntriesOut(BaseModel):
    items: list[FeedEntryOut]
    count: int


class GulpEntryResponse(BaseModel):
    snapshot_id: uuid.UUID
    duplicate: bool


class CatalogRouteOut(BaseModel):
    namespace: str
    namespace_name: str
    route_path: str
    route_name: str | None
    example: str | None
    parameters: dict[str, str] | None
    require_config: bool
    heat: int


class CatalogSearchOut(BaseModel):
    items: list[CatalogRouteOut]
    count: int
```

- [ ] **Step 3: Service**

```python
# services/api/app/services/feeds.py
"""Feeds business logic (spec 2026-07-09): subscription lifecycle, entry
browsing, and promotion into the snapshot pipeline."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from gulp_shared.domain.feeds import normalize_feed_url
from gulp_shared.models import FeedEntry, SnapshotStatus, Source, SourceKind
from gulp_shared.models.source import CapturedVia
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.schemas.capture import CaptureRequest
from app.schemas.feeds import (
    FeedEntryOut,
    SubscriptionCreate,
    SubscriptionHealth,
    SubscriptionOut,
    SubscriptionPatch,
)
from app.services.capture import create_snapshot
from app.services.processing import start_processing


def create_subscription(
    db: Session, owner_id: uuid.UUID, req: SubscriptionCreate
) -> tuple[Source, bool]:
    normalized = normalize_feed_url(req.feed_url)  # ValueError -> router 422
    existing = db.scalar(
        select(Source).where(
            Source.owner_id == owner_id,
            Source.kind == SourceKind.subscription,
            Source.feed_url == normalized,
            Source.deleted_at.is_(None),
        )
    )
    if existing is not None:
        return existing, True
    sub = Source(
        owner_id=owner_id,
        kind=SourceKind.subscription,
        title=req.title or normalized,  # backfilled from feed title on first fetch
        status=SnapshotStatus.ready,  # constant for subscriptions; health is derived
        feed_url=normalized,
        muted=False,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub, False


def health_of(sub: Source) -> SubscriptionHealth:
    if sub.muted:
        return "muted"
    if sub.last_fetch_error is not None:
        return "error"
    return "active"


def get_subscription(db: Session, owner_id: uuid.UUID, sub_id: uuid.UUID) -> Source | None:
    sub = db.get(Source, sub_id)
    ok = (
        sub is not None
        and sub.owner_id == owner_id
        and sub.kind == SourceKind.subscription
        and sub.deleted_at is None
    )
    return sub if ok else None


def _unread_counts(db: Session, sub_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not sub_ids:
        return {}
    rows = db.execute(
        select(FeedEntry.subscription_id, func.count())
        .where(FeedEntry.subscription_id.in_(sub_ids), FeedEntry.read_at.is_(None))
        .group_by(FeedEntry.subscription_id)
    ).all()
    return dict(rows)


def to_subscription_out(sub: Source, unread: int) -> SubscriptionOut:
    return SubscriptionOut(
        id=sub.id,
        title=sub.title,
        feed_url=sub.feed_url or "",
        health=health_of(sub),
        muted=bool(sub.muted),
        unread_count=unread,
        last_fetch_at=sub.last_fetch_at,
        last_fetch_error=sub.last_fetch_error,
        created_at=sub.created_at,
    )


def list_subscriptions(db: Session, owner_id: uuid.UUID) -> list[SubscriptionOut]:
    subs = list(
        db.scalars(
            select(Source)
            .where(
                Source.owner_id == owner_id,
                Source.kind == SourceKind.subscription,
                Source.deleted_at.is_(None),
            )
            .order_by(Source.created_at.desc())
        )
    )
    unread = _unread_counts(db, [s.id for s in subs])
    return [to_subscription_out(s, unread.get(s.id, 0)) for s in subs]


def update_subscription(db: Session, sub: Source, patch: SubscriptionPatch) -> Source:
    if patch.title is not None:
        sub.title = patch.title
    if patch.muted is not None:
        sub.muted = patch.muted
    db.commit()
    db.refresh(sub)
    return sub


def delete_subscription(db: Session, sub: Source) -> None:
    """Tombstone the subscription (docs/02 §9); its entries are working data,
    hard-deleted. Promoted snapshots survive via their own rows."""
    db.execute(delete(FeedEntry).where(FeedEntry.subscription_id == sub.id))
    sub.deleted_at = datetime.now(UTC)
    db.commit()


def to_entry_out(entry: FeedEntry, subscription_title: str) -> FeedEntryOut:
    return FeedEntryOut(
        id=entry.id,
        subscription_id=entry.subscription_id,
        subscription_title=subscription_title,
        title=entry.title,
        url=entry.url,
        author=entry.author,
        published_at=entry.published_at,
        content_html=entry.content_html,
        read=entry.read_at is not None,
        promoted_source_id=entry.promoted_source_id,
        created_at=entry.created_at,
    )


def list_entries(
    db: Session,
    owner_id: uuid.UUID,
    subscription_id: uuid.UUID | None = None,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[FeedEntry, str]], int]:
    q = (
        select(FeedEntry, Source.title)
        .join(Source, FeedEntry.subscription_id == Source.id)
        .where(Source.owner_id == owner_id, Source.deleted_at.is_(None))
    )
    if subscription_id is not None:
        q = q.where(FeedEntry.subscription_id == subscription_id)
    if unread_only:
        q = q.where(FeedEntry.read_at.is_(None))
    count = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.execute(
        q.order_by(
            FeedEntry.published_at.desc().nullslast(), FeedEntry.created_at.desc()
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return [(e, title) for e, title in rows], count


def get_entry(db: Session, owner_id: uuid.UUID, entry_id: uuid.UUID) -> FeedEntry | None:
    row = db.execute(
        select(FeedEntry)
        .join(Source, FeedEntry.subscription_id == Source.id)
        .where(FeedEntry.id == entry_id, Source.owner_id == owner_id)
    ).scalar_one_or_none()
    return row


def set_read(db: Session, entry: FeedEntry, read: bool) -> FeedEntry:
    entry.read_at = datetime.now(UTC) if read else None
    db.commit()
    db.refresh(entry)
    return entry


def mark_all_read(db: Session, sub: Source) -> None:
    from sqlalchemy import update

    db.execute(
        update(FeedEntry)
        .where(FeedEntry.subscription_id == sub.id, FeedEntry.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    db.commit()


def gulp_entry(
    db: Session,
    owner_id: uuid.UUID,
    entry: FeedEntry,
    enqueue: Callable[..., None],
) -> tuple[uuid.UUID, bool]:
    """Promote an entry: snapshot via the capture path, then straight into
    processing (spec §2.4 — the feed gulp is the explicit 'Start')."""
    if entry.promoted_source_id is not None:
        existing = db.get(Source, entry.promoted_source_id)
        if existing is not None and existing.deleted_at is None:
            return existing.id, True
    if not entry.url:
        raise ValueError("entry has no URL to promote")
    req = CaptureRequest(url=entry.url, title=entry.title, captured_via=CapturedVia.feed)
    source, duplicate = create_snapshot(db, owner_id, req)
    if not duplicate:
        source.emitted_by = entry.subscription_id
        db.commit()
        enqueue("resolve_metadata", str(source.id))
        start_processing(db, source, enqueue)
    entry.promoted_source_id = source.id
    if entry.read_at is None:
        entry.read_at = datetime.now(UTC)
    db.commit()
    return source.id, duplicate
```

- [ ] **Step 4: Router + wiring**

```python
# services/api/app/routers/feeds.py
"""Feeds endpoints — thin (docs/05 D4): parse, call service, return."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db, get_enqueue
from app.schemas.feeds import (
    CatalogSearchOut,
    FeedEntriesOut,
    GulpEntryResponse,
    SubscriptionCreate,
    SubscriptionCreateResponse,
    SubscriptionOut,
    SubscriptionPatch,
    SubscriptionsOut,
)
from app.services import feeds as svc
from app.services.catalog import search_catalog

router = APIRouter()


@router.post("/subscriptions", response_model=SubscriptionCreateResponse)
def create_subscription(
    req: SubscriptionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> SubscriptionCreateResponse:
    try:
        sub, duplicate = svc.create_subscription(db, user.id, req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not duplicate:
        enqueue("fetch_feed", str(sub.id))
    return SubscriptionCreateResponse(
        subscription=svc.to_subscription_out(sub, 0), duplicate=duplicate
    )


@router.get("/subscriptions", response_model=SubscriptionsOut)
def list_subscriptions(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SubscriptionsOut:
    items = svc.list_subscriptions(db, user.id)
    return SubscriptionsOut(items=items, count=len(items))


def _sub_or_404(db: Session, user: User, sub_id: uuid.UUID):
    sub = svc.get_subscription(db, user.id, sub_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    return sub


@router.patch("/subscriptions/{sub_id}", response_model=SubscriptionOut)
def patch_subscription(
    sub_id: uuid.UUID,
    patch: SubscriptionPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubscriptionOut:
    sub = svc.update_subscription(db, _sub_or_404(db, user, sub_id), patch)
    unread = svc._unread_counts(db, [sub.id]).get(sub.id, 0)
    return svc.to_subscription_out(sub, unread)


@router.delete("/subscriptions/{sub_id}", status_code=204)
def delete_subscription(
    sub_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    svc.delete_subscription(db, _sub_or_404(db, user, sub_id))


@router.post("/subscriptions/{sub_id}/refresh", status_code=202)
def refresh_subscription(
    sub_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> None:
    sub = _sub_or_404(db, user, sub_id)
    enqueue("fetch_feed", str(sub.id))


@router.post("/subscriptions/{sub_id}/read-all", status_code=204)
def read_all(
    sub_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    svc.mark_all_read(db, _sub_or_404(db, user, sub_id))


@router.get("/subscriptions/{sub_id}/entries", response_model=FeedEntriesOut)
def subscription_entries(
    sub_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedEntriesOut:
    _sub_or_404(db, user, sub_id)
    rows, count = svc.list_entries(db, user.id, sub_id, unread_only, limit, offset)
    return FeedEntriesOut(items=[svc.to_entry_out(e, t) for e, t in rows], count=count)


@router.get("/feed-entries", response_model=FeedEntriesOut)
def all_entries(
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedEntriesOut:
    rows, count = svc.list_entries(db, user.id, None, unread_only, limit, offset)
    return FeedEntriesOut(items=[svc.to_entry_out(e, t) for e, t in rows], count=count)


def _entry_or_404(db: Session, user: User, entry_id: uuid.UUID):
    entry = svc.get_entry(db, user.id, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="entry not found")
    return entry


@router.post("/feed-entries/{entry_id}/read", response_model=None, status_code=204)
def mark_read(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    svc.set_read(db, _entry_or_404(db, user, entry_id), True)


@router.post("/feed-entries/{entry_id}/unread", response_model=None, status_code=204)
def mark_unread(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    svc.set_read(db, _entry_or_404(db, user, entry_id), False)


@router.post("/feed-entries/{entry_id}/gulp", response_model=GulpEntryResponse)
def gulp_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> GulpEntryResponse:
    entry = _entry_or_404(db, user, entry_id)
    try:
        snapshot_id, duplicate = svc.gulp_entry(db, user.id, entry, enqueue)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return GulpEntryResponse(snapshot_id=snapshot_id, duplicate=duplicate)


@router.get("/feeds/catalog/search", response_model=CatalogSearchOut)
def catalog_search(
    q: str = "",
    limit: int = 30,
    user: User = Depends(get_current_user),
) -> CatalogSearchOut:
    items = search_catalog(q, limit=limit)
    return CatalogSearchOut(items=items, count=len(items))
```

In `main.py`: add `feeds` to the router import block and `app.include_router(feeds.router, tags=["feeds"])` (alphabetical: after `figures`). NOTE: the catalog import means Task 6's `app/services/catalog.py` must exist for the app to boot — create it in this task as a stub `def search_catalog(q, limit=30): return []` and fill it in Task 6.

- [ ] **Step 5: Run tests**

Run: `cd services/api && uv run pytest tests/test_feeds_api.py -v` → PASS
Run: `cd services/api && uv run pytest -q` → full suite PASS

- [ ] **Step 6: Commit**

```bash
git add services/api
git commit -m "feat(api): subscriptions + feed entries + gulp promotion endpoints"
```

---

### Task 6: API — RSSHub catalog search

**Files:**
- Modify: `services/api/app/services/catalog.py` (replace Task 5 stub)
- Modify: `services/api/pyproject.toml` (add `httpx>=0.28`, `redis>=5`)
- Test: `services/api/tests/test_catalog.py`, fixture `services/api/tests/fixtures/routes_slice.json`

**Interfaces:**
- Consumes: settings `rsshub_routes_url`, `redis_url`.
- Produces: `search_catalog(q: str, limit: int = 30, catalog: dict | None = None) -> list[CatalogRouteOut]`; `get_catalog() -> dict` (Redis-cached 7 days, in-process memo).

- [ ] **Step 1: Fixture + failing tests**

`routes_slice.json` — a 3-namespace slice mirroring the real shape:

```json
{
  "github": {
    "name": "GitHub", "url": "github.com", "categories": ["programming"],
    "routes": {
      "/github/activity/:user": {
        "path": "/activity/:user", "name": "User Activities",
        "example": "/github/activity/DIYgod",
        "parameters": {"user": "GitHub username"},
        "features": {"requireConfig": false}, "heat": 4835
      },
      "/github/notifications": {
        "path": "/notifications", "name": "Notifications",
        "example": "/github/notifications", "parameters": {},
        "features": {"requireConfig": true}, "heat": 900
      }
    }
  },
  "sspai": {
    "name": "少数派 sspai", "url": "sspai.com", "categories": ["new-media"],
    "routes": {
      "/sspai/index": {
        "path": "/index", "name": "首页", "example": "/sspai/index",
        "parameters": null, "features": {"requireConfig": false}, "heat": 32039
      }
    }
  },
  "v2ex": {
    "name": "V2EX", "url": "v2ex.com", "categories": ["bbs"],
    "routes": {
      "/v2ex/topics/:type": {
        "path": "/topics/:type", "name": "最热 / 最新主题",
        "example": "/v2ex/topics/latest", "parameters": {"type": "hot or latest"},
        "features": {"requireConfig": false}, "heat": 23471
      }
    }
  }
}
```

```python
# services/api/tests/test_catalog.py
import json
import pathlib

from app.services.catalog import search_catalog

CATALOG = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "routes_slice.json").read_text()
)


def test_search_by_namespace_name():
    items = search_catalog("github", catalog=CATALOG)
    assert [i.route_path for i in items] == ["/github/activity/:user", "/github/notifications"]
    assert items[0].heat == 4835 and items[0].require_config is False
    assert items[1].require_config is True


def test_search_matches_chinese_namespace():
    items = search_catalog("少数派", catalog=CATALOG)
    assert items[0].route_path == "/sspai/index" and items[0].parameters is None


def test_search_by_route_name():
    assert search_catalog("Activities", catalog=CATALOG)[0].route_name == "User Activities"


def test_empty_query_returns_top_heat():
    items = search_catalog("", catalog=CATALOG, limit=2)
    assert [i.route_path for i in items] == ["/sspai/index", "/v2ex/topics/:type"]


def test_no_match_is_empty():
    assert search_catalog("zzzznope", catalog=CATALOG) == []
```

Run: `cd services/api && uv run pytest tests/test_catalog.py -v` → FAIL (stub returns [])

- [ ] **Step 2: Implement**

```python
# services/api/app/services/catalog.py
"""RSSHub route catalog (spec 2026-07-09 §3.1): the official routes.json,
Redis-cached for 7 days, searched in-process. This is the one API-side
network fetch — lazy, cached, and never on the subscription hot path."""

import json
import logging
import time
from typing import Any

import httpx
from gulp_shared.settings import settings
from redis import Redis

from app.schemas.feeds import CatalogRouteOut

logger = logging.getLogger("gulp.api")

_CACHE_KEY = "rsshub:catalog"
_REDIS_TTL = 7 * 24 * 3600
_MEMO_TTL = 3600.0

_memo: dict[str, Any] | None = None
_memo_at: float = 0.0


def _fetch_routes_json() -> bytes:
    resp = httpx.get(settings.rsshub_routes_url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def get_catalog() -> dict[str, Any]:
    global _memo, _memo_at
    if _memo is not None and time.monotonic() - _memo_at < _MEMO_TTL:
        return _memo
    raw: bytes | None = None
    try:
        r = Redis.from_url(settings.redis_url)
        raw = r.get(_CACHE_KEY)
        if raw is None:
            raw = _fetch_routes_json()
            r.set(_CACHE_KEY, raw, ex=_REDIS_TTL)
    except httpx.HTTPError:
        raise
    except Exception as exc:  # Redis down — fetch straight through
        logger.warning("catalog cache unavailable (%s); fetching direct", exc)
        raw = _fetch_routes_json()
    _memo = json.loads(raw)
    _memo_at = time.monotonic()
    return _memo


def search_catalog(
    q: str, limit: int = 30, catalog: dict[str, Any] | None = None
) -> list[CatalogRouteOut]:
    data = catalog if catalog is not None else get_catalog()
    ql = q.strip().lower()
    hits: list[CatalogRouteOut] = []
    for ns_key, ns in data.items():
        ns_name = ns.get("name") or ns_key
        ns_match = not ql or ql in ns_key.lower() or ql in ns_name.lower()
        for route_path, route in (ns.get("routes") or {}).items():
            route_name = route.get("name")
            if not (
                ns_match
                or ql in route_path.lower()
                or (route_name and ql in route_name.lower())
            ):
                continue
            features = route.get("features") or {}
            hits.append(
                CatalogRouteOut(
                    namespace=ns_key,
                    namespace_name=ns_name,
                    route_path=route_path,
                    route_name=route_name,
                    example=route.get("example"),
                    parameters=route.get("parameters") or None,
                    require_config=bool(features.get("requireConfig")),
                    heat=int(route.get("heat") or 0),
                )
            )
    hits.sort(key=lambda h: h.heat, reverse=True)
    return hits[:limit]
```

Add `"httpx>=0.28",` and `"redis>=5",` to `services/api/pyproject.toml` dependencies; `uv sync`.

- [ ] **Step 3: Run tests**

Run: `cd services/api && uv run pytest tests/test_catalog.py tests/test_feeds_api.py -q` → PASS

- [ ] **Step 4: Regenerate the TS client**

Run: `just gen-client`
Expected: `packages/api-client/src/schema.gen.ts` gains `/subscriptions`, `/feed-entries`, `/feeds/catalog/search` paths. (Known pre-existing dup-identifier `tsc` noise in schema.gen.ts is unrelated — `just lint` uses eslint.)

- [ ] **Step 5: Commit**

```bash
git add services/api packages/api-client
git commit -m "feat(api): RSSHub catalog search (routes.json, redis-cached); regen client"
```

---

### Task 7: Infra — self-hosted RSSHub + env

**Files:**
- Modify: `infra/docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Add the service**

```yaml
  rsshub:
    image: diygod/rsshub
    ports:
      - "1200:1200"
    environment:
      NODE_ENV: production
      CACHE_TYPE: redis
      REDIS_URL: redis://redis:6379/1
    depends_on:
      - redis
```

`.env.example` — append under a new section:

```
# --- Feeds (spec 2026-07-09) ---
RSSHUB_BASE_URL=http://localhost:1200
```

- [ ] **Step 2: Verify**

Run: `just up && sleep 20 && curl -s http://localhost:1200/ | head -c 200`
Expected: RSSHub welcome page HTML.
Run: `curl -s "http://localhost:1200/hellogithub/volume" | head -c 300` → RSS XML.

- [ ] **Step 3: Commit**

```bash
git add infra/docker-compose.yml .env.example
git commit -m "feat(infra): self-hosted RSSHub service in local compose"
```

---

### Task 8: Web — api-client helpers + sidebar Feeds item

**Files:**
- Modify: `packages/api-client/src/index.ts`
- Modify: `apps/web/components/shell/SidebarNav.tsx` (+ its test)

**Interfaces:**
- Produces (all throw on error, mirroring existing helpers): `getSubscriptions()`, `createSubscription(body)`, `patchSubscription(id, body)`, `deleteSubscription(id)`, `refreshSubscription(id)`, `readAllSubscription(id)`, `getFeedEntries(params?: {subscriptionId?, unreadOnly?, limit?, offset?})`, `setEntryRead(id, read)`, `gulpEntry(id)`, `searchCatalog(q, limit?)`; types `Subscription`, `FeedEntry`, `CatalogRoute`, `FeedEntriesOut`.

- [ ] **Step 1: Add typed helpers**

```typescript
// append to packages/api-client/src/index.ts
export type SubscriptionsOut =
  paths["/subscriptions"]["get"]["responses"]["200"]["content"]["application/json"];
export type Subscription = SubscriptionsOut["items"][number];
export type SubscriptionCreateResponse =
  paths["/subscriptions"]["post"]["responses"]["200"]["content"]["application/json"];
export type FeedEntriesOut =
  paths["/feed-entries"]["get"]["responses"]["200"]["content"]["application/json"];
export type FeedEntry = FeedEntriesOut["items"][number];
export type CatalogSearchOut =
  paths["/feeds/catalog/search"]["get"]["responses"]["200"]["content"]["application/json"];
export type CatalogRoute = CatalogSearchOut["items"][number];

export async function getSubscriptions(): Promise<SubscriptionsOut> {
  const { data, error } = await client.GET("/subscriptions", { cache: "no-store" });
  if (error || !data) throw new Error("subscriptions fetch failed");
  return data;
}

export async function createSubscription(body: {
  feed_url: string;
  title?: string | null;
}): Promise<SubscriptionCreateResponse> {
  const { data, error } = await client.POST("/subscriptions", { body });
  if (error || !data) throw new Error("subscription create failed");
  return data;
}

export async function patchSubscription(
  id: string,
  body: { title?: string | null; muted?: boolean | null },
): Promise<Subscription> {
  const { data, error } = await client.PATCH("/subscriptions/{sub_id}", {
    params: { path: { sub_id: id } },
    body,
  });
  if (error || !data) throw new Error("subscription update failed");
  return data;
}

export async function deleteSubscription(id: string): Promise<void> {
  const { error } = await client.DELETE("/subscriptions/{sub_id}", {
    params: { path: { sub_id: id } },
  });
  if (error) throw new Error("subscription delete failed");
}

export async function refreshSubscription(id: string): Promise<void> {
  const { error } = await client.POST("/subscriptions/{sub_id}/refresh", {
    params: { path: { sub_id: id } },
  });
  if (error) throw new Error("subscription refresh failed");
}

export async function readAllSubscription(id: string): Promise<void> {
  const { error } = await client.POST("/subscriptions/{sub_id}/read-all", {
    params: { path: { sub_id: id } },
  });
  if (error) throw new Error("read-all failed");
}

export async function getFeedEntries(params?: {
  subscriptionId?: string;
  unreadOnly?: boolean;
  limit?: number;
  offset?: number;
}): Promise<FeedEntriesOut> {
  const query = {
    unread_only: params?.unreadOnly,
    limit: params?.limit,
    offset: params?.offset,
  };
  if (params?.subscriptionId) {
    const { data, error } = await client.GET("/subscriptions/{sub_id}/entries", {
      params: { path: { sub_id: params.subscriptionId }, query },
      cache: "no-store",
    });
    if (error || !data) throw new Error("entries fetch failed");
    return data;
  }
  const { data, error } = await client.GET("/feed-entries", {
    params: { query },
    cache: "no-store",
  });
  if (error || !data) throw new Error("entries fetch failed");
  return data;
}

export async function setEntryRead(id: string, read: boolean): Promise<void> {
  const path = read ? "/feed-entries/{entry_id}/read" : "/feed-entries/{entry_id}/unread";
  const { error } = await client.POST(path, { params: { path: { entry_id: id } } });
  if (error) throw new Error("read toggle failed");
}

export async function gulpEntry(
  id: string,
): Promise<{ snapshot_id: string; duplicate: boolean }> {
  const { data, error } = await client.POST("/feed-entries/{entry_id}/gulp", {
    params: { path: { entry_id: id } },
  });
  if (error || !data) throw new Error("gulp failed");
  return data;
}

export async function searchCatalog(q: string, limit = 30): Promise<CatalogSearchOut> {
  const { data, error } = await client.GET("/feeds/catalog/search", {
    params: { query: { q, limit } },
  });
  if (error || !data) throw new Error("catalog search failed");
  return data;
}
```

(`setEntryRead`'s two literal paths may need separate typed calls if openapi-fetch complains about the union — split into an if/else with two `client.POST` literals in that case.)

- [ ] **Step 2: Sidebar**

In `SidebarNav.tsx` add to `NAV` (icon exists already):

```typescript
import { IconToday, IconInbox, IconLibrary, IconFeeds } from "@/components/ui/icons";

const NAV = [
  { label: "Today", href: "/", icon: IconToday },
  { label: "Inbox", href: "/inbox", icon: IconInbox },
  { label: "Library", href: "/library", icon: IconLibrary },
  { label: "Feeds", href: "/feeds", icon: IconFeeds },
] as const;
```

Update the stale comment ("Feeds returns with S7" → "Feeds live per spec 2026-07-09"). Check `SidebarNav.test.tsx` / `Sidebar.test.tsx` for item-count assertions and update them.

- [ ] **Step 3: Test + commit**

Run: `pnpm --filter @gulp/web test` → PASS
Run: `pnpm turbo run lint` → PASS

```bash
git add packages/api-client apps/web/components/shell
git commit -m "feat(web): feeds api-client helpers + Feeds sidebar item"
```

---

### Task 9: Web — /feeds workspace (three panes)

**Files:**
- Create: `apps/web/app/feeds/page.tsx`, `apps/web/app/feeds/page.module.css`
- Create: `apps/web/components/feeds/FeedsWorkspace.tsx` (+ `.module.css`), `SubscriptionList.tsx`, `EntryList.tsx`, `EntryReader.tsx`, `AddFeedDialog.tsx`
- Test: `apps/web/components/feeds/SubscriptionList.test.tsx`, `apps/web/components/feeds/EntryList.test.tsx`

**Interfaces:**
- Consumes: Task 8 helpers/types.
- Component contract: `FeedsWorkspace({ initialSubscriptions, initialEntries })` owns selection + refetch; `SubscriptionList({ subscriptions, selectedId, onSelect, onToggleMute, onDelete, onAdd })`; `EntryList({ entries, selectedId, onSelect, unreadOnly, onToggleUnreadOnly })`; `EntryReader({ entry, onGulp, onToggleRead })`; `AddFeedDialog({ open, onClose, onSubmit })`.

- [ ] **Step 1: Server page**

```tsx
// apps/web/app/feeds/page.tsx
import { getFeedEntries, getSubscriptions } from "@gulp/api-client";
import { FeedsWorkspace } from "@/components/feeds/FeedsWorkspace";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

// Feeds — the stream: follow, browse, and explicitly gulp what's worth it
// (spec 2026-07-09 §5; docs/03 §7.11).
export default async function FeedsPage() {
  const [subs, entries] = await Promise.all([getSubscriptions(), getFeedEntries()]);
  return (
    <div className={styles.page}>
      <FeedsWorkspace initialSubscriptions={subs.items} initialEntries={entries.items} />
    </div>
  );
}
```

- [ ] **Step 2: Client components** (follow `LibraryList` styling idioms; every file `"use client"` + `import React`)

`FeedsWorkspace` — state: `subs`, `entries`, `selectedSubId: string | null` (null = All), `selectedEntryId`, `unreadOnly`. Handlers call the api-client helpers then refetch the affected lists (`getSubscriptions()` / `getFeedEntries({subscriptionId: selectedSubId ?? undefined, unreadOnly})`). `onGulp(entry)` → `gulpEntry(entry.id)` → update the entry locally with `promoted_source_id` and show a link `→ /snapshots/{id}`. Three-pane CSS grid: `240px 320px 1fr`, full height.

`SubscriptionList` — "All entries" row on top, then one row per subscription: health dot (`active` = accent, `error` = red with `title={last_fetch_error}`, `muted` = dimmed), title, mono unread count, hover actions (mute/unmute toggle, delete with `confirm()`), footer "+ Add feed" button opening `AddFeedDialog`, plus a "Discover →" link to `/feeds/discover`.

`EntryList` — header with subscription name + unread-only toggle + "mark all read" (when a sub is selected); rows: title, `t-data` meta line (subscription_title · published date via `lib/time` helpers if present, else `toLocaleDateString`), unread dot, "forwarded" check when `promoted_source_id`.

`EntryReader` — empty state ("Select an entry"); else header (title as link to `url`, author/date), actions row (Forward button — disabled when `!entry.url`, shows "Forwarded ✓ →" link when forwarded → the snapshot, which lands in the Inbox and reaches the Library only at `status=ready`; mark read/unread), body `dangerouslySetInnerHTML={{ __html: entry.content_html ?? "" }}` inside a scrollable prose container. (Feed HTML is third-party: strip `<script>` tags with a small `sanitize(html)` — `html.replace(/<script[\s\S]*?<\/script>/gi, "")` — before rendering; a full sanitizer is a fast-follow.)

`AddFeedDialog` — input (placeholder `rsshub://ns/path, /ns/path, or https://…`) + optional title; submit → `createSubscription`; on 422 show the error inline; on success close + refresh.

- [ ] **Step 3: Component tests**

```tsx
// apps/web/components/feeds/SubscriptionList.test.tsx
import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { Subscription } from "@gulp/api-client";
import { SubscriptionList } from "./SubscriptionList";

const sub = (over: Partial<Subscription>): Subscription =>
  ({
    id: "s1",
    title: "Anthropic Research",
    feed_url: "rsshub://anthropic/research",
    health: "active",
    muted: false,
    unread_count: 3,
    last_fetch_at: null,
    last_fetch_error: null,
    created_at: "2026-07-09T00:00:00Z",
    ...over,
  }) as Subscription;

describe("SubscriptionList", () => {
  it("renders unread count and fires selection", () => {
    const onSelect = vi.fn();
    render(
      <SubscriptionList
        subscriptions={[sub({})]}
        selectedId={null}
        onSelect={onSelect}
        onToggleMute={vi.fn()}
        onDelete={vi.fn()}
        onAdd={vi.fn()}
      />,
    );
    expect(screen.getByText("3")).toBeDefined();
    fireEvent.click(screen.getByText("Anthropic Research"));
    expect(onSelect).toHaveBeenCalledWith("s1");
  });

  it("marks error health", () => {
    render(
      <SubscriptionList
        subscriptions={[sub({ health: "error", last_fetch_error: "boom" })]}
        selectedId={null}
        onSelect={vi.fn()}
        onToggleMute={vi.fn()}
        onDelete={vi.fn()}
        onAdd={vi.fn()}
      />,
    );
    expect(screen.getByTitle("boom")).toBeDefined();
  });
});
```

```tsx
// apps/web/components/feeds/EntryList.test.tsx
import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { FeedEntry } from "@gulp/api-client";
import { EntryList } from "./EntryList";

const entry = (over: Partial<FeedEntry>): FeedEntry =>
  ({
    id: "e1",
    subscription_id: "s1",
    subscription_title: "Anthropic Research",
    title: "A post",
    url: "https://example.com/1",
    author: null,
    published_at: "2026-07-08T10:00:00Z",
    content_html: null,
    read: false,
    promoted_source_id: null,
    created_at: "2026-07-08T10:05:00Z",
    ...over,
  }) as FeedEntry;

describe("EntryList", () => {
  it("shows unread state and selects", () => {
    const onSelect = vi.fn();
    render(
      <EntryList
        entries={[entry({})]}
        selectedId={null}
        onSelect={onSelect}
        unreadOnly={false}
        onToggleUnreadOnly={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText("A post"));
    expect(onSelect).toHaveBeenCalledWith("e1");
  });

  it("marks promoted entries as gulped", () => {
    render(
      <EntryList
        entries={[entry({ promoted_source_id: "snap1", read: true })]}
        selectedId={null}
        onSelect={vi.fn()}
        unreadOnly={false}
        onToggleUnreadOnly={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("gulped")).toBeDefined();
  });
});
```

- [ ] **Step 4: Run + commit**

Run: `pnpm --filter @gulp/web test` → PASS; `pnpm turbo run lint` → PASS

```bash
git add apps/web
git commit -m "feat(web): /feeds workspace — subscriptions, entries, reader with gulp"
```

---

### Task 10: Web — /feeds/discover (catalog + starter list)

**Files:**
- Create: `apps/web/app/feeds/discover/page.tsx` (+ `.module.css`)
- Create: `apps/web/components/feeds/DiscoverSearch.tsx`, `apps/web/components/feeds/starters.ts`
- Test: `apps/web/components/feeds/starters.test.ts`

**Interfaces:**
- Consumes: `searchCatalog`, `createSubscription` (Task 8).
- Produces: `STARTER_SOURCES: {feedUrl: string; title: string; note: string}[]` (the spec §7 list).

- [ ] **Step 1: Starter list**

```typescript
// apps/web/components/feeds/starters.ts
// Spec 2026-07-09 §7 — verified zero-config starter sources.
export type StarterSource = { feedUrl: string; title: string; note: string };

export const STARTER_SOURCES: StarterSource[] = [
  { feedUrl: "rsshub://anthropic/research", title: "Anthropic Research", note: "English AI research articles" },
  { feedUrl: "rsshub://sspai/index", title: "少数派", note: "Chinese long-form, high volume" },
  { feedUrl: "rsshub://qbitai/category/资讯", title: "量子位", note: "Chinese AI news" },
  { feedUrl: "rsshub://solidot/www", title: "Solidot", note: "Short tech news items" },
  { feedUrl: "rsshub://36kr/hot-list", title: "36氪热榜", note: "Ranked tech list" },
  { feedUrl: "rsshub://hellogithub/volume", title: "HelloGitHub 月刊", note: "Monthly open-source digest" },
  { feedUrl: "rsshub://v2ex/topics/hot", title: "V2EX 最热", note: "Forum threads" },
  { feedUrl: "rsshub://readhub/daily", title: "Readhub 每日早报", note: "One brief per day" },
  { feedUrl: "https://www.ruanyifeng.com/blog/atom.xml", title: "阮一峰的网络日志", note: "Weekly, plain Atom" },
  { feedUrl: "https://rss.arxiv.org/rss/cs.AI", title: "arXiv cs.AI", note: "Papers — exercises the paper pipeline" },
  { feedUrl: "https://simonwillison.net/atom/everything/", title: "Simon Willison", note: "English AI blog, plain Atom" },
  { feedUrl: "https://hnrss.org/best", title: "Hacker News Best", note: "Link aggregation" },
];
```

```typescript
// apps/web/components/feeds/starters.test.ts
import { describe, expect, it } from "vitest";
import { STARTER_SOURCES } from "./starters";

describe("STARTER_SOURCES", () => {
  it("covers both address forms", () => {
    expect(STARTER_SOURCES.some((s) => s.feedUrl.startsWith("rsshub://"))).toBe(true);
    expect(STARTER_SOURCES.some((s) => s.feedUrl.startsWith("https://"))).toBe(true);
  });
  it("has unique addresses", () => {
    const urls = STARTER_SOURCES.map((s) => s.feedUrl);
    expect(new Set(urls).size).toBe(urls.length);
  });
});
```

- [ ] **Step 2: Discover page + search component**

`app/feeds/discover/page.tsx` — server shell: heading "Discover", back-link to `/feeds`, renders `<DiscoverSearch />` and the starter grid (cards: title, note, mono feedUrl, Subscribe button — the grid lives inside DiscoverSearch so subscribe state is client-side).

`DiscoverSearch.tsx` (client) — paste box + Subscribe (any of the three forms, calls `createSubscription`, inline success "Added ✓ → Feeds" / 422 error); search input, on submit `searchCatalog(q)`; result cards grouped visually by `namespace_name`: route name + mono `route_path`, heat, `requireConfig` badge ("needs instance config"), example chip that prefills the paste box with the example path (e.g. `/github/activity/DIYgod`). Starter section below (from `STARTER_SOURCES`), each with a Subscribe button that disables to "Added ✓" after success.

- [ ] **Step 3: Run + commit**

Run: `pnpm --filter @gulp/web test` → PASS; `pnpm turbo run lint` → PASS

```bash
git add apps/web
git commit -m "feat(web): /feeds/discover — catalog search + starter sources"
```

---

### Task 11: Doc fold-back + full gates + live E2E

**Files:**
- Modify: `docs/02-data-model.md` §4.8 (+ §4.3 `emitted_by`, ER diagram note)
- Modify: `docs/01-interaction-spec.md` §F6 (subscription half live, digest still deferred)
- Modify: `docs/04-development-plan.md` (amendment note)

- [ ] **Step 1: Amend docs per spec §9**

`02 §4.8`: replace the field table with the implemented set (`feed_url`, `muted`, `last_fetch_at`, `last_fetch_error`, `feed_etag`, `feed_http_modified`, `consecutive_failures`), note "health derived, not stored (spec 2026-07-09)", add `FeedEntry` table description + the `feed_entries` line in the ER diagram, mark `emitted_by` live in §4.3.
`01 §F6`: bracket note — subscriptions implemented per spec 2026-07-09 (entries + explicit gulp; auto-snapshot and digest remain deferred).
`04`: add to the amendment block — "2026-07-09: the subscription half of dropped S7 re-derived and built (spec 2026-07-09); digest half remains dropped."

- [ ] **Step 2: Full quality gates**

Run: `just lint` → green (keep it green per repo memory)
Run: `cd services/shared && uv run pytest -q` → PASS
Run: `cd services/api && uv run pytest -q` → PASS
Run: `cd services/worker && uv run pytest -q` → PASS
Run: `pnpm turbo run test` → PASS

- [ ] **Step 3: Live E2E (single worker running — beware the stale-arq-worker trap)**

1. `just up` (postgres + redis + rsshub), `just migrate-up`, `just dev`.
2. Web → Feeds → Discover → subscribe `rsshub://hellogithub/volume` and `https://www.ruanyifeng.com/blog/atom.xml`.
3. Verify: entries appear after the immediate fetch (refresh /feeds); subscription titles backfilled.
4. Gulp one entry → snapshot appears in Inbox processing → `ready`; pack opens; `emitted_by` set (check via `GET /snapshots/{id}` or DB).
5. Subscribe a garbage URL (`https://example.com/nope`) → health dot turns error, message on hover, nothing else breaks.

- [ ] **Step 4: Commit**

```bash
git add docs
git commit -m "docs: fold subscription system back into 01/02/04 (spec 2026-07-09)"
```
