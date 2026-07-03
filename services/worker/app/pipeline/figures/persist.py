# services/worker/app/pipeline/figures/persist.py
"""Persist extracted figures: clear the source's prior figures, then write
files + rows. Idempotent, mirroring persist_pack (re-run replaces cleanly)."""

import shutil
import uuid

from gulp_shared.media import figure_abspath, media_root
from gulp_shared.models.source import Source
from gulp_shared.models.source_figure import SourceFigure
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.pipeline.figures.types import ExtractedFigure


def persist_figures(
    db: Session, source: Source, figures: list[ExtractedFigure]
) -> list[SourceFigure]:
    db.execute(delete(SourceFigure).where(SourceFigure.source_id == source.id))
    db.flush()
    shutil.rmtree(media_root() / str(source.id), ignore_errors=True)

    rows: list[SourceFigure] = []
    for fig in figures:
        fig_id = uuid.uuid4()
        path = figure_abspath(source.id, fig_id, fig.ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fig.data)
        row = SourceFigure(
            id=fig_id, source_id=source.id, order_index=fig.order,
            label=fig.label, caption=fig.caption, ext=fig.ext,
            mime_type=fig.mime, width=fig.width, height=fig.height,
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows
