"""Job definitions (arq). `process_snapshot` runs the S2 report pipeline;
`poll_feeds`/`fetch_feed` run the subscription loop (spec 2026-07-09 §2)."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from arq import cron
from arq.connections import RedisSettings
from gulp_shared.db import SessionLocal
from gulp_shared.models import FeedEntry
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.settings import settings
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.export.jobs import (
    run_build_cards_export,
    run_build_export,
    run_import_result,
)
from app.pipeline.adapters.fetch import fetch_document
from app.pipeline.feeds import run_fetch_feed
from app.pipeline.cards import generate_cards_for_source
from app.pipeline.figures.run import link_imported_figures
from app.pipeline.metadata import run_resolve_metadata
from app.pipeline.run import process_source

logger = logging.getLogger("gulp.worker")


async def process_snapshot(ctx: dict[str, Any], snapshot_id: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("process_snapshot: snapshot %s not found", snapshot_id)
            return
        await process_source(db, source)
    finally:
        db.close()


async def build_export(ctx: dict[str, Any], snapshot_id: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("build_export: snapshot %s not found", snapshot_id)
            return
        await run_build_export(db, source)
    finally:
        db.close()


async def build_cards_export(ctx: dict[str, Any], snapshot_id: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("build_cards_export: snapshot %s not found", snapshot_id)
            return
        run_build_cards_export(db, source)
    finally:
        db.close()


async def import_result(ctx: dict[str, Any], snapshot_id: str, upload_path: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("import_result: snapshot %s not found", snapshot_id)
            return
        with open(upload_path, "rb") as f:
            data = f.read()
        run_import_result(db, source, data)
        if source.status is SnapshotStatus.ready:
            await _maybe_link_figures(db, source)
    finally:
        db.close()


async def _maybe_link_figures(db: Session, source: Source) -> None:
    """Best-effort: the pack is already `ready`; a figure failure must not change that."""
    try:
        await link_imported_figures(db, source, fetch_document)
    except Exception:
        db.rollback()
        logger.exception("figure auto-link failed for %s", source.id)


async def generate_cards(ctx: dict[str, Any], snapshot_id: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("generate_cards: snapshot %s not found", snapshot_id)
            return
        await generate_cards_for_source(db, source)
    finally:
        db.close()


async def resolve_metadata(ctx: dict[str, Any], snapshot_id: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("resolve_metadata: snapshot %s not found", snapshot_id)
            return
        await run_resolve_metadata(db, source)
    finally:
        db.close()


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
