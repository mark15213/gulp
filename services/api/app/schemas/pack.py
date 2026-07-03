"""Pack read contract — these become the OpenAPI types the web client reads."""

import uuid
from typing import Annotated, Literal

from gulp_shared.models.knowledge_pack import PackStatus
from pydantic import BaseModel, Field, TypeAdapter


class ProseBlockOut(BaseModel):
    id: uuid.UUID
    type: Literal["prose"] = "prose"
    content: str


class FormulaBlockOut(BaseModel):
    id: uuid.UUID
    type: Literal["formula"] = "formula"
    latex: str
    explanation: str


class TableBlockOut(BaseModel):
    id: uuid.UUID
    type: Literal["table"] = "table"
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None


class FigureBlockOut(BaseModel):
    id: uuid.UUID
    type: Literal["figure"] = "figure"
    label: str
    explanation: str
    figure_id: uuid.UUID | None = None


class ListBlockOut(BaseModel):
    id: uuid.UUID
    type: Literal["list"] = "list"
    items: list[str]
    ordered: bool = False


class ProseWrite(BaseModel):
    type: Literal["prose"] = "prose"
    content: str


class FormulaWrite(BaseModel):
    type: Literal["formula"] = "formula"
    latex: str
    explanation: str


class TableWrite(BaseModel):
    type: Literal["table"] = "table"
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None


class FigureWrite(BaseModel):
    type: Literal["figure"] = "figure"
    label: str
    explanation: str
    figure_id: uuid.UUID | None = None


class ListWrite(BaseModel):
    type: Literal["list"] = "list"
    items: list[str]
    ordered: bool = False


BlockOut = Annotated[
    ProseBlockOut | FormulaBlockOut | TableBlockOut | FigureBlockOut | ListBlockOut,
    Field(discriminator="type"),
]

BlockWrite = Annotated[
    ProseWrite | FormulaWrite | TableWrite | FigureWrite | ListWrite,
    Field(discriminator="type"),
]
BlockWriteAdapter: TypeAdapter[BlockWrite] = TypeAdapter(BlockWrite)


class BlockUpdate(BaseModel):
    content: BlockWrite | None = None
    position: int | None = None


class BlockCreate(BaseModel):
    content: BlockWrite
    position: int


class PackSectionOut(BaseModel):
    id: uuid.UUID
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
