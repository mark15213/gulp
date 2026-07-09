import pytest
from gulp_shared.domain.feeds import entry_guid, normalize_feed_url, resolve_feed_url


def test_normalize_rsshub_url_passes_through():
    assert normalize_feed_url("rsshub://github/activity/DIYgod") == "rsshub://github/activity/DIYgod"


def test_normalize_strips_whitespace_and_slashes():
    assert normalize_feed_url("  rsshub://sspai/index/  ") == "rsshub://sspai/index"


def test_normalize_bare_route_path_becomes_rsshub():
    assert normalize_feed_url("/github/trending/daily") == "rsshub://github/trending/daily"


def test_normalize_https_passes_through():
    url = "https://www.ruanyifeng.com/blog/atom.xml"
    assert normalize_feed_url(url) == url


@pytest.mark.parametrize("bad", ["", "   ", "rsshub://", "/", "ftp://x", "not a url"])
def test_normalize_rejects_garbage(bad):
    with pytest.raises(ValueError):
        normalize_feed_url(bad)


def test_resolve_rsshub_against_instance():
    assert (
        resolve_feed_url("rsshub://github/activity/DIYgod", "http://localhost:1200")
        == "http://localhost:1200/github/activity/DIYgod"
    )


def test_resolve_plain_url_untouched():
    url = "https://hnrss.org/best"
    assert resolve_feed_url(url, "http://localhost:1200") == url


def test_entry_guid_prefers_feed_id():
    assert entry_guid(" tag:x,2026:1 ", "https://a", "T") == "tag:x,2026:1"


def test_entry_guid_falls_back_to_hash():
    g = entry_guid(None, "https://a/post", "Title")
    assert g.startswith("sha256:") and g == entry_guid("", "https://a/post", "Title")
