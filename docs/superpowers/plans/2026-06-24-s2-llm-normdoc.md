# S2 LLM Service Layer + NormDoc Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the two type-agnostic halves the S2 pipeline needs — the **extraction → `NormDoc`** layer (webpage + note adapters) and the **provider-agnostic LLM service layer** (Anthropic adapter) — so Plan 3's `process_snapshot` can fetch/parse into a `NormDoc` and call one `complete_structured(...)` to produce pack/cards.

**Architecture:** Everything lives in `services/worker/app/`. `pipeline/normdoc.py` defines pydantic DTOs (`Anchor`/`NormBlock`/`NormDoc`) that all input adapters normalize into — the unification seam (`S2 design §2.1–2.2`). `pipeline/adapters/` holds per-input-type adapters (note, webpage). `llm/` exposes one `complete_structured(response_model=..., ...)` that picks a provider by config, calls it, and validates the result into a pydantic model — with an injectable `AnthropicProvider` using tool-use structured output (`S2 design §2.6`). Tests are hermetic: adapters parse fixtures (no network), the LLM layer uses a `FakeProvider` and a mocked SDK client (no API key, no calls).

**Tech Stack:** Python 3.13, pydantic 2, `trafilatura` (new dep) for main-content extraction, `httpx` (existing) for fetch, `anthropic` 0.111 SDK (existing), pytest + pytest-asyncio (`asyncio_mode=auto`).

## Global Constraints

- **All new code lives in `services/worker/app/`** — `pipeline/` (extraction) and `llm/` (model clients), per `services/worker/CLAUDE.md`. Persistence stays in `gulp_shared` (this plan adds NO ORM models — it produces in-memory DTOs only).
- **Enum/style conventions** match the repo: `class E(str, enum.Enum)` where enums are needed (UP042 is accepted pre-existing debt — do not switch to `StrEnum`); type everything (mypy is `strict`).
- **`NormDoc` invariant:** for every block, `normdoc.content_body[block.anchor.start:block.anchor.end] == block.text`. Anchors are char offsets into `content_body`. Tests must assert this.
- **Hermetic tests:** no test makes a network call or needs `ANTHROPIC_API_KEY`. The webpage adapter separates `fetch` (async httpx, not unit-tested) from pure parse (tested on fixture HTML/markdown). The Anthropic adapter takes an **injectable client** so tests pass a fake.
- **Structured output is pydantic-model-driven:** `complete_structured(response_model=SomeModel, ...)` uses `SomeModel.model_json_schema()` as the tool `input_schema` and validates the provider's returned dict via `SomeModel.model_validate(...)`. One schema source for the tool, the validation, and (later) the export job-spec.
- **Async:** the LLM provider interface is `async`; the worker runs under arq (async). pytest `asyncio_mode=auto` means `async def test_...` runs directly.
- **Quality gates:** `cd services/worker && uv run pytest` green; `uv run mypy services/worker` clean. (Repo-wide `ruff check .` and `just lint` carry accepted pre-existing debt — confirm your NEW files add no new ruff errors beyond UP042-style accepted items.)
- **TDD + a commit per task.**

---

## File Structure

- `services/worker/app/pipeline/normdoc.py` *(new)* — `Anchor`, `NormBlock`, `NormDoc` pydantic models + the slice invariant helper. The unified intermediate representation.
- `services/worker/app/pipeline/adapters/__init__.py` *(new)* — package marker (and a thin convenience re-export).
- `services/worker/app/pipeline/adapters/note.py` *(new)* — `note_to_normdoc(title, body) -> NormDoc`.
- `services/worker/app/pipeline/adapters/webpage.py` *(new)* — `fetch_html(url)` (async httpx), `extract_markdown(html)` (trafilatura), `webpage_to_normdoc(html, *, fallback_title, url) -> NormDoc` (pure splitter).
- `services/worker/app/llm/base.py` *(new)* — `ModelConfig`, `Message`, `LLMProvider` protocol, `LLMError`.
- `services/worker/app/llm/service.py` *(new)* — provider registry + `complete_structured(...)` (validate + retry).
- `services/worker/app/llm/anthropic_provider.py` *(new)* — `AnthropicProvider` (tool-use structured output, injectable client).
- `services/worker/app/llm/__init__.py` *(modify)* — register `AnthropicProvider`, export the public surface.
- `services/shared/gulp_shared/settings.py` *(modify)* — add `llm_provider` + `llm_model` defaults.
- `services/worker/pyproject.toml` *(modify)* — add `pydantic`, `trafilatura`.
- Tests *(new)*: `services/worker/tests/test_normdoc.py`, `test_adapter_note.py`, `test_adapter_webpage.py`, `test_llm_service.py`, `test_anthropic_provider.py`, `test_llm_wiring.py`.

