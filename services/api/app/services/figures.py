"""Figure gallery queries + on-disk resolution."""

import uuid
from pathlib import Path

from gulp_shared.media import figure_abspath
from gulp_shared.models.source_figure import SourceFigure
from sqlalchemy import select
from sqlalchemy.orm import Session


def list_figures(db: Session, snapshot_id: uuid.UUID) -> list[SourceFigure]:
    return list(
        db.scalars(
            select(SourceFigure)
            .where(SourceFigure.source_id == snapshot_id, SourceFigure.deleted_at.is_(None))
            .order_by(SourceFigure.order_index)
        )
    )


def figure_file(
    db: Session, snapshot_id: uuid.UUID, figure_id: uuid.UUID
) -> tuple[Path, str] | None:
    fig = db.scalar(
        select(SourceFigure).where(
            SourceFigure.id == figure_id,
            SourceFigure.source_id == snapshot_id,
            SourceFigure.deleted_at.is_(None),
        )
    )
    if fig is None:
        return None
    path = figure_abspath(snapshot_id, figure_id, fig.ext)
    if not path.exists():
        return None
    return path, fig.mime_type
