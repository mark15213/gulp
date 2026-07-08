# services/worker/app/pipeline/figures/match.py
"""Match imported figure blocks ("Figure 3") to extracted SourceFigure rows.

Pure-code matching, no LLM: LaTeX assigns figure numbers in order of figure
environments in the source, so the Nth logical figure in TeX order is
"Figure N". Conservative by design — fallback-scanned figures (no TeX
metadata at all) are skipped because their order is filename-sorted, and an
existing figure_id (a manual link) is never overwritten.
"""

import re

from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
)
from gulp_shared.models.source import Source
from gulp_shared.models.source_figure import SourceFigure
from sqlalchemy import select
from sqlalchemy.orm import Session

_FIG_NUM = re.compile(r"^fig(?:ure)?\.?\s*(\d+)", re.IGNORECASE)


def fig_number(label: str) -> int | None:
    """'Figure 3' / 'Fig. 12: overview' -> 3 / 12; anything else -> None."""
    m = _FIG_NUM.match(label.strip())
    return int(m.group(1)) if m else None


def group_logical(figures: list[SourceFigure]) -> list[SourceFigure]:
    """Collapse subfigure runs into one representative row per logical figure.

    Rows arrive in order_index order. Consecutive rows sharing the same
    (label, caption) — with at least one of the two set — are subfigures of
    one figure environment; the first row represents the group. Returns []
    when no row has any TeX metadata (file-scan fallback).
    """
    if all(f.label is None and f.caption is None for f in figures):
        return []
    logical: list[SourceFigure] = []
    prev_key: tuple[str | None, str | None] | None = None
    for f in figures:
        key = (f.label, f.caption)
        if key != prev_key or key == (None, None):
            logical.append(f)
        prev_key = key
    return logical


def link_figures(db: Session, source: Source) -> int:
    """Fill figure_id on unlinked figure blocks by figure number.

    Flushes but does not commit. Returns the number of blocks linked.
    """
    figures = list(db.scalars(
        select(SourceFigure)
        .where(SourceFigure.source_id == source.id)
        .order_by(SourceFigure.order_index)
    ))
    logical = group_logical(figures) if figures else []
    if not logical:
        return 0
    blocks = db.scalars(
        select(PackBlock)
        .join(PackSection, PackBlock.section_id == PackSection.id)
        .join(KnowledgePack, PackSection.pack_id == KnowledgePack.id)
        .where(
            KnowledgePack.snapshot_id == source.id,
            PackBlock.block_type == PackBlockType.figure,
            PackBlock.deleted_at.is_(None),
        )
    )
    linked = 0
    for block in blocks:
        if block.data.get("figure_id"):
            continue  # a manual link wins
        n = fig_number(block.data.get("label") or "")
        if n is None or not 1 <= n <= len(logical):
            continue
        block.data = {**block.data, "figure_id": str(logical[n - 1].id)}
        linked += 1
    db.flush()
    return linked