Task order (dependency-driven): NormDoc → note adapter → webpage adapter → LLM base+service → Anthropic provider → settings+wiring.

---

### Task 1: `NormDoc` DTOs

**Files:**
- Create: `services/worker/app/pipeline/normdoc.py`
- Modify: `services/worker/pyproject.toml` (add `pydantic`)
- Test: `services/worker/tests/test_normdoc.py`

**Interfaces:**
- Produces: `Anchor(kind: str = "char_range", start: int, end: int)`; `NormBlock(text: str, section_label: str | None = None, anchor: Anchor)`; `NormDoc(title: str, lang: str | None = None, media_type: str, content_body: str, blocks: list[NormBlock])`. All `pydantic.BaseModel`. Invariant: `content_body[b.anchor.start:b.anchor.end] == b.text` for every block.

- [ ] **Step 1: Add the dependency**

In `services/worker/pyproject.toml`, add `"pydantic>=2"` to `dependencies` (the worker now imports pydantic directly). Then:

Run: `uv sync`
Expected: resolves with pydantic already present (no version churn).

- [ ] **Step 2: Write the failing test**

Create `services/worker/tests/test_normdoc.py`:

```python
from app.pipeline.normdoc import Anchor, NormBlock, NormDoc


def test_normdoc_round_trips_and_anchors_slice_content_body():
    body = "First paragraph.\n\nSecond paragraph."
    blocks = [
        NormBlock(text="First paragraph.", section_label="Intro", anchor=Anchor(start=0, end=16)),
        NormBlock(text="Second paragraph.", anchor=Anchor(start=18, end=35)),
    ]
    doc = NormDoc(title="T", lang="en", media_type="note", content_body=body, blocks=blocks)

    # anchors slice content_body exactly
    for b in doc.blocks:
        assert doc.content_body[b.anchor.start : b.anchor.end] == b.text

    # JSON round-trip (forward-compat for the export job spec)
    again = NormDoc.model_validate_json(doc.model_dump_json())
    assert again == doc
    assert again.blocks[0].anchor.kind == "char_range"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_normdoc.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.normdoc'`

- [ ] **Step 4: Write the model**

Create `services/worker/app/pipeline/normdoc.py`:

```python
"""NormDoc — the unified intermediate representation every input adapter
produces (S2 design §2.1-2.2). All downstream LLM work sees only this.

Anchors are char offsets into `content_body`: for every block,
`content_body[anchor.start:anchor.end] == block.text`.
"""

from pydantic import BaseModel


class Anchor(BaseModel):
    kind: str = "char_range"
    start: int
    end: int


class NormBlock(BaseModel):
    text: str
    section_label: str | None = None
    anchor: Anchor


class NormDoc(BaseModel):
    title: str
    lang: str | None = None
    media_type: str
    content_body: str
    blocks: list[NormBlock]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_normdoc.py -v`
Expected: PASS

- [ ] **Step 6: mypy + commit**

```bash
cd services/worker && uv run mypy . && cd ../..
git add services/worker/app/pipeline/normdoc.py services/worker/tests/test_normdoc.py services/worker/pyproject.toml
git commit -m "feat(s2): NormDoc unified intermediate representation"
```

---

### Task 2: note adapter

**Files:**
- Create: `services/worker/app/pipeline/adapters/__init__.py`, `services/worker/app/pipeline/adapters/note.py`
- Test: `services/worker/tests/test_adapter_note.py`

