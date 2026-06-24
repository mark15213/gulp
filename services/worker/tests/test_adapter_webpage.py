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
