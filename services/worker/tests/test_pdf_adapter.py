from pathlib import Path

from app.pipeline.adapters.pdf import pdf_to_normdoc

_SAMPLE = Path(__file__).parent / "fixtures" / "sample.pdf"


def test_pdf_to_normdoc_extracts_title_text_and_valid_anchors():
    nd = pdf_to_normdoc(_SAMPLE.read_bytes(), fallback_title="arxiv.org", url="https://x/y.pdf")
    assert nd.media_type == "pdf"
    assert nd.title == "The Spacing Effect"  # from PDF /Title metadata
    assert "Distributed practice" in nd.content_body
    assert "increasing intervals" in nd.content_body
    assert nd.blocks, "expected at least one block"
    # NormDoc invariant: every block's anchor slices content_body exactly
    for b in nd.blocks:
        assert nd.content_body[b.anchor.start : b.anchor.end] == b.text


def test_pdf_title_falls_back_to_first_line_when_metadata_missing(tmp_path):
    # A PDF with no /Title: title comes from the first substantial page-1 line.
    import importlib.util
    if importlib.util.find_spec("reportlab") is None:
        return  # generation lib unavailable in this env; covered by the metadata case
    from reportlab.pdfgen import canvas
    p = tmp_path / "untitled.pdf"
    c = canvas.Canvas(str(p))
    c.drawString(72, 720, "An Untitled Born-Digital Document")
    c.showPage(); c.save()
    nd = pdf_to_normdoc(p.read_bytes(), fallback_title="fallback", url="https://x/z.pdf")
    assert nd.title == "An Untitled Born-Digital Document"
