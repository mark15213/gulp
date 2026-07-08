"""Job definitions (arq). `process_snapshot` runs the S2 report pipeline."""

import logging
import uuid
from typing import Any

from arq.connections import RedisSettings
from gulp_shared.db import SessionLocal
from gulp_shared.models.source import SnapshotStatus, Source
from gulp_shared.settings import settings
from sqlalchemy.orm import Session

from app.export.jobs import (
    run_build_cards_export,
    run_build_export,
    run_import_result,
)
from app.pipeline.adapters.fetch import fetch_document
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


class WorkerSettings:
    functions = [
        process_snapshot,
        build_export,
        build_cards_export,
        import_result,
        resolve_metadata,
        generate_cards,
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
