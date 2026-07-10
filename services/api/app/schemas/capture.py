"""Request/response schemas — these become the OpenAPI contract (docs/05 §4)."""

import uuid
from datetime import datetime
from typing import Annotated

from gulp_shared.domain.urls import is_http_url
from gulp_shared.models.source import (
    CapturedVia,
    CardsStatus,
    MediaType,
    SnapshotStatus,
    SourceGenre,
    SourceKind,
)
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator


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
        if has_url and not is_http_url(self.url):  # type: ignore[arg-type]
            raise ValueError("url is not a valid http(s) URL")
        return self


class SourceFeedOut(BaseModel):
    """The subscription feed that produced a snapshot (derived from
    Source.emitted_by); null for ad-hoc captures."""

    id: uuid.UUID
    title: str


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: SourceKind
    title: str
    note: str | None
    status: SnapshotStatus
    media_type: MediaType | None
    genre: SourceGenre | None
    origin_url: str | None
    content_body: str | None
    captured_via: CapturedVia | None
    cards_status: CardsStatus | None
    tags: list[str]
    source_feed: SourceFeedOut | None = None
    created_at: datetime
    updated_at: datetime


class SnapshotPatch(BaseModel):
    """Curation-time corrections; genre re-selects the processing strategy on
    the next re-run."""

    genre: SourceGenre


class TagCreate(BaseModel):
    tag: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CaptureResponse(BaseModel):
    snapshot: SnapshotOut
    duplicate: bool


class InboxOut(BaseModel):
    items: list[SnapshotOut]
    count: int


class LibraryOut(BaseModel):
    items: list[SnapshotOut]
    count: int
