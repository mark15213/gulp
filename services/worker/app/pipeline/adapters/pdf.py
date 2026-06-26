"""PDF adapter — extract born-digital PDF text + title into a NormDoc.

Mirrors the webpage adapter's contract: content_body is the assembled text and
every block anchor slices it exactly (content_body[start:end] == block.text).
"""

import re
from io import BytesIO

from pypdf import PdfReader

from app.pipeline.normdoc import Anchor, NormBlock, NormDoc


def _pdf_title(reader: PdfReader, page1_text: str, fallback: str) -> str:
    meta = reader.metadata
    raw = (meta.title if meta and meta.title else "") or ""
    title = raw.strip()
    if len(title) >= 4:
        return title
    for line in page1_text.splitlines():
        candidate = line.strip()
        if len(candidate) >= 12:
            return candidate[:200]
    return fallback


def pdf_to_normdoc(data: bytes, *, fallback_title: str, url: str) -> NormDoc:
    reader = PdfReader(BytesIO(data))
    paragraphs: list[tuple[str, str]] = []  # (section_label, text)
    page1_text = ""
    for page_no, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if page_no == 1:
            page1_text = text
        for para in re.split(r"\n\s*\n", text):
            stripped = para.strip()
            if stripped:
                paragraphs.append((f"Page {page_no}", stripped))

    blocks: list[NormBlock] = []
    parts: list[str] = []
    pos = 0
    for label, text in paragraphs:
        start = pos
        end = start + len(text)
        blocks.append(NormBlock(text=text, section_label=label, anchor=Anchor(start=start, end=end)))
        parts.append(text)
        pos = end + 2  # the "\n\n" join separator

    content_body = "\n\n".join(parts)
    title = _pdf_title(reader, page1_text, fallback_title)
    return NormDoc(title=title, lang="en", media_type="pdf", content_body=content_body, blocks=blocks)
