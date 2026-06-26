"""Export orchestration cores — testable with injected fetch / export_dir."""

import logging
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.export.builder import build_job_archive
from app.export.importer import import_result_archive
from app.pipeline.adapters.webpage import fetch_html
from app.pipeline.persist import persist_pack
from app.pipeline.run import _to_normdoc
from gulp_shared.models.source import MediaType, SnapshotStatus, Source  # type: ignore[import-untyped]
from gulp_shared.settings import settings  # type: ignore[import-untyped]

logger = logging.getLogger("gulp.worker")

FetchFn = Callable[[str], Awaitable[str]]


async def run_build_export(
    db: Session,
    source: Source,
    *,
    fetch: FetchFn = fetch_html,
    export_dir: str | None = None,
    now: str | None = None,
) -> str:
    out_dir = export_dir or settings.export_dir
    try:
        normdoc = await _to_normdoc(source, fetch)
        if not normdoc.content_body.strip():
            raise ValueError("extraction produced no content")
        source.content_body = normdoc.content_body
        source.media_type = MediaType(normdoc.media_type)
        data = build_job_archive(
            snapshot_id=str(source.id),
            owner_id=str(source.owner_id),
            normdoc=normdoc,
            created_at=now or datetime.now(UTC).isoformat(),
        )
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{source.id}.zip")
        with open(path, "wb") as f:
            f.write(data)
        source.status = SnapshotStatus.exported
        db.commit()
        return path
    except Exception:
        db.rollback()
        source.status = SnapshotStatus.needs_attention
        db.commit()
        logger.exception("build_export failed for %s", source.id)
        raise


def run_import_result(db: Session, source: Source, data: bytes) -> None:
    try:
        digest = import_result_archive(data)
        persist_pack(db, source, digest)
        source.status = SnapshotStatus.ready
        db.commit()
    except Exception:
        db.rollback()
        source.status = SnapshotStatus.exported
        db.commit()
        logger.exception("import_result failed for %s", source.id)
