"""Pack read contract — these become the OpenAPI types the web client reads."""

import uuid

from pydantic import BaseModel

from gulp_shared.models.knowledge_pack import PackBlockType, PackElementType, PackStatus


class PackBlockOut(BaseModel):
    type: PackBlockType
    content: str | None
    anchor_id: str


class PackSectionOut(BaseModel):
    heading: str | None
    blocks: list[PackBlockOut]


class PackFacetOut(BaseModel):
    element_type: PackElementType
    text: str | None


class PackOut(BaseModel):
    snapshot_id: uuid.UUID
    status: PackStatus
    summary: str
    background: str | None
    confidence: float | None
    sections: list[PackSectionOut]
    facets: list[PackFacetOut]
