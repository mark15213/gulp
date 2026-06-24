"""Webpage/article adapter — fetch, extract main content (trafilatura), and
split the extracted markdown into sectioned NormDoc blocks.

`content_body` IS the extracted markdown, so block anchors slice it exactly.
Headings set the running section label and are not emitted as blocks.

Implementation note (trafilatura 2.1.0): the `markdown` output_format with
include_formatting=True duplicates paragraphs when there are multiple headings.
We use `xml` output instead and rebuild clean markdown ourselves via stdlib
xml.etree.ElementTree, stopping at the first repeated (tag, text) pair to
remove the duplicate tail.
"""

import re
import xml.etree.ElementTree as ET

import httpx
import trafilatura

from app.pipeline.normdoc import Anchor, NormBlock, NormDoc

_HEADING = re.compile(r"^#{1,6}\s+(.*\S)\s*$")


async def fetch_html(url: str) -> str:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url, headers={"User-Agent": "GulpBot/1.0"})
        resp.raise_for_status()
        return resp.text


def _xml_to_markdown(xml: str) -> str:
    """Convert trafilatura XML output to clean markdown.

    Trafilatura 2.1.0 can emit duplicate paragraphs in the XML when there are
    multiple headings (a known quirk). We deduplicate by stopping at the first
    repeated (tag, text) pair.
    """
    tree = ET.fromstring(xml)
    main = tree.find("main")
    if main is None:
        return ""

    seen: list[tuple[str, str | None]] = []
    parts: list[str] = []

    for elem in main:
        key = (elem.tag, elem.text)
        if key in seen:
            # First repeated element — truncate (trafilatura's duplicate tail)
            break
        seen.append(key)

        tag = elem.tag
        text = (elem.text or "").strip()
        if not text:
            continue

        if tag == "head":
            rend = elem.attrib.get("rend", "h1")
            level = int(rend[1]) if len(rend) >= 2 and rend[1:].isdigit() else 1
            parts.append("#" * level + " " + text)
        else:
            parts.append(text)

    return "\n\n".join(parts)


def extract_markdown(html: str) -> tuple[str, str | None]:
    xml = trafilatura.extract(html, output_format="xml", include_formatting=True) or ""
    md = _xml_to_markdown(xml) if xml else ""
    meta = trafilatura.extract_metadata(html)
    title = meta.title if meta is not None else None
    return md, title


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
    markdown, title = extract_markdown(html)
    return NormDoc(
        title=title or fallback_title,
        lang=None,
        media_type="article",
        content_body=markdown,
        blocks=_split(markdown),
    )
