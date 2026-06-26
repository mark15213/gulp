from gulp_shared.domain.urls import normalize_url


def test_strips_fragment_tracking_and_trailing_slash_and_lowercases_host():
    a = normalize_url("https://A.com/Path/?utm_source=x&q=1#frag")
    b = normalize_url("https://a.com/Path?q=1")
    assert a == b == "https://a.com/Path?q=1"


def test_root_keeps_single_slash():
    assert normalize_url("http://a.com") == "http://a.com/"


def test_defaults_missing_scheme_to_https():
    assert normalize_url("a.com/x") == "https://a.com/x"


def test_is_http_url_accepts_and_rejects():
    from gulp_shared.domain.urls import is_http_url
    assert is_http_url("https://a.com/x")
    assert is_http_url("a.com/x")        # scheme-less ok
    assert not is_http_url("javascript:alert(1)")
    assert not is_http_url("data:text/html,x")
    assert not is_http_url("note: buy milk")


def test_normalize_url_does_not_raise_on_bad_port():
    from gulp_shared.domain.urls import normalize_url
    normalize_url("http://h:notaport/x")   # must not raise


def test_host_of_extracts_hostname():
    from gulp_shared.urls import host_of
    assert host_of("https://arxiv.org/pdf/2606.27377") == "arxiv.org"
    assert host_of("http://example.com/a?b=1") == "example.com"


def test_host_of_falls_back_to_the_raw_string():
    from gulp_shared.urls import host_of
    assert host_of("not a url") == "not a url"