**Interfaces:**
- Consumes: `app.pipeline.normdoc.{NormDoc, NormBlock, Anchor}`.
- Produces: `note_to_normdoc(title: str, body: str) -> NormDoc` — one block spanning the whole body, `media_type="note"`, `lang=None`, `content_body=body`.

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_adapter_note.py`:

```python
from app.pipeline.adapters.note import note_to_normdoc


def test_note_becomes_single_block_normdoc():
    doc = note_to_normdoc("My note", "Remember this idea.")
    assert doc.media_type == "note"
    assert doc.title == "My note"
    assert doc.content_body == "Remember this idea."
    assert len(doc.blocks) == 1
    b = doc.blocks[0]
    assert b.text == "Remember this idea."
    assert doc.content_body[b.anchor.start : b.anchor.end] == b.text
    assert b.section_label is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_adapter_note.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.adapters'`

- [ ] **Step 3: Write the adapter**

Create `services/worker/app/pipeline/adapters/__init__.py`:

```python
"""Per-input-type adapters → NormDoc (S2 design §2.2). Add a new input type
by adding an adapter here; the digest/card stages never change."""
```

Create `services/worker/app/pipeline/adapters/note.py`:

```python
"""Note adapter — the trivial case: the body is its own single block."""

from app.pipeline.normdoc import Anchor, NormBlock, NormDoc


def note_to_normdoc(title: str, body: str) -> NormDoc:
    block = NormBlock(text=body, anchor=Anchor(start=0, end=len(body)))
    return NormDoc(
        title=title,
        lang=None,
        media_type="note",
        content_body=body,
        blocks=[block],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_adapter_note.py -v`
Expected: PASS

- [ ] **Step 5: mypy + commit**

```bash
cd services/worker && uv run mypy . && cd ../..
git add services/worker/app/pipeline/adapters/ services/worker/tests/test_adapter_note.py
git commit -m "feat(s2): note → NormDoc adapter"
```

---

### Task 3: webpage adapter

**Files:**
- Create: `services/worker/app/pipeline/adapters/webpage.py`
- Modify: `services/worker/pyproject.toml` (add `trafilatura`)
- Test: `services/worker/tests/test_adapter_webpage.py`

**Interfaces:**
- Consumes: `normdoc.*`, `httpx`, `trafilatura`.
- Produces:
  - `async def fetch_html(url: str) -> str` — httpx GET, `raise_for_status`, return text. (Not unit-tested — network.)
  - `extract_markdown(html: str) -> tuple[str, str | None]` — returns `(markdown, title)` via trafilatura.
  - `webpage_to_normdoc(html: str, *, fallback_title: str, url: str) -> NormDoc` — extract markdown, then split into blocks: markdown headings (`#`/`##`/…) set the current `section_label` and are not themselves blocks; each non-empty non-heading paragraph (separated by blank lines) becomes a `NormBlock` whose anchor is its char span in the markdown (`content_body == markdown`). `media_type="article"`.

- [ ] **Step 1: Add the dependency**

In `services/worker/pyproject.toml`, add `"trafilatura>=1.12"` to `dependencies`. Then:

Run: `uv sync`
Expected: trafilatura (+ lxml etc.) installed.

- [ ] **Step 2: Write the failing test**

Create `services/worker/tests/test_adapter_webpage.py`:

```python
from app.pipeline.adapters.webpage import webpage_to_normdoc

# A minimal article. trafilatura extracts the <article> main content.
HTML = """
<html><head><title>Attention Explained</title></head>
<body>
<nav>home about</nav>
<article>
<h1>Attention</h1>
<p>Attention lets a model weigh tokens by relevance.</p>
<h2>Self-Attention</h2>
<p>Each token attends to every other token in the sequence.</p>
</article>
<footer>copyright</footer>
</body></html>
"""


def test_webpage_extracts_main_content_into_sectioned_blocks():
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_adapter_webpage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.adapters.webpage'`

- [ ] **Step 4: Write the adapter**

Create `services/worker/app/pipeline/adapters/webpage.py`:

