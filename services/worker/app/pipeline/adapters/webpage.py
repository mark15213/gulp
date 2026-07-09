"""Webpage/article adapter — fetch, extract main content (trafilatura), and
split the extracted markdown into sectioned NormDoc blocks.

`content_body` IS the extracted markdown, so block anchors slice it exactly.
Headings set the running section label and are not emitted as blocks.

Implementation note (trafilatura 2.1.0): the default markdown output_format
preserves inline formatting (bold/italic/links) correctly, but appends exact
copies of full paragraphs after the structured content. We deduplicate by
keeping only the FIRST occurrence of each paragraph (keyed by stripped text).
"""

import re

import trafilatura

from app.pipeline.normdoc import Anchor, NormBlock, NormDoc

_HEADING = re.compile(r"^#{1,6}\s+(.*\S)\s*$")

# Leading site chrome an aggregator/preprint host prepends to <title>: a
# HuggingFace "Paper page - …" label or an arXiv id "[2607.05061] …". Left in,
# it leaks into the user-visible snapshot title (Library, card source).
_TITLE_CHROME = re.compile(
    r"^\s*(?:\[\d{4}\.\d{4,5}(?:v\d+)?\]\s*|Paper page\s*[-–—:]\s*)+",
    re.IGNORECASE,
)


def _clean_title(title: str | None) -> str | None:
    if title is None:
        return None
    cleaned = _TITLE_CHROME.sub("", title).strip()
    return cleaned or title  # never strip a title down to nothing


def _dedupe(markdown: str) -> str:
    """Remove exact-duplicate paragraphs from trafilatura's markdown output.

    trafilatura 2.1.0 appends exact copies of paragraph text after the
    structured content (a known quirk). We keep the first occurrence of each
    paragraph (keyed by stripped text) and discard subsequent duplicates.
    """
    seen: set[str] = set()
    kept: list[str] = []
    for para in re.split(r"\n\s*\n", markdown):
        key = para.strip()
        if not key:
            continue
        if key not in seen:
            seen.add(key)
            kept.append(para)
    return "\n\n".join(kept)


def extract_markdown(html: str) -> tuple[str, str | None, str | None]:
    md = trafilatura.extract(html, output_format="markdown") or ""
    meta = trafilatura.extract_metadata(html)
    title = meta.title if meta is not None else None
    description = meta.description if meta is not None else None
    return md, title, description


def _split(markdown: str) -> list[NormBlock]:
    blocks: list[NormBlock] = []
    section: str | None = None
    pos = 0
    # iterate paragraphs separated by blank lines, tracking char offsets
    for para in re.split(r"\n\s*\n", markdown):
        start = markdown.find(para, pos)
        if start < 0:
            continue
        end = start + len(para)
        pos = end
        stripped = para.strip()
        if not stripped:
            continue
        m = _HEADING.match(stripped)
        if m:
            section = m.group(1)
            continue
        blocks.append(
            NormBlock(text=para, section_label=section, anchor=Anchor(start=start, end=end))
        )
    return blocks


def webpage_to_normdoc(html: str, *, fallback_title: str, url: str) -> NormDoc:
    raw, title, description = extract_markdown(html)
    body = _dedupe(raw)
    return NormDoc(
        title=_clean_title(title) or fallback_title,
        lang=None,
        media_type="article",
        description=description or None,
        content_body=body,
        blocks=_split(body),
    )
