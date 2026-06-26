"""Job definitions (arq). `process_snapshot` runs the S2 report pipeline."""

import logging
import uuid

from arq.connections import RedisSettings

from app.export.jobs import run_build_export, run_import_result
from app.pipeline.metadata import run_resolve_metadata
from app.pipeline.run import process_source
from gulp_shared.db import SessionLocal  # type: ignore[import-untyped]
from gulp_shared.models.source import Source  # type: ignore[import-untyped]
from gulp_shared.settings import settings  # type: ignore[import-untyped]

logger = logging.getLogger("gulp.worker")


async def process_snapshot(ctx: dict, snapshot_id: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("process_snapshot: snapshot %s not found", snapshot_id)
            return
        await process_source(db, source)
    finally:
        db.close()


async def build_export(ctx: dict, snapshot_id: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("build_export: snapshot %s not found", snapshot_id)
            return
        await run_build_export(db, source)
    finally:
        db.close()


async def import_result(ctx: dict, snapshot_id: str, upload_path: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("import_result: snapshot %s not found", snapshot_id)
            return
        with open(upload_path, "rb") as f:
            data = f.read()
        run_import_result(db, source, data)
    finally:
        db.close()


async def resolve_metadata(ctx: dict, snapshot_id: str) -> None:
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
    functions = [process_snapshot, build_export, import_result, resolve_metadata]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
