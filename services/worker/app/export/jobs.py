"""Export orchestration cores — testable with injected fetch / export_dir."""

import logging
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from gulp_shared.models.knowledge_pack import KnowledgePack, PackStatus
from gulp_shared.models.source import (
    MediaType,
    SnapshotStatus,
    Source,
)
from gulp_shared.settings import settings
from gulp_shared.urls import host_of
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.export.builder import build_cards_job_archive, build_job_archive
from app.export.importer import import_result_archive
from app.pipeline.adapters.fetch import FetchedDoc, fetch_document
from app.pipeline.cards import render_conversation, render_pack_text
from app.pipeline.persist import persist_pack
from app.pipeline.run import _to_normdoc
from app.pipeline.schemas import draft_from_paper_report

logger = logging.getLogger("gulp.worker")

FetchFn = Callable[[str], Awaitable[FetchedDoc]]


async def run_build_export(
    db: Session,
    source: Source,
    *,
    fetch: FetchFn = fetch_document,
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
        if (
            source.origin_url
            and source.title == host_of(source.origin_url)
            and normdoc.title
            and normdoc.title != source.title
        ):
            source.title = normdoc.title
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


def run_build_cards_export(
    db: Session,
    source: Source,
    *,
    export_dir: str | None = None,
    now: str | None = None,
) -> str:
    """Package a card-generation job (rendered pack + conversation) as a zip the
    user can run in Claude Code / Codex, then import the result via cards.json.
    Cheap and offline — the pack already exists, so there is no fetch."""
    out_dir = export_dir or settings.export_dir
    pack = db.scalar(
        select(KnowledgePack).where(KnowledgePack.snapshot_id == source.id)
    )
    if pack is None or pack.status is not PackStatus.ready:
        raise ValueError("no ready pack to build a cards job from")
    data = build_cards_job_archive(
        snapshot_id=str(source.id),
        owner_id=str(source.owner_id),
        pack_text=render_pack_text(pack),
        conversation_text=render_conversation(db, pack),
        created_at=now or datetime.now(UTC).isoformat(),
    )
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{source.id}-cards.zip")
    with open(path, "wb") as f:
        f.write(data)
    return path


def run_import_result(db: Session, source: Source, data: bytes) -> None:
    try:
        digest = import_result_archive(data)
        persist_pack(db, source, draft_from_paper_report(digest))
        source.status = SnapshotStatus.ready
        db.commit()
    except Exception:
        db.rollback()
        source.status = SnapshotStatus.exported
        db.commit()
        logger.exception("import_result failed for %s", source.id)
