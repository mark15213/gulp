"""Note adapter — the trivial case: the body is its own single block."""

from app.pipeline.normdoc import Anchor, NormBlock, NormDoc


def note_to_normdoc(title: str, body: str) -> NormDoc:
    block = NormBlock(text=body, anchor=Anchor(start=0, end=len(body)))
    return NormDoc(
        title=title,
        lang=None,
        media_type="note",
        content_body=body,
        blocks=[block],
    )
