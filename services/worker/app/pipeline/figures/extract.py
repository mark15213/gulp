# services/worker/app/pipeline/figures/extract.py
"""Hybrid figure extraction (spec §8): TeX-driven order/caption + file-scan fallback."""

import logging

from app.pipeline.figures.convert import normalize
from app.pipeline.figures.tarball import TarMember, read_tar_gz, resolve_member
from app.pipeline.figures.tex import parse_graphicspath, parse_tex_refs
from app.pipeline.figures.types import ExtractedFigure

logger = logging.getLogger("gulp.worker")

MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_FIGURES = 40
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf")


def _tex_source(members: list[TarMember]) -> str:
    parts = [m.data.decode("utf-8", "replace") for m in members if m.name.lower().endswith(".tex")]
    return "\n".join(parts)


def _make(member: TarMember, order: int) -> ExtractedFigure | None:
    if len(member.data) > MAX_IMAGE_BYTES:
        return None
    norm = normalize(member.name, member.data)
    if norm is None:
        return None
    data, ext, mime, w, h = norm
    return ExtractedFigure(data=data, ext=ext, mime=mime, label=None,
                           caption=None, order=order, width=w, height=h)


def extract_figures(tar_bytes: bytes) -> list[ExtractedFigure]:
    members = read_tar_gz(tar_bytes, max_total=MAX_TOTAL_BYTES)
    if not members:
        return []
    tex = _tex_source(members)
    graphicspath = parse_graphicspath(tex)

    figures: list[ExtractedFigure] = []
    used: set[str] = set()
    for ref in parse_tex_refs(tex):
        member = resolve_member(ref.path, graphicspath, members)
        if member is None or member.name in used:
            continue
        fig = _make(member, len(figures))
        if fig is None:
            continue
        used.add(member.name)
        figures.append(ExtractedFigure(
            **{**fig.__dict__, "label": ref.label, "caption": ref.caption}
        ))
        if len(figures) >= MAX_FIGURES:
            break

    if figures:
        return figures

    # Fallback: file-scan every image-like member (spec §8 step 4), stable order.
    for member in sorted(members, key=lambda m: m.name):
        if not member.name.lower().endswith(_IMAGE_EXTS):
            continue
        fig = _make(member, len(figures))
        if fig is None:
            continue
        figures.append(fig)
        if len(figures) >= MAX_FIGURES:
            break
    if not figures:
        logger.info("extract_figures: no usable figures in tarball")
    return figures
