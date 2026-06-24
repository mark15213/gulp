"""NormDoc — the unified intermediate representation every input adapter
produces (S2 design §2.1-2.2). All downstream LLM work sees only this.

Anchors are char offsets into `content_body`: for every block,
`content_body[anchor.start:anchor.end] == block.text`.
"""

from pydantic import BaseModel


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
