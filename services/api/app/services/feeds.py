"""Feeds business logic (spec 2026-07-09): subscription lifecycle, entry
browsing, and promotion into the snapshot pipeline."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from gulp_shared.domain.feeds import normalize_feed_url
from gulp_shared.models import FeedEntry, SnapshotStatus, Source, SourceKind
from gulp_shared.models.source import CapturedVia
from sqlalchemy import ColumnElement, delete, func, select, update
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


def _pending() -> tuple[ColumnElement[bool], ...]:
    """The undecided set: neither forwarded nor skipped (spec 2026-08-01 §2).
    `read_at` deliberately plays no part — seen is not decided."""
    return (
        FeedEntry.promoted_source_id.is_(None),
        FeedEntry.skipped_at.is_(None),
    )


def pending_counts(db: Session, sub_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not sub_ids:
        return {}
    rows = db.execute(
        select(FeedEntry.subscription_id, func.count())
        .where(FeedEntry.subscription_id.in_(sub_ids), *_pending())
        .group_by(FeedEntry.subscription_id)
    ).all()
    return {sub_id: count for sub_id, count in rows}


def to_subscription_out(sub: Source, pending: int) -> SubscriptionOut:
    return SubscriptionOut(
        id=sub.id,
        title=sub.title,
        feed_url=sub.feed_url or "",
        health=health_of(sub),
        muted=bool(sub.muted),
        pending_count=pending,
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
    pending = pending_counts(db, [s.id for s in subs])
    return [to_subscription_out(s, pending.get(s.id, 0)) for s in subs]


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
        skipped=entry.skipped_at is not None,
        promoted_source_id=entry.promoted_source_id,
        created_at=entry.created_at,
    )


def list_entries(
    db: Session,
    owner_id: uuid.UUID,
    subscription_id: uuid.UUID | None = None,
    pending_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[FeedEntry, str]], int]:
    """The Inbox `New` section (pending_only) or the review view (all).

    No longer joins the promoted snapshot: a forwarded entry's status belongs
    to the Inbox sections that own it, not to a mirror here (spec §4.4)."""
    q = (
        select(FeedEntry, Source.title)
        .join(Source, FeedEntry.subscription_id == Source.id)
        .where(Source.owner_id == owner_id, Source.deleted_at.is_(None))
    )
    if subscription_id is not None:
        q = q.where(FeedEntry.subscription_id == subscription_id)
    if pending_only:
        q = q.where(*_pending())
    count = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.execute(
        q.order_by(FeedEntry.published_at.desc().nullslast(), FeedEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [(e, title) for e, title in rows], count


def get_entry(db: Session, owner_id: uuid.UUID, entry_id: uuid.UUID) -> FeedEntry | None:
    return db.execute(
        select(FeedEntry)
        .join(Source, FeedEntry.subscription_id == Source.id)
        .where(FeedEntry.id == entry_id, Source.owner_id == owner_id)
    ).scalar_one_or_none()


def set_read(db: Session, entry: FeedEntry, read: bool) -> FeedEntry:
    entry.read_at = datetime.now(UTC) if read else None
    db.commit()
    db.refresh(entry)
    return entry


def set_skipped(db: Session, entry: FeedEntry, skipped: bool) -> FeedEntry:
    """Explicit dismissal, reversible. Skipping also marks the entry seen —
    you looked at it long enough to reject it."""
    entry.skipped_at = datetime.now(UTC) if skipped else None
    if skipped and entry.read_at is None:
        entry.read_at = entry.skipped_at
    db.commit()
    db.refresh(entry)
    return entry


def skip_all(db: Session, sub: Source) -> None:
    """Bulk-dismiss the subscription's undecided entries. Forwarded entries are
    already decided and are left alone."""
    now = datetime.now(UTC)
    db.execute(
        update(FeedEntry)
        .where(FeedEntry.subscription_id == sub.id, *_pending())
        .values(skipped_at=now, read_at=func.coalesce(FeedEntry.read_at, now))
    )
    db.commit()


def gulp_entry(
    db: Session,
    owner_id: uuid.UUID,
    entry: FeedEntry,
    enqueue: Callable[..., None],
) -> tuple[uuid.UUID, bool, SnapshotStatus]:
    """Promote an entry into the snapshot pipeline.

    Forward means *take it in*, never *digest it* (spec 2026-08-01 decision 1):
    the snapshot lands `unprocessed` and waits for an explicit Start, exactly
    like an ad-hoc capture. Only metadata resolution is enqueued — network-only
    title work, no LLM — so the Kept row shows a real title rather than a host.
    """
    if entry.promoted_source_id is not None:
        existing = db.get(Source, entry.promoted_source_id)
        if existing is not None and existing.deleted_at is None:
            return existing.id, True, existing.status
    if not entry.url:
        raise ValueError("entry has no URL to promote")
    req = CaptureRequest(url=entry.url, title=entry.title, captured_via=CapturedVia.feed)
    source, duplicate = create_snapshot(db, owner_id, req)
    if not duplicate:
        source.emitted_by = entry.subscription_id
        db.commit()
        enqueue("resolve_metadata", str(source.id))
    entry.promoted_source_id = source.id
    entry.skipped_at = None  # forwarding a skipped entry un-skips it
    if entry.read_at is None:
        entry.read_at = datetime.now(UTC)
    db.commit()
    return source.id, duplicate, source.status
