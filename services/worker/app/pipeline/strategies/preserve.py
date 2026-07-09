"""Preserve strategy — deterministic markdown -> PackDraft, zero LLM.

The safe default for every non-paper genre: the pack body IS the source's own
content, re-shaped into the shared section/block substrate. Nothing is
re-authored, so the worst case is "no enrichment", never misrepresentation.

Input is a NormDoc whose `content_body` is markdown (the webpage/pdf/note
adapters all produce that). Anything the classifier below doesn't recognize
stays a verbatim prose block.
"""

import re
from dataclasses import dataclass

from app.pipeline.normdoc import NormDoc
from app.pipeline.schemas import (
    Block,
    CodeBlock,
    FigureBlock,
    FormulaBlock,
    ListBlock,
    PackDraft,
    ProseBlock,
    Section,
    TableBlock,
)

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_FENCE_OPEN = re.compile(r"^```(\S*)\s*$")
_IMAGE_ONLY = re.compile(r"^!\[([^\]]*)\]\(\s*(\S+?)(?:\s+\"[^\"]*\")?\s*\)$")
_TABLE_SEP = re.compile(r"^\|?[\s:\-|]+$")
_BULLET = re.compile(r"^[-*+]\s+(.*\S)\s*$")
_ORDERED = re.compile(r"^\d+[.)]\s+(.*\S)\s*$")

_SUMMARY_MAX = 280


@dataclass
class _Segment:
    kind: str  # "text" | "code"
    content: str
    language: str | None = None


def _split_code_fences(md: str) -> list[_Segment]:
    """Split into alternating text/code segments so nothing inside a fence is
    ever parsed as a heading/table/list. An unclosed fence runs to EOF."""
    segments: list[_Segment] = []
    text_buf: list[str] = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        m = _FENCE_OPEN.match(lines[i])
        if m is None:
            text_buf.append(lines[i])
            i += 1
            continue
        segments.append(_Segment("text", "\n".join(text_buf)))
        text_buf = []
        lang = m.group(1) or None
        code_buf: list[str] = []
        i += 1
        while i < len(lines) and not lines[i].startswith("```"):
            code_buf.append(lines[i])
            i += 1
        i += 1  # skip the closing fence (no-op at EOF)
        segments.append(_Segment("code", "\n".join(code_buf), language=lang))
    segments.append(_Segment("text", "\n".join(text_buf)))
    return segments


def _parse_table(lines: list[str]) -> TableBlock | None:
    if len(lines) < 2:
        return None
    if not all(ln.strip().startswith("|") and ln.strip().endswith("|") for ln in lines):
        return None
    if not _TABLE_SEP.match(lines[1].strip()):
        return None

    def cells(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    headers = cells(lines[0])
    rows = [cells(ln) for ln in lines[2:]]
    return TableBlock(headers=headers, rows=rows)


def _parse_list(lines: list[str]) -> ListBlock | None:
    bullets = [_BULLET.match(ln.strip()) for ln in lines]
    if all(bullets):
        return ListBlock(items=[m.group(1) for m in bullets if m], ordered=False)
    ordered = [_ORDERED.match(ln.strip()) for ln in lines]
    if all(ordered):
        return ListBlock(items=[m.group(1) for m in ordered if m], ordered=True)
    return None


def _classify_paragraph(par: str) -> Block:
    stripped = par.strip()
    m = _IMAGE_ONLY.match(stripped)
    if m:
        return FigureBlock(label=m.group(1) or "Figure", explanation="", url=m.group(2))
    if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4:
        return FormulaBlock(latex=stripped[2:-2].strip(), explanation="")
    lines = [ln for ln in stripped.split("\n") if ln.strip()]
    table = _parse_table(lines)
    if table is not None:
        return table
    lst = _parse_list(lines)
    if lst is not None:
        return lst
    return ProseBlock(content=stripped)


def _sections_from_markdown(md: str) -> list[Section]:
    sections: list[Section] = []
    heading: str | None = None
    blocks: list[Block] = []

    def close() -> None:
        nonlocal blocks, heading
        # keep heading-only sections (faithful structure), drop an empty intro
        if blocks or heading is not None:
            sections.append(Section(heading=heading, blocks=blocks))
        blocks = []

    for seg in _split_code_fences(md):
        if seg.kind == "code":
            blocks.append(CodeBlock(language=seg.language, content=seg.content))
            continue
        for par in re.split(r"\n\s*\n", seg.content):
            stripped = par.strip()
            if not stripped:
                continue
            first, _, rest = stripped.partition("\n")
            m = _HEADING.match(first)
            if m:
                close()
                heading = m.group(2)
                stripped = rest.strip()
                if not stripped:
                    continue
            blocks.append(_classify_paragraph(stripped))
    close()
    if not sections:
        sections = [Section(heading=None, blocks=[ProseBlock(content=md.strip())])]
    return sections


def _first_prose_excerpt(sections: list[Section]) -> str | None:
    for section in sections:
        for block in section.blocks:
            if isinstance(block, ProseBlock) and block.content.strip():
                text = block.content.strip()
                if len(text) <= _SUMMARY_MAX:
                    return text
                return text[:_SUMMARY_MAX].rsplit(" ", 1)[0] + "…"
    return None


def build_preserve_draft(normdoc: NormDoc) -> PackDraft:
    sections = _sections_from_markdown(normdoc.content_body)
    summary = (normdoc.description or "").strip() or _first_prose_excerpt(sections)
    return PackDraft(
        title=normdoc.title,
        summary=summary,
        pack_type="article",
        sections=sections,
    )
