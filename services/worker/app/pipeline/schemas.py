"""The paper-report structured contract (PaperReport).

The block `type` literals mirror the ORM enum `PackBlockType` exactly, so the
persist stage can map them by string value.
"""

from typing import Annotated, Any, Literal

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
    figure_id: str | None = None
    # article packs: the image lives at its original remote URL, not in SourceFigure
    url: str | None = None


class ListBlock(BaseModel):
    type: Literal["list"] = "list"
    items: list[str]
    ordered: bool = False


class CodeBlock(BaseModel):
    type: Literal["code"] = "code"
    language: str | None = None
    content: str


Block = Annotated[
    ProseBlock | FormulaBlock | TableBlock | FigureBlock | ListBlock | CodeBlock,
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


class PackDraft(BaseModel):
    """The generic persist-boundary contract every pack strategy produces.

    `extras` holds the per-pack_type additions (docs/02 §4.4): the paper
    strategy puts key_insight / core_contributions / references there; the
    preserve strategy leaves it empty.
    """

    title: str
    summary: str | None = None
    pack_type: Literal["paper", "article"]
    extras: dict[str, Any] = Field(default_factory=dict)
    sections: list[Section] = Field(min_length=1)


def draft_from_paper_report(report: PaperReport) -> PackDraft:
    return PackDraft(
        title=report.title,
        pack_type="paper",
        extras={
            "key_insight": report.key_insight,
            "core_contributions": list(report.core_contributions),
            "references": [r.model_dump() for r in report.references],
        },
        sections=report.sections,
    )
