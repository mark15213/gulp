"""Feeds contract (spec 2026-07-09 §3): subscriptions, entries, promotion."""

import uuid
from datetime import datetime
from typing import Literal

from gulp_shared.models import SnapshotStatus
from pydantic import BaseModel

SubscriptionHealth = Literal["active", "muted", "error"]


class SubscriptionCreate(BaseModel):
    feed_url: str
    title: str | None = None


class SubscriptionPatch(BaseModel):
    title: str | None = None
    muted: bool | None = None


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    title: str
    feed_url: str
    health: SubscriptionHealth
    muted: bool
    # Undecided entries: neither forwarded nor skipped. "Seen" is not decided,
    # so this is not an unread count (spec 2026-08-01 §3.1).
    pending_count: int
    last_fetch_at: datetime | None
    last_fetch_error: str | None
    created_at: datetime


class SubscriptionCreateResponse(BaseModel):
    subscription: SubscriptionOut
    duplicate: bool


class SubscriptionsOut(BaseModel):
    items: list[SubscriptionOut]
    count: int


class FeedEntryOut(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID
    subscription_title: str
    title: str
    url: str | None
    author: str | None
    published_at: datetime | None
    content_html: str | None
    # `read` is cosmetic ("seen" — drives dimming). The triage state is
    # derived from `skipped` + `promoted_source_id`: forwarded > skipped >
    # pending. No promoted_status: a forwarded entry's snapshot is one Inbox
    # section below, so nothing needs mirroring (spec 2026-08-01 §1).
    read: bool
    skipped: bool
    promoted_source_id: uuid.UUID | None
    created_at: datetime


class FeedEntriesOut(BaseModel):
    items: list[FeedEntryOut]
    count: int


class GulpEntryResponse(BaseModel):
    snapshot_id: uuid.UUID
    duplicate: bool
    # `unprocessed` for a fresh forward — Forward takes the item in, it never
    # digests it — or the existing status when the entry was already forwarded.
    status: SnapshotStatus


class CatalogRouteOut(BaseModel):
    namespace: str
    namespace_name: str
    route_path: str
    route_name: str | None
    example: str | None
    parameters: dict[str, str] | None
    require_config: bool
    heat: int


class CatalogSearchOut(BaseModel):
    items: list[CatalogRouteOut]
    count: int
