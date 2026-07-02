"""NormDoc — the unified intermediate representation every input adapter
produces (S2 design §2.1-2.2). All downstream LLM work sees only this.

Anchors are char offsets into `content_body`: for every block,
`content_body[anchor.start:anchor.end] == block.text`.
"""

from pydantic import BaseModel, model_validator


def _clean_text(s: str) -> str:
    """Replace characters no downstream store can hold with U+FFFD.

    pypdf text extraction and html.unescape can emit two kinds of un-storable
    characters from broken encodings:
      - lone UTF-16 surrogate code points (U+D800–U+DFFF): not UTF-8 encodable,
        so they crash JSON serialization (the export builder);
      - NUL (U+0000): UTF-8/JSON accept it, but PostgreSQL text fields reject it,
        so it crashes the content_body DB write.
    The replacement is length-preserving (one code point → one), so NormDoc
    anchor offsets keep slicing content_body exactly.
    """

    def _bad(c: str) -> bool:
        return c == "\x00" or "\ud800" <= c <= "\udfff"

    if not any(_bad(c) for c in s):
        return s
    return "".join("�" if _bad(c) else c for c in s)


class Anchor(BaseModel):
    kind: str = "char_range"
    start: int
    end: int


class NormBlock(BaseModel):
    text: str
    section_label: str | None = None
    anchor: Anchor


class NormDoc(BaseModel):
    title: str
    lang: str | None = None
    media_type: str
    content_body: str
    blocks: list[NormBlock]

    @model_validator(mode="after")
    def _clean_text_fields(self) -> "NormDoc":
        # Single choke point: every adapter (pdf/webpage/note) flows through
        # NormDoc, so downstream (export JSON, DB persist, LLM) never sees an
        # un-encodable string. Length-preserving, so anchors stay valid.
        self.title = _clean_text(self.title)
        self.content_body = _clean_text(self.content_body)
        for block in self.blocks:
            block.text = _clean_text(block.text)
            if block.section_label is not None:
                block.section_label = _clean_text(block.section_label)
        return self
