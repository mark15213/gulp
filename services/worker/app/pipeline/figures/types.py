# services/worker/app/pipeline/figures/types.py
"""Shared value types for the figure-extraction pipeline."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TexRef:
    path: str            # raw \includegraphics target (extension often omitted)
    label: str | None
    caption: str | None
    order: int


@dataclass(frozen=True)
class ExtractedFigure:
    data: bytes
    ext: str             # normalized stored extension: png|jpg|jpeg|gif|webp
    mime: str            # image/png, image/jpeg, ...
    label: str | None
    caption: str | None
    order: int
    width: int | None
    height: int | None
