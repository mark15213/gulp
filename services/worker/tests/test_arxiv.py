
from app.pipeline.adapters.arxiv import (
    arxiv_abs_url,
    arxiv_eprint_url,
    arxiv_id,
    arxiv_title,
    is_arxiv,
)
from app.pipeline.adapters.fetch import FetchedDoc

_ABS_HTML = (
    '<html><head>'
    '<meta name="citation_title" content="Attention Is All You Need">'
    '<title>[1706.03762] Attention Is All You Need</title>'
    '</head><body>...</body></html>'
)


def test_arxiv_abs_url_normalizes_the_url_forms():
    assert arxiv_abs_url("https://arxiv.org/pdf/1706.03762") == "https://arxiv.org/abs/1706.03762"
    assert arxiv_abs_url("https://arxiv.org/pdf/1706.03762v7") == "https://arxiv.org/abs/1706.03762v7"
    assert arxiv_abs_url("https://arxiv.org/pdf/1706.03762.pdf") == "https://arxiv.org/abs/1706.03762"
    assert arxiv_abs_url("https://arxiv.org/abs/1706.03762") == "https://arxiv.org/abs/1706.03762"
    assert arxiv_abs_url("https://arxiv.org/abs/cs/0112017") == "https://arxiv.org/abs/cs/0112017"


def test_arxiv_abs_url_returns_none_for_non_arxiv():
    assert arxiv_abs_url("https://example.com/pdf/x") is None
    assert arxiv_abs_url("https://arxiv.org/list/cs.CL/recent") is None
    assert arxiv_abs_url("not a url") is None


async def test_arxiv_title_reads_citation_title():
    async def _fetch(url: str) -> FetchedDoc:
        assert url == "https://arxiv.org/abs/1706.03762"
        return FetchedDoc(content=_ABS_HTML.encode(), content_type="text/html")

    title = await arxiv_title("https://arxiv.org/pdf/1706.03762", fetch=_fetch)
    assert title == "Attention Is All You Need"


async def test_arxiv_title_non_arxiv_returns_none_without_fetching():
    async def _fetch(url: str) -> FetchedDoc:
        raise AssertionError("must not fetch for a non-arxiv url")

    assert await arxiv_title("https://example.com/p.pdf", fetch=_fetch) is None


async def test_arxiv_title_swallows_failures():
    async def _boom(url: str) -> FetchedDoc:
        raise RuntimeError("network down")

    assert await arxiv_title("https://arxiv.org/pdf/1706.03762", fetch=_boom) is None


def test_arxiv_id_normalizes_all_forms() -> None:
    cases = {
        "https://arxiv.org/abs/2606.17162": "2606.17162",
        "https://arxiv.org/pdf/2606.17162": "2606.17162",
        "https://arxiv.org/pdf/2606.17162.pdf": "2606.17162",
        "https://arxiv.org/pdf/2606.17162v2": "2606.17162v2",
        "https://arxiv.org/pdf/2606.17162v2.pdf": "2606.17162v2",
        "http://www.arxiv.org/abs/2606.17162": "2606.17162",
        "https://export.arxiv.org/pdf/2606.17162": "2606.17162",
        "https://arxiv.org/abs/cs/0112017": "cs/0112017",
        "https://arxiv.org/abs/2606.17162v2?foo=1#s": "2606.17162v2",
        "https://arxiv.org/abs/2606.17162/": "2606.17162",
    }
    for url, want in cases.items():
        assert arxiv_id(url) == want, url


def test_arxiv_id_rejects_non_papers() -> None:
    assert arxiv_id("https://example.com/pdf/x") is None
    assert arxiv_id("https://arxiv.org/list/cs.CL/recent") is None
    assert arxiv_id("https://arxiv.org/pdf/") is None
    assert arxiv_id("not a url") is None


def test_arxiv_eprint_url_and_is_arxiv() -> None:
    assert arxiv_eprint_url("https://arxiv.org/pdf/2606.17162v2") == "https://arxiv.org/e-print/2606.17162v2"
    assert arxiv_eprint_url("https://example.com/x") is None
    assert is_arxiv("https://arxiv.org/abs/2606.17162") is True
    assert is_arxiv("https://example.com/x") is False
