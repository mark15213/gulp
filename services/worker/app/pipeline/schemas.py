"""The digest LLM's structured response contract (S2 design §2.5/§3).

The `Literal` values mirror the ORM enums `PackBlockType` / `PackElementType`
exactly, so the persist stage can map them by string value.
"""

from typing import Literal

from pydantic import BaseModel


class DigestBlock(BaseModel):
    type: Literal["prose", "callout", "quote"] = "prose"
    content: str


class DigestSection(BaseModel):
    heading: str | None = None
    blocks: list[DigestBlock]


class DigestFacet(BaseModel):
    element_type: Literal["key_term", "person_org", "claim", "counter_view", "connection"]
    text: str


class DigestResult(BaseModel):
    summary: str
    background: str | None = None
    confidence: float = 0.7
    sections: list[DigestSection]
    facets: list[DigestFacet]
