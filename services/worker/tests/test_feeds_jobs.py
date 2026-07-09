from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.tasks import _feed_due


def _sub(**kw):
    defaults = dict(last_fetch_at=None, consecutive_failures=None)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


NOW = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)


def test_never_fetched_is_due():
    assert _feed_due(_sub(), NOW)


def test_recently_fetched_not_due():
    assert not _feed_due(_sub(last_fetch_at=NOW - timedelta(minutes=5)), NOW)


def test_stale_is_due():
    assert _feed_due(_sub(last_fetch_at=NOW - timedelta(minutes=31)), NOW)


def test_failing_feed_backs_off_to_daily():
    sub = _sub(last_fetch_at=NOW - timedelta(hours=2), consecutive_failures=5)
    assert not _feed_due(sub, NOW)
    assert _feed_due(_sub(last_fetch_at=NOW - timedelta(hours=25), consecutive_failures=5), NOW)


def test_naive_timestamp_tolerated():  # sqlite loses tzinfo
    assert _feed_due(_sub(last_fetch_at=(NOW - timedelta(hours=1)).replace(tzinfo=None)), NOW)
