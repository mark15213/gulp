"""Genre detection heuristics — pure code, no LLM."""

import pytest
from app.pipeline.classify import detect_genre
from gulp_shared.models.source import SourceGenre


@pytest.mark.parametrize(
    ("url", "media_type", "expected"),
    [
        (None, "note", SourceGenre.note),
        ("https://arxiv.org/abs/2607.00123", "pdf", SourceGenre.paper),
        ("https://arxiv.org/pdf/2607.00123v2", "pdf", SourceGenre.paper),
        ("http://export.arxiv.org/abs/2607.00123", "article", SourceGenre.paper),
        ("https://openreview.net/forum?id=xyz", "article", SourceGenre.paper),
        # any PDF defaults to paper (user-correctable via genre)
        ("https://example.com/whitepaper.pdf", "pdf", SourceGenre.paper),
        # the motivating case: a technical blog is an article, not a paper
        ("https://lilianweng.github.io/posts/2026-07-04-harness/", "article", SourceGenre.article),
        ("https://example.com/post", "webpage", SourceGenre.article),
        # host must match as a domain label, not a substring
        ("https://notarxiv.org/abs/1", "article", SourceGenre.article),
    ],
)
def test_detect_genre(url: str | None, media_type: str, expected: SourceGenre) -> None:
    assert detect_genre(url, media_type) == expected
