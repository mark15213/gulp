import uuid
from datetime import UTC, datetime

from app.deps import get_enqueue
from app.main import app
from gulp_shared.models import FeedEntry, SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID


def _capture_enqueue(calls):
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: calls.append(a))


def _mk_sub(db, feed_url="rsshub://sspai/index"):
    sub = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.subscription,
        title=feed_url,
        status=SnapshotStatus.ready,
        feed_url=feed_url,
        muted=False,
    )
    db.add(sub)
    db.commit()
    return sub


def _mk_entry(db, sub, **kw):
    e = FeedEntry(
        subscription_id=sub.id,
        guid=kw.pop("guid", str(uuid.uuid4())),
        title=kw.pop("title", "An entry"),
        url=kw.pop("url", "https://example.com/p/1"),
        **kw,
    )
    db.add(e)
    db.commit()
    return e


def test_create_subscription_normalizes_and_enqueues(client, db):
    calls = []
    _capture_enqueue(calls)
    r = client.post("/subscriptions", json={"feed_url": "/github/trending/daily"})
    assert r.status_code == 200
    body = r.json()
    assert body["subscription"]["feed_url"] == "rsshub://github/trending/daily"
    assert body["duplicate"] is False
    assert calls == [("fetch_feed", body["subscription"]["id"])]


def test_create_subscription_idempotent(client, db):
    client.post("/subscriptions", json={"feed_url": "rsshub://sspai/index"})
    r = client.post("/subscriptions", json={"feed_url": "rsshub://sspai/index/"})
    assert r.json()["duplicate"] is True


def test_create_subscription_rejects_garbage(client):
    assert client.post("/subscriptions", json={"feed_url": "nope"}).status_code == 422


def test_list_subscriptions_health_and_unread(client, db):
    sub = _mk_sub(db)
    _mk_entry(db, sub)
    _mk_entry(db, sub, read_at=datetime.now(UTC))
    errored = _mk_sub(db, feed_url="https://bad.example/feed")
    errored.last_fetch_error = "boom"
    db.commit()
    items = {i["feed_url"]: i for i in client.get("/subscriptions").json()["items"]}
    assert items["rsshub://sspai/index"]["unread_count"] == 1
    assert items["rsshub://sspai/index"]["health"] == "active"
    assert items["https://bad.example/feed"]["health"] == "error"


def test_mute_and_delete(client, db):
    sub = _mk_sub(db)
    _mk_entry(db, sub)
    r = client.patch(f"/subscriptions/{sub.id}", json={"muted": True})
    assert r.json()["health"] == "muted"
    assert client.delete(f"/subscriptions/{sub.id}").status_code == 204
    assert client.get("/subscriptions").json()["count"] == 0
    assert db.query(FeedEntry).count() == 0  # entries hard-deleted with the sub


def test_entries_listing_and_read_toggle(client, db):
    sub = _mk_sub(db)
    e = _mk_entry(db, sub)
    r = client.get(f"/subscriptions/{sub.id}/entries")
    assert r.json()["count"] == 1 and r.json()["items"][0]["read"] is False
    client.post(f"/feed-entries/{e.id}/read")
    assert client.get("/feed-entries", params={"unread_only": True}).json()["count"] == 0


def test_gulp_promotes_and_is_idempotent(client, db):
    calls = []
    _capture_enqueue(calls)
    sub = _mk_sub(db)
    e = _mk_entry(db, sub)
    r = client.post(f"/feed-entries/{e.id}/gulp")
    assert r.status_code == 200
    snap_id = r.json()["snapshot_id"]
    snap = db.get(Source, uuid.UUID(snap_id))
    assert snap.kind == SourceKind.snapshot and snap.emitted_by == sub.id
    assert snap.captured_via.value == "feed"
    assert ("process_snapshot", snap_id) in calls
    # idempotent second gulp
    assert client.post(f"/feed-entries/{e.id}/gulp").json()["snapshot_id"] == snap_id


def test_gulp_entry_without_url_is_422(client, db):
    sub = _mk_sub(db)
    e = _mk_entry(db, sub, url=None)
    assert client.post(f"/feed-entries/{e.id}/gulp").status_code == 422
