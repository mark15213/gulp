"""Feeds endpoints — thin (docs/05 D4): parse, call service, return."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from gulp_shared.models import FeedEntry, Source
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db, get_enqueue
from app.schemas.feeds import (
    CatalogSearchOut,
    FeedEntriesOut,
    GulpEntryResponse,
    SubscriptionCreate,
    SubscriptionCreateResponse,
    SubscriptionOut,
    SubscriptionPatch,
    SubscriptionsOut,
)
from app.services import feeds as svc
from app.services.catalog import search_catalog

router = APIRouter()


@router.post("/subscriptions", response_model=SubscriptionCreateResponse)
def create_subscription(
    req: SubscriptionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> SubscriptionCreateResponse:
    try:
        sub, duplicate = svc.create_subscription(db, user.id, req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not duplicate:
        enqueue("fetch_feed", str(sub.id))
    unread = svc.unread_counts(db, [sub.id]).get(sub.id, 0)
    return SubscriptionCreateResponse(
        subscription=svc.to_subscription_out(sub, unread), duplicate=duplicate
    )


@router.get("/subscriptions", response_model=SubscriptionsOut)
def list_subscriptions(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SubscriptionsOut:
    items = svc.list_subscriptions(db, user.id)
    return SubscriptionsOut(items=items, count=len(items))


def _sub_or_404(db: Session, user: User, sub_id: uuid.UUID) -> Source:
    sub = svc.get_subscription(db, user.id, sub_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    return sub


@router.patch("/subscriptions/{sub_id}", response_model=SubscriptionOut)
def patch_subscription(
    sub_id: uuid.UUID,
    patch: SubscriptionPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubscriptionOut:
    sub = svc.update_subscription(db, _sub_or_404(db, user, sub_id), patch)
    unread = svc.unread_counts(db, [sub.id]).get(sub.id, 0)
    return svc.to_subscription_out(sub, unread)


@router.delete("/subscriptions/{sub_id}", status_code=204)
def delete_subscription(
    sub_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    svc.delete_subscription(db, _sub_or_404(db, user, sub_id))


@router.post("/subscriptions/{sub_id}/refresh", status_code=202)
def refresh_subscription(
    sub_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> None:
    sub = _sub_or_404(db, user, sub_id)
    enqueue("fetch_feed", str(sub.id))


@router.post("/subscriptions/{sub_id}/read-all", status_code=204)
def read_all(
    sub_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    svc.mark_all_read(db, _sub_or_404(db, user, sub_id))


@router.get("/subscriptions/{sub_id}/entries", response_model=FeedEntriesOut)
def subscription_entries(
    sub_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedEntriesOut:
    _sub_or_404(db, user, sub_id)
    rows, count = svc.list_entries(db, user.id, sub_id, unread_only, limit, offset)
    return FeedEntriesOut(items=[svc.to_entry_out(e, t, st) for e, t, st in rows], count=count)


@router.get("/feed-entries", response_model=FeedEntriesOut)
def all_entries(
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedEntriesOut:
    rows, count = svc.list_entries(db, user.id, None, unread_only, limit, offset)
    return FeedEntriesOut(items=[svc.to_entry_out(e, t, st) for e, t, st in rows], count=count)


def _entry_or_404(db: Session, user: User, entry_id: uuid.UUID) -> FeedEntry:
    entry = svc.get_entry(db, user.id, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="entry not found")
    return entry


@router.post("/feed-entries/{entry_id}/read", status_code=204)
def mark_read(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    svc.set_read(db, _entry_or_404(db, user, entry_id), True)


@router.post("/feed-entries/{entry_id}/unread", status_code=204)
def mark_unread(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    svc.set_read(db, _entry_or_404(db, user, entry_id), False)


@router.post("/feed-entries/{entry_id}/gulp", response_model=GulpEntryResponse)
def gulp_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> GulpEntryResponse:
    entry = _entry_or_404(db, user, entry_id)
    try:
        snapshot_id, duplicate, status = svc.gulp_entry(db, user.id, entry, enqueue)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return GulpEntryResponse(snapshot_id=snapshot_id, duplicate=duplicate, status=status)


@router.get("/feeds/catalog/search", response_model=CatalogSearchOut)
def catalog_search(
    q: str = "",
    limit: int = 30,
    user: User = Depends(get_current_user),
) -> CatalogSearchOut:
    items = search_catalog(q, limit=limit)
    return CatalogSearchOut(items=items, count=len(items))
