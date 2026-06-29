"""Pack read contract — these become the OpenAPI types the web client reads."""

import uuid
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from gulp_shared.models.knowledge_pack import PackStatus


class ProseBlockOut(BaseModel):
    type: Literal["prose"] = "prose"
    content: str


class FormulaBlockOut(BaseModel):
    type: Literal["formula"] = "formula"
    latex: str
    explanation: str


class TableBlockOut(BaseModel):
    type: Literal["table"] = "table"
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None


class FigureBlockOut(BaseModel):
    type: Literal["figure"] = "figure"
    label: str
    explanation: str


class ListBlockOut(BaseModel):
    type: Literal["list"] = "list"
    items: list[str]
    ordered: bool = False


BlockOut = Annotated[
    Union[ProseBlockOut, FormulaBlockOut, TableBlockOut, FigureBlockOut, ListBlockOut],
    Field(discriminator="type"),
]


class PackSectionOut(BaseModel):
    heading: str | None
    blocks: list[BlockOut]


class PackReferenceOut(BaseModel):
    citation: str
    why_interesting: str


class PackOut(BaseModel):
    snapshot_id: uuid.UUID
    status: PackStatus
    title: str
    core_contributions: list[str]
    key_insight: str
    sections: list[PackSectionOut]
    references: list[PackReferenceOut]