```python
"""Webpage/article adapter — fetch, extract main content (trafilatura), and
split the extracted markdown into sectioned NormDoc blocks.

`content_body` IS the extracted markdown, so block anchors slice it exactly.
Headings set the running section label and are not emitted as blocks.
"""

import re

import httpx
import trafilatura

from app.pipeline.normdoc import Anchor, NormBlock, NormDoc

_HEADING = re.compile(r"^#{1,6}\s+(.*\S)\s*$")


async def fetch_html(url: str) -> str:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url, headers={"User-Agent": "GulpBot/1.0"})
        resp.raise_for_status()
        return resp.text


def extract_markdown(html: str) -> tuple[str, str | None]:
    md = trafilatura.extract(html, output_format="markdown", with_metadata=False) or ""
    meta = trafilatura.extract_metadata(html)
    title = meta.title if meta is not None else None
    return md, title


def _split(markdown: str) -> list[NormBlock]:
    blocks: list[NormBlock] = []
    section: str | None = None
    pos = 0
    # iterate paragraphs separated by blank lines, tracking char offsets
    for para in re.split(r"\n\s*\n", markdown):
        start = markdown.find(para, pos)
        if start < 0:
            continue
        end = start + len(para)
        pos = end
        stripped = para.strip()
        if not stripped:
            continue
        m = _HEADING.match(stripped)
        if m:
            section = m.group(1)
            continue
        blocks.append(
            NormBlock(text=para, section_label=section, anchor=Anchor(start=start, end=end))
        )
    return blocks


def webpage_to_normdoc(html: str, *, fallback_title: str, url: str) -> NormDoc:
    markdown, title = extract_markdown(html)
    return NormDoc(
        title=title or fallback_title,
        lang=None,
        media_type="article",
        content_body=markdown,
        blocks=_split(markdown),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_adapter_webpage.py -v`
