"""Normalize a figure file to a web-displayable raster (spec §5.2).

Raster (png/jpg/jpeg/gif/webp) passes through; PDF renders page 0 to PNG via
PyMuPDF (pure wheel, no system deps). EPS / vector-only return None (skipped)."""

import logging

import fitz  # PyMuPDF

logger = logging.getLogger("gulp.worker")

_RASTER_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}
_PDF_DPI = 150


def normalize(name: str, data: bytes) -> tuple[bytes, str, str, int | None, int | None] | None:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext in _RASTER_MIME:
        return (data, ext, _RASTER_MIME[ext], None, None)
    if ext == "pdf":
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            if doc.page_count == 0:
                return None
            pix = doc.load_page(0).get_pixmap(dpi=_PDF_DPI)
            return (pix.tobytes("png"), "png", "image/png", pix.width, pix.height)
        except Exception:
            logger.debug("normalize: failed to render PDF %r to PNG", name, exc_info=True)
            return None
    return None
