"""Request/response schemas — these become the OpenAPI contract (docs/05 §4)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from gulp_shared.models.source import (
    CapturedVia,
    MediaType,
    SnapshotStatus,
    SourceKind,
)


class CaptureRequest(BaseModel):
    url: str | None = None
    text: str | None = None  # note body
    note: str | None = None  # one-line annotation
    title: str | None = None
    tags: list[str] = []
    captured_via: CapturedVia = CapturedVia.in_app

    @model_validator(mode="after")
    def _exactly_one_of_url_or_text(self) -> "CaptureRequest":
        has_url = bool(self.url and self.url.strip())
        has_text = bool(self.text and self.text.strip())
        if has_url == has_text:
            raise ValueError("provide exactly one of `url` or `text`")
        return self


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: SourceKind
    title: str
    note: str | None
    status: SnapshotStatus
    media_type: MediaType | None
    origin_url: str | None
    content_body: str | None
    captured_via: CapturedVia | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class CaptureResponse(BaseModel):
    snapshot: SnapshotOut
    duplicate: bool


class InboxOut(BaseModel):
    items: list[SnapshotOut]
    count: int
