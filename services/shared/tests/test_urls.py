from gulp_shared.domain.urls import normalize_url


def test_strips_fragment_tracking_and_trailing_slash_and_lowercases_host():
    a = normalize_url("https://A.com/Path/?utm_source=x&q=1#frag")
    b = normalize_url("https://a.com/Path?q=1")
    assert a == b == "https://a.com/Path?q=1"


def test_root_keeps_single_slash():
    assert normalize_url("http://a.com") == "http://a.com/"


def test_defaults_missing_scheme_to_https():
    assert normalize_url("a.com/x").startswith("https://a.com/x")
