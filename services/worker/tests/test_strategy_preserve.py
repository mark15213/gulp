"""Preserve strategy: deterministic markdown -> PackDraft, zero LLM, verbatim prose."""

from app.pipeline.normdoc import Anchor, NormBlock, NormDoc
from app.pipeline.strategies.preserve import build_preserve_draft


def _doc(body: str, *, title: str = "T", description: str | None = None) -> NormDoc:
    return NormDoc(
        title=title,
        media_type="article",
        description=description,
        content_body=body,
        blocks=[NormBlock(text=body, anchor=Anchor(start=0, end=len(body)))],
    )


_MD = """Intro paragraph before any heading with **bold** text.

## Setup

Some prose with inline math $x^2$.

```python
# not a heading
def f():
    return 1
```

### Data

| Model | F1 |
|---|---|
| BERT | 93.2 |

![Architecture diagram](https://x.test/fig1.png)

$$
L = -\\sum_i y_i \\log p_i
$$

- alpha
- beta

1. first
2. second

## Closing

Final thoughts.
"""


def test_golden_markdown_transform() -> None:
    draft = build_preserve_draft(_doc(_MD))

    assert draft.pack_type == "article"
    assert draft.title == "T"
    assert draft.extras == {}

    headings = [s.heading for s in draft.sections]
    assert headings == [None, "Setup", "Data", "Closing"]

    intro = draft.sections[0].blocks
    assert [b.type for b in intro] == ["prose"]
    assert intro[0].content == "Intro paragraph before any heading with **bold** text."

    setup = draft.sections[1].blocks
    assert [b.type for b in setup] == ["prose", "code"]
    assert setup[0].content == "Some prose with inline math $x^2$."
    assert setup[1].language == "python"
    assert setup[1].content == "# not a heading\ndef f():\n    return 1"

    data = draft.sections[2].blocks
    assert [b.type for b in data] == ["table", "figure", "formula", "list", "list"]
    assert data[0].headers == ["Model", "F1"]
    assert data[0].rows == [["BERT", "93.2"]]
    assert data[1].label == "Architecture diagram"
    assert data[1].url == "https://x.test/fig1.png"
    assert data[1].figure_id is None
    assert data[2].latex == "L = -\\sum_i y_i \\log p_i"
    assert data[3].items == ["alpha", "beta"] and data[3].ordered is False
    assert data[4].items == ["first", "second"] and data[4].ordered is True

    closing = draft.sections[3].blocks
    assert [b.type for b in closing] == ["prose"]
    assert closing[0].content == "Final thoughts."


def test_summary_prefers_meta_description() -> None:
    draft = build_preserve_draft(_doc(_MD, description="A primer."))
    assert draft.summary == "A primer."


def test_summary_falls_back_to_first_prose_paragraph() -> None:
    draft = build_preserve_draft(_doc(_MD))
    assert draft.summary == "Intro paragraph before any heading with **bold** text."


def test_summary_excerpt_is_truncated() -> None:
    long_par = "word " * 100  # ~500 chars
    draft = build_preserve_draft(_doc(long_par.strip()))
    assert draft.summary is not None
    assert len(draft.summary) <= 281  # 280 + ellipsis
    assert draft.summary.endswith("…")


def test_empty_body_still_yields_one_section() -> None:
    draft = build_preserve_draft(_doc("   \n\n  "))
    assert len(draft.sections) == 1
    assert draft.sections[0].heading is None


def test_heading_only_section_is_kept() -> None:
    draft = build_preserve_draft(_doc("## Alpha\n\n## Beta\n\ntext"))
    assert [s.heading for s in draft.sections] == ["Alpha", "Beta"]
    assert draft.sections[0].blocks == []
    assert draft.sections[1].blocks[0].content == "text"


def test_unclosed_fence_consumes_rest_as_code() -> None:
    draft = build_preserve_draft(_doc("prose\n\n```\ncode line\nmore code"))
    blocks = draft.sections[0].blocks
    assert [b.type for b in blocks] == ["prose", "code"]
    assert blocks[1].content == "code line\nmore code"
