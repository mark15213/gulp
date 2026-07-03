import fitz  # PyMuPDF
from app.pipeline.figures.convert import normalize


def _one_page_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page(width=120, height=90)
    return doc.tobytes()


def test_raster_passthrough_maps_mime() -> None:
    out = normalize("figs/plot.JPG", b"\xff\xd8\xff\xe0rawjpeg")
    assert out is not None
    data, ext, mime, w, h = out
    assert (ext, mime) == ("jpg", "image/jpeg") and data == b"\xff\xd8\xff\xe0rawjpeg"


def test_pdf_is_rendered_to_png_with_dims() -> None:
    out = normalize("figs/arch.pdf", _one_page_pdf())
    assert out is not None
    data, ext, mime, w, h = out
    assert ext == "png" and mime == "image/png"
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and w and h


def test_unsupported_returns_none() -> None:
    assert normalize("old.eps", b"%!PS") is None
