"""Feed polling (spec 2026-07-09 §2): resolve rsshub:// against the configured
instance, conditional GET, feedparser parse, upsert entries by (sub, guid).
Failures never raise — they land on the subscription row (derived health)."""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx
from gulp_shared.domain.feeds import entry_guid, resolve_feed_url
from gulp_shared.models import FeedEntry, Source
from gulp_shared.settings import settings
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("gulp.worker")

HttpGet = Callable[[str, dict[str, str]], Awaitable[httpx.Response]]

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _use_proxy_env(url: str) -> bool:
    """System/env proxies (VPN clients) commonly refuse loopback targets with a
    bare 502 — the self-hosted RSSHub must be reached directly. Remote feeds
    keep the proxy (it may be the only route out)."""
    return httpx.URL(url).host not in _LOOPBACK_HOSTS


async def _default_http_get(url: str, headers: dict[str, str]) -> httpx.Response:
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=30, trust_env=_use_proxy_env(url)
    ) as client:
        return await client.get(url, headers=headers)


def _entry_content(entry: Any) -> str | None:
    contents = entry.get("content") or []
    if contents and contents[0].get("value"):
        return str(contents[0]["value"])
    summary = entry.get("summary")
    return str(summary) if summary else None


def _entry_published(entry: Any) -> datetime | None:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return None
    return datetime(t[0], t[1], t[2], t[3], t[4], t[5], tzinfo=UTC)


def _mark_ok(sub: Source) -> None:
    sub.last_fetch_error = None
    sub.consecutive_failures = 0


async def run_fetch_feed(db: Session, sub: Source, *, http_get: HttpGet | None = None) -> int:
    """Fetch one subscription; returns the number of new entries."""
    get = http_get or _default_http_get
    sub.last_fetch_at = datetime.now(UTC)
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

    guids = [entry_guid(e.get("id"), e.get("link"), e.get("title")) for e in parsed.entries]
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
