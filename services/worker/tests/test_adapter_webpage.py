from app.pipeline.adapters.webpage import webpage_to_normdoc

# A minimal article. trafilatura extracts the <article> main content.
HTML = """
<html><head><title>Attention Explained</title></head>
<body>
<nav>home about</nav>
<article>
<h1>Attention</h1>
<p>Attention lets a model weigh tokens by relevance in the input sequence.</p>
<h2>Self-Attention</h2>
<p>Each token attends to every other token in the sequence to build context representations.</p>
</article>
<footer>copyright</footer>
</body></html>
"""

# An article with inline formatting to verify no inline-text truncation.
HTML_INLINE = """
<html><head><title>Inline Formatting Test</title></head>
<body>
<article>
<h1>Transformers</h1>
<p>Attention weighs tokens by <b>relevance</b> across the whole input sequence.</p>
<h2>Training</h2>
<p>The model is trained on <b>large</b> corpora using self-supervised objectives.</p>
</article>
</body></html>
"""


def test_webpage_extracts_main_content_into_sectioned_blocks() -> None:
    doc = webpage_to_normdoc(HTML, fallback_title="fallback", url="https://x.example/a")
    assert doc.media_type == "article"
    # nav/footer junk is stripped by trafilatura
    assert "home about" not in doc.content_body
    assert "copyright" not in doc.content_body
    texts = [b.text for b in doc.blocks]
    assert any("weigh tokens by relevance" in t for t in texts)
    assert any("attends to every other token" in t for t in texts)
    # headings are not blocks; they label the following paragraphs
    assert all(not b.text.lstrip().startswith("#") for b in doc.blocks)
    # the section label is carried onto the self-attention paragraph
    sa = next(b for b in doc.blocks if "attends to every other token" in b.text)
    assert sa.section_label is not None and "Self-Attention" in sa.section_label
    # anchor invariant holds against content_body
    for b in doc.blocks:
        assert doc.content_body[b.anchor.start : b.anchor.end] == b.text


def test_inline_formatting_not_truncated() -> None:
    """Inline markup (bold/italic) must not cause text after the tag to be dropped."""
    doc = webpage_to_normdoc(HTML_INLINE, fallback_title="fallback", url="https://x.example/b")
    # Full sentence must be present — not truncated at the <b> element.
    # trafilatura markdown output wraps bold in **, so the text after the tag
    # appears as "**relevance** across the whole input sequence".
    assert any(
        "across the whole input sequence" in b.text for b in doc.blocks
    ), "Text after inline element was truncated"
    # The bold word itself must also be present (not dropped)
    assert any("relevance" in b.text for b in doc.blocks), "Inline bold word was dropped"
    # anchor invariant holds
    for b in doc.blocks:
        assert doc.content_body[b.anchor.start : b.anchor.end] == b.text


def test_duplicate_paragraphs_are_removed() -> None:
    """trafilatura 2.1.0 appends exact copies of paragraphs; dedup must remove them."""
    doc = webpage_to_normdoc(HTML_INLINE, fallback_title="fallback", url="https://x.example/c")
    # HTML_INLINE has 2 real paragraphs; deduplicated output must not have doubles
    assert len(doc.blocks) == 2, (
        f"Expected 2 content blocks after dedup, got {len(doc.blocks)}: "
        + str([b.text for b in doc.blocks])
    )
    # anchor invariant holds
    for b in doc.blocks:
        assert doc.content_body[b.anchor.start : b.anchor.end] == b.text
