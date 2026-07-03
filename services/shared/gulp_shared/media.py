"""On-disk layout for stored media (paper figures). Worker writes; API reads.
One definition so the two never disagree: media_dir/<source_id>/<figure_id>.<ext>."""

import uuid
from pathlib import Path

from gulp_shared.settings import settings


def media_root() -> Path:
    return Path(settings.media_dir)


def figure_relpath(source_id: uuid.UUID, figure_id: uuid.UUID, ext: str) -> str:
    return f"{source_id}/{figure_id}.{ext}"


def figure_abspath(source_id: uuid.UUID, figure_id: uuid.UUID, ext: str) -> Path:
    return media_root() / str(source_id) / f"{figure_id}.{ext}"
