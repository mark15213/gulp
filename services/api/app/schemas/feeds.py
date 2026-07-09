"""Feeds contract (spec 2026-07-09 §3): subscriptions, entries, promotion."""

import uuid
from datetime import datetime
from typing import Literal

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
    unread_count: int
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
    read: bool
    promoted_source_id: uuid.UUID | None
    created_at: datetime


class FeedEntriesOut(BaseModel):
    items: list[FeedEntryOut]
    count: int


class GulpEntryResponse(BaseModel):
    snapshot_id: uuid.UUID
    duplicate: bool


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
