"""The paper-report structured contract (PaperReport).

The block `type` literals mirror the ORM enum `PackBlockType` exactly, so the
persist stage can map them by string value.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class ProseBlock(BaseModel):
    type: Literal["prose"] = "prose"
    content: str


class FormulaBlock(BaseModel):
    type: Literal["formula"] = "formula"
    latex: str
    explanation: str


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None


class FigureBlock(BaseModel):
    type: Literal["figure"] = "figure"
    label: str
    explanation: str


class ListBlock(BaseModel):
    type: Literal["list"] = "list"
    items: list[str]
    ordered: bool = False


Block = Annotated[
    Union[ProseBlock, FormulaBlock, TableBlock, FigureBlock, ListBlock],
    Field(discriminator="type"),
]


class Section(BaseModel):
    heading: str
    blocks: list[Block]


class Reference(BaseModel):
    citation: str
    why_interesting: str


class PaperReport(BaseModel):
    title: str
    core_contributions: list[str] = Field(min_length=1, max_length=5)
    key_insight: str
    sections: list[Section] = Field(min_length=1)
    references: list[Reference] = Field(default_factory=list)