Expected: PASS. (If trafilatura's markdown emits a heading inline with text rather than on its own paragraph, adjust the fixture or the split to still satisfy the assertions — the contract is: junk stripped, paragraphs are blocks, headings label sections, anchors slice `content_body`.)

- [ ] **Step 6: mypy + commit**

```bash
cd services/worker && uv run mypy . && cd ../..
git add services/worker/app/pipeline/adapters/webpage.py services/worker/tests/test_adapter_webpage.py services/worker/pyproject.toml
git commit -m "feat(s2): webpage → NormDoc adapter (trafilatura)"
```

---

### Task 4: LLM base types + service

**Files:**
- Create: `services/worker/app/llm/base.py`, `services/worker/app/llm/service.py`
- Test: `services/worker/tests/test_llm_service.py`

**Interfaces:**
- Produces in `base.py`: `Message = dict[str, str]`; `ModelConfig(BaseModel)` with `provider: str = "anthropic"`, `model: str = "claude-sonnet-4-6"`, `max_tokens: int = 4096`, `temperature: float = 0.2`; `class LLMError(Exception)`; `LLMProvider` Protocol with `async def complete_json(self, *, system: str | None, messages: list[Message], json_schema: dict[str, Any], config: ModelConfig) -> dict[str, Any]`.
- Produces in `service.py`: `register_provider(name: str, provider: LLMProvider) -> None`; `get_provider(name: str) -> LLMProvider`; `async def complete_structured(*, response_model: type[T], messages: list[Message], system: str | None = None, config: ModelConfig | None = None, provider: LLMProvider | None = None, max_attempts: int = 2) -> T` where `T = TypeVar("T", bound=BaseModel)`. It resolves the provider (arg → `get_provider(config.provider)`), calls `complete_json` with `response_model.model_json_schema()`, and validates via `response_model.model_validate(...)`, retrying on `pydantic.ValidationError` up to `max_attempts`, raising `LLMError` if all attempts fail.

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_llm_service.py`:

```python
from typing import Any

import pytest
from pydantic import BaseModel

from app.llm.base import LLMError, Message, ModelConfig
from app.llm.service import complete_structured, get_provider, register_provider


class Person(BaseModel):
    name: str
    age: int


class FakeProvider:
    """Returns queued dicts in order; lets us simulate invalid-then-valid."""

    def __init__(self, *responses: dict[str, Any]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[Message],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]:
        self.calls += 1
        return self._responses.pop(0)


async def test_complete_structured_validates_into_model():
    fake = FakeProvider({"name": "Ada", "age": 36})
    out = await complete_structured(
        response_model=Person,
        messages=[{"role": "user", "content": "who?"}],
        config=ModelConfig(),
        provider=fake,
    )
    assert isinstance(out, Person) and out.name == "Ada" and out.age == 36
    assert fake.calls == 1


async def test_complete_structured_retries_then_succeeds():
    fake = FakeProvider({"name": "Ada"}, {"name": "Ada", "age": 36})  # 1st missing age
    out = await complete_structured(
        response_model=Person,
        messages=[{"role": "user", "content": "who?"}],
        config=ModelConfig(),
        provider=fake,
        max_attempts=2,
    )
    assert out.age == 36
    assert fake.calls == 2


async def test_complete_structured_raises_after_max_attempts():
    fake = FakeProvider({"name": "x"}, {"name": "y"})  # both invalid
    with pytest.raises(LLMError):
        await complete_structured(
            response_model=Person,
            messages=[{"role": "user", "content": "who?"}],
            config=ModelConfig(),
            provider=fake,
            max_attempts=2,
        )


def test_registry_round_trips():
    fake = FakeProvider({"name": "z", "age": 1})
    register_provider("fake", fake)
    assert get_provider("fake") is fake


def test_get_provider_unknown_raises():
    with pytest.raises(LLMError):
        get_provider("nope-not-registered")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_llm_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.llm.base'`

- [ ] **Step 3: Write base.py**

Create `services/worker/app/llm/base.py`:

```python
"""Provider-agnostic LLM contract (S2 design §2.6)."""

from typing import Any, Protocol

from pydantic import BaseModel

Message = dict[str, str]


class LLMError(Exception):
    """Raised on provider failure or when output can't be validated."""


class ModelConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    temperature: float = 0.2


class LLMProvider(Protocol):
    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[Message],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]: ...
```

- [ ] **Step 4: Write service.py**

Create `services/worker/app/llm/service.py`:

```python
"""Provider registry + the validated `complete_structured` entry point."""

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.llm.base import LLMError, LLMProvider, Message, ModelConfig

T = TypeVar("T", bound=BaseModel)

_PROVIDERS: dict[str, LLMProvider] = {}


def register_provider(name: str, provider: LLMProvider) -> None:
    _PROVIDERS[name] = provider


def get_provider(name: str) -> LLMProvider:
    try:
        return _PROVIDERS[name]
    except KeyError as exc:
        raise LLMError(f"no LLM provider registered as {name!r}") from exc


async def complete_structured(
    *,
    response_model: type[T],
    messages: list[Message],
    system: str | None = None,
    config: ModelConfig | None = None,
    provider: LLMProvider | None = None,
    max_attempts: int = 2,
) -> T:
    cfg = config or ModelConfig()
    prov = provider or get_provider(cfg.provider)
    schema = response_model.model_json_schema()
    last: Exception | None = None
    for _ in range(max_attempts):
        raw = await prov.complete_json(
            system=system, messages=messages, json_schema=schema, config=cfg
        )
        try:
            return response_model.model_validate(raw)
        except ValidationError as exc:
            last = exc
    raise LLMError(
        f"{response_model.__name__} validation failed after {max_attempts} attempts"
    ) from last
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_llm_service.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: mypy + commit**

```bash
cd services/worker && uv run mypy . && cd ../..
git add services/worker/app/llm/base.py services/worker/app/llm/service.py services/worker/tests/test_llm_service.py
git commit -m "feat(s2): provider-agnostic LLM service (validate + retry)"
```

---

### Task 5: Anthropic provider (tool-use structured output)

**Files:**
- Create: `services/worker/app/llm/anthropic_provider.py`
- Test: `services/worker/tests/test_anthropic_provider.py`

**Interfaces:**
- Consumes: `anthropic` SDK (`AsyncAnthropic`, `anthropic.types.ToolUseBlock`), `app.llm.base.*`, `gulp_shared.settings.settings`.
- Produces: `class AnthropicProvider` implementing `LLMProvider`. Constructor takes an optional injected client (`AnthropicProvider(client=...)`); when omitted it lazily builds `AsyncAnthropic(api_key=settings.anthropic_api_key)` on first call (so import/registration needs no key). `complete_json` builds a single tool `{"name": "emit", "description": ..., "input_schema": json_schema}`, calls `messages.create(..., tools=[tool], tool_choice={"type": "tool", "name": "emit"})`, finds the `ToolUseBlock`, and returns its `.input` as a dict. Raises `LLMError` if no tool_use block is present.

- [ ] **Step 1: Write the failing test (mocked SDK — no network, no key)**

Create `services/worker/tests/test_anthropic_provider.py`:

```python
from typing import Any

import pytest

from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMError, ModelConfig


class _ToolUseBlock:
    type = "tool_use"

    def __init__(self, data: dict[str, Any]) -> None:
        self.input = data


class _TextBlock:
    type = "text"
    text = "ignored"


class _Resp:
    def __init__(self, content: list[Any]) -> None:
        self.content = content


class _Messages:
    def __init__(self, resp: _Resp) -> None:
        self._resp = resp
        self.last_kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> _Resp:
        self.last_kwargs = kwargs
        return self._resp


class _FakeClient:
    def __init__(self, resp: _Resp) -> None:
        self.messages = _Messages(resp)


async def test_returns_tool_use_input_and_forces_the_tool():
    resp = _Resp([_TextBlock(), _ToolUseBlock({"name": "Ada", "age": 36})])
    client = _FakeClient(resp)
    prov = AnthropicProvider(client=client)

    out = await prov.complete_json(
        system="be precise",
        messages=[{"role": "user", "content": "who?"}],
        json_schema={"type": "object", "properties": {"name": {"type": "string"}}},
        config=ModelConfig(model="claude-sonnet-4-6"),
    )
    assert out == {"name": "Ada", "age": 36}
    kw = client.messages.last_kwargs
    assert kw is not None
    assert kw["model"] == "claude-sonnet-4-6"
    assert kw["tool_choice"] == {"type": "tool", "name": "emit"}
    assert kw["tools"][0]["input_schema"]["type"] == "object"
    assert kw["system"] == "be precise"


async def test_raises_when_no_tool_use_block():
    client = _FakeClient(_Resp([_TextBlock()]))
    prov = AnthropicProvider(client=client)
    with pytest.raises(LLMError):
        await prov.complete_json(
            system=None,
            messages=[{"role": "user", "content": "hi"}],
            json_schema={"type": "object"},
            config=ModelConfig(),
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_anthropic_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.llm.anthropic_provider'`

- [ ] **Step 3: Write the provider**

Create `services/worker/app/llm/anthropic_provider.py`:

```python
"""Anthropic adapter — structured output via forced tool use (S2 design §2.6).

The client is injectable so tests pass a fake; in production it is built lazily
from settings so importing/registering this module needs no API key.
"""

from typing import Any, cast

from anthropic import AsyncAnthropic

from app.llm.base import LLMError, Message, ModelConfig
from gulp_shared.settings import settings

_TOOL_NAME = "emit"


class AnthropicProvider:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[Message],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]:
        tool = {
            "name": _TOOL_NAME,
            "description": "Return the structured result for this task.",
            "input_schema": json_schema,
        }
        kwargs: dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "messages": messages,
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": _TOOL_NAME},
        }
        if system is not None:
            kwargs["system"] = system
        resp = await self._get_client().messages.create(**kwargs)
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                return cast(dict[str, Any], block.input)
        raise LLMError("Anthropic response contained no tool_use block")
```

> Note: the client is typed `Any` deliberately so the fake test double and the real `AsyncAnthropic` both satisfy it without fighting the SDK's overloaded `messages.create` signature under mypy strict. The structured-output mechanism (forced tool use, read `tool_use` block `.input`) is the contract verified by the test.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_anthropic_provider.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: mypy + commit**

```bash
cd services/worker && uv run mypy . && cd ../..
git add services/worker/app/llm/anthropic_provider.py services/worker/tests/test_anthropic_provider.py
git commit -m "feat(s2): Anthropic provider (forced tool-use structured output)"
```

---

### Task 6: settings + wiring

**Files:**
- Modify: `services/shared/gulp_shared/settings.py`, `services/worker/app/llm/__init__.py`
- Test: `services/worker/tests/test_llm_wiring.py`

**Interfaces:**
- `settings` gains `llm_provider: str = "anthropic"` and `llm_model: str = "claude-sonnet-4-6"`.
- `app.llm` (package) registers `AnthropicProvider()` under `"anthropic"` at import and re-exports `complete_structured`, `ModelConfig`, `Message`, `LLMError`, `LLMProvider`, `register_provider`, `get_provider`, `AnthropicProvider`.

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_llm_wiring.py`:

```python
import app.llm as llm
from app.llm import AnthropicProvider, get_provider
from gulp_shared.settings import settings


def test_anthropic_is_registered_by_default():
    assert isinstance(get_provider("anthropic"), AnthropicProvider)


def test_public_surface_is_exported():
    for name in ("complete_structured", "ModelConfig", "LLMError", "get_provider"):
        assert hasattr(llm, name)


def test_settings_have_llm_defaults():
    assert settings.llm_provider == "anthropic"
    assert settings.llm_model == "claude-sonnet-4-6"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_llm_wiring.py -v`
Expected: FAIL — `AttributeError` on `settings.llm_provider` / missing exports.

- [ ] **Step 3: Add settings**

In `services/shared/gulp_shared/settings.py`, add to `Settings` (after `anthropic_api_key`):

```python
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-6"
```

- [ ] **Step 4: Wire the llm package**

Replace `services/worker/app/llm/__init__.py` with:

```python
"""Model/provider clients for the pipeline. Registers the default provider."""

from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMError, LLMProvider, Message, ModelConfig
from app.llm.service import (
    complete_structured,
    get_provider,
    register_provider,
)

register_provider("anthropic", AnthropicProvider())

__all__ = [
    "AnthropicProvider",
    "LLMError",
    "LLMProvider",
    "Message",
    "ModelConfig",
    "complete_structured",
    "get_provider",
    "register_provider",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_llm_wiring.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Full worker suite + mypy + commit**

```bash
cd services/worker && uv run pytest -q && uv run mypy . && cd ../..
git add services/shared/gulp_shared/settings.py services/worker/app/llm/__init__.py services/worker/tests/test_llm_wiring.py
git commit -m "feat(s2): LLM settings defaults + register default provider"
```

---

## Self-Review

**Spec coverage** (against `S2 design §2.2` NormDoc, `§2.3` adapters, `§2.6` LLM layer):
- `NormDoc` unified IR with char-range anchors → Task 1 ✓.
- note + webpage adapters (the v1 input scope, `C17`) → Tasks 2–3 ✓; webpage uses trafilatura main-content extraction, deterministic splitter.
- Provider-agnostic LLM interface, config-driven, structured output normalized, validation + bounded retry → Tasks 4–6 ✓; pydantic-model-as-schema (one source for tool input_schema + validation + future export).
- Hermetic tests (FakeProvider + injected SDK client, fixture HTML) → all tasks ✓.
- **Deferred (correctly out of this plan):** the `process_snapshot` orchestration that fetches + adapts + calls the digest/card prompts (Plan 3); the export/custom executors; PDF/video/etc. adapters; the actual digest/card pydantic response models + prompts (Plan 3, evaluated against the §4 seed set).

**Placeholder scan:** none — every step has concrete code/commands. The one judgment note (Task 3 Step 5) is a real fallback instruction, not a placeholder.

**Type consistency:** `complete_structured`, `complete_json`, `ModelConfig`, `LLMProvider`, `register_provider`/`get_provider`, `NormDoc`/`NormBlock`/`Anchor`, `note_to_normdoc`, `webpage_to_normdoc`/`extract_markdown`/`fetch_html` are named identically across `base.py`, `service.py`, `anthropic_provider.py`, `__init__.py`, the adapters, and their tests. The provider Protocol's `complete_json` signature matches the `FakeProvider` test double and `AnthropicProvider` exactly (`system`, `messages`, `json_schema`, `config`).
