# MaaS Layer + BYOK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `gulp_shared/llm` into a unified multi-provider model-access layer (Claude/OpenAI/DeepSeek/Qwen) with per-user BYOK keys, streaming reader chat, a tool-use loop, and multimodal-capable contracts.

**Architecture:** Two wire adapters (Anthropic + OpenAI-compatible) behind the existing provider-agnostic contract; a static provider catalog replaces the mutable registry; keys resolve per call from encrypted per-user credentials (`resolve_model_config`) with the env key as dev fallback. Reader chat becomes SSE streaming with inline `[[block:ID]]` citation markers parsed server-side.

**Tech Stack:** Python 3.13 (FastAPI, SQLAlchemy 2, Alembic, arq, pydantic), `anthropic` + `openai` SDKs, `cryptography` (Fernet), Next.js App Router + vitest, `openapi-fetch` client.

**Spec:** `docs/superpowers/specs/2026-07-13-maas-layer-design.md`

## Global Constraints

- All code, comments, commit messages in **English** (repo rule 6).
- Work on branch `feat/maas-byok` (create from `main` before Task 1).
- Use `just` recipes where they exist; Python via `uv`, TS via `pnpm`.
- Python tests run **per package**: `uv run pytest services/shared services/api` from repo root; worker via `cd services/worker && uv run --package gulp-worker pytest`.
- Web vitest uses the **classic JSX transform**: JSX-bearing files (components AND tests) need `import React`; JSX-free files must not import it.
- `just lint` must stay green after every task.
- `web`/`api-client` `tsc --noEmit` has 2 PRE-EXISTING dup-identifier errors in `schema.gen.ts` (cards/job HEAD+GET) — ignore those two only.
- End commit messages with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Routers stay thin; business logic in `services/api/app/services`; persistence in `services/shared`.
- TS clients consume generated `packages/api-client` — never hand-write duplicate types (streaming helper lives in api-client, typed by hand only because SSE is outside OpenAPI).

---

## Slice 1 — contract rework + both adapters (env key; no product behaviour change)

### Task 1: Contract types + typed errors (`base.py` rework)

**Files:**
- Modify: `services/shared/gulp_shared/llm/base.py` (full rewrite)
- Modify: `services/shared/gulp_shared/llm/service.py` (messages type only)
- Modify: `services/shared/gulp_shared/llm/anthropic_provider.py` (imports/serialization shim — fully reworked in Task 3)
- Modify: `services/shared/gulp_shared/llm/__init__.py`
- Modify: `services/worker/app/prompts/digest.py`, `services/worker/app/prompts/cards.py` (return `list[ChatMessage]`)
- Modify: `services/api/app/services/chat.py` (build `ChatMessage` history)
- Modify: `services/worker/tests/test_llm_service.py`, `services/api/tests/test_pack_chat.py` (fakes' message types)
- Create: `services/shared/tests/test_llm_contract.py`

**Interfaces (produced — later tasks import these exact names from `gulp_shared.llm.base`):**
- Errors: `LLMError`, `LLMNotConfiguredError`, `LLMAuthError`, `LLMRateLimitError`, `LLMCapabilityError` (all subclass `LLMError`)
- `TextPart(type="text", text: str)`, `ImagePart(type="image", media_type: str, data_b64: str)`, `ContentPart = TextPart | ImagePart`
- `ToolSpec(name, description, input_schema: dict)`, `ToolCall(id, name, arguments: dict)`
- `ChatMessage(role: Literal["system","user","assistant","tool"], content: str | list[ContentPart] = "", tool_calls: list[ToolCall] | None = None, tool_call_id: str | None = None)`
- Stream events: `TextDelta(text)`, `ToolCallEvent(tool_call)`, `UsageEvent(input_tokens, output_tokens)`, `DoneEvent(stop_reason: str = "stop")`; `StreamEvent` = union of the four
- `ModelConfig(provider="anthropic", model="claude-sonnet-4-6", api_key: SecretStr = SecretStr(""), base_url: str | None = None, max_tokens=4096, temperature=0.2)`
- `LLMProvider` Protocol: `async complete_json(*, system, messages: list[ChatMessage], json_schema, config) -> dict` and `def stream_chat(*, system, messages, tools: list[ToolSpec] | None, config) -> AsyncIterator[StreamEvent]`

- [ ] **Step 1: Write the failing test** — `services/shared/tests/test_llm_contract.py`:

```python
"""Contract-shape tests for the provider-neutral LLM types."""

from gulp_shared.llm.base import (
    ChatMessage,
    DoneEvent,
    ImagePart,
    LLMAuthError,
    LLMCapabilityError,
    LLMError,
    LLMNotConfiguredError,
    LLMRateLimitError,
    ModelConfig,
    TextDelta,
    TextPart,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
    UsageEvent,
)


def test_error_taxonomy_subclasses_llm_error() -> None:
    for exc in (LLMNotConfiguredError, LLMAuthError, LLMRateLimitError, LLMCapabilityError):
        assert issubclass(exc, LLMError)


def test_chat_message_accepts_string_and_parts() -> None:
    plain = ChatMessage(role="user", content="hi")
    assert plain.content == "hi" and plain.tool_calls is None
    multi = ChatMessage(
        role="user",
        content=[TextPart(text="what is this?"), ImagePart(media_type="image/png", data_b64="aGk=")],
    )
    assert isinstance(multi.content, list) and multi.content[1].type == "image"


def test_tool_turns_round_trip() -> None:
    call = ToolCall(id="c1", name="search", arguments={"q": "gulp"})
    assistant = ChatMessage(role="assistant", content="", tool_calls=[call])
    result = ChatMessage(role="tool", content="found it", tool_call_id="c1")
    assert assistant.tool_calls[0].name == "search"
    assert result.tool_call_id == "c1"
    spec = ToolSpec(name="search", description="d", input_schema={"type": "object"})
    assert spec.input_schema["type"] == "object"


def test_stream_events_and_config() -> None:
    events = [
        TextDelta(text="a"),
        ToolCallEvent(tool_call=ToolCall(id="1", name="t", arguments={})),
        UsageEvent(input_tokens=1, output_tokens=2),
        DoneEvent(stop_reason="tool_use"),
    ]
    assert [e.type for e in events] == ["text_delta", "tool_call", "usage", "done"]
    cfg = ModelConfig(api_key="sk-test")  # coerces to SecretStr
    assert cfg.api_key.get_secret_value() == "sk-test"
    assert "sk-test" not in repr(cfg)  # never leaks in logs
```

- [ ] **Step 2: Run it to verify it fails** — `uv run pytest services/shared/tests/test_llm_contract.py -v` → FAIL (ImportError: `ChatMessage`).

- [ ] **Step 3: Rewrite `services/shared/gulp_shared/llm/base.py`:**

```python
"""Provider-agnostic LLM contract (spec 2026-07-13 MaaS layer)."""

from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol

from pydantic import BaseModel, SecretStr


class LLMError(Exception):
    """Raised on provider failure or when output can't be validated."""


class LLMNotConfiguredError(LLMError):
    """The user has no usable LLM credentials (and no dev fallback exists)."""


class LLMAuthError(LLMError):
    """The provider rejected the API key. Never retried."""


class LLMRateLimitError(LLMError):
    """The provider throttled the call (429)."""


class LLMCapabilityError(LLMError):
    """The request needs a capability this provider lacks (e.g. vision)."""


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ImagePart(BaseModel):
    type: Literal["image"] = "image"
    media_type: str  # e.g. "image/png"
    data_b64: str


ContentPart = TextPart | ImagePart


class ToolSpec(BaseModel):
    """A tool declared to the model."""

    name: str
    description: str
    input_schema: dict[str, Any]


class ToolCall(BaseModel):
    """A call the model asked for."""

    id: str
    name: str
    arguments: dict[str, Any]


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[ContentPart] = ""
    tool_calls: list[ToolCall] | None = None  # assistant turns that invoked tools
    tool_call_id: str | None = None  # tool-result turns


class TextDelta(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    text: str


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool_call: ToolCall


class UsageEvent(BaseModel):
    type: Literal["usage"] = "usage"
    input_tokens: int
    output_tokens: int


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    stop_reason: str = "stop"  # "stop" | "tool_use" | "max_tokens" | provider-raw


StreamEvent = TextDelta | ToolCallEvent | UsageEvent | DoneEvent


class ModelConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key: SecretStr = SecretStr("")
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.2


class LLMProvider(Protocol):
    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]: ...

    def stream_chat(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None,
        config: ModelConfig,
    ) -> AsyncIterator[StreamEvent]: ...
```

The old `Message = dict[str, str]` alias is **deleted**. Ripple edits (all mechanical):

- `service.py`: change `messages: list[Message]` → `messages: list[ChatMessage]` in `complete_structured` (imports update; registry untouched until Task 2).
- `anthropic_provider.py`: replace `Message` import with `ChatMessage`; in `complete_json` serialize with `[{"role": m.role, "content": m.content} for m in messages]` (temporary — Task 3 replaces the file).
- `services/worker/app/prompts/digest.py` and `cards.py`: return `tuple[str, list[ChatMessage]]`, body `return _SYSTEM, [ChatMessage(role="user", content=user)]`; import `ChatMessage` from `gulp_shared.llm.base`.
- `services/api/app/services/chat.py`: `messages = [ChatMessage(role=m.role.value, content=m.content) for m in history]` (import `ChatMessage`).
- Test fakes in `services/worker/tests/test_llm_service.py` and `services/api/tests/test_pack_chat.py`: change `messages` param type hints to `list[ChatMessage]` and message literals to `ChatMessage(role="user", content=...)`; in `test_pack_chat.py` assertions that inspect `last_messages` use `.content` / `.role` attributes instead of dict keys.
- Grep for stragglers: `grep -rn '"role":' services --include='*.py' | grep -v __pycache__ | grep -v adapters` — remaining dict-literal messages must be converted (except inside provider serialization code).

- [ ] **Step 4: Run tests** — `uv run pytest services/shared services/api && (cd services/worker && uv run --package gulp-worker pytest)` → all PASS.
- [ ] **Step 5: Commit** — `refactor(llm): provider-neutral message/stream/tool contract + typed errors`

### Task 2: Provider catalog replaces the registry

**Files:**
- Create: `services/shared/gulp_shared/llm/catalog.py`
- Modify: `services/shared/gulp_shared/llm/service.py`
- Modify: `services/shared/gulp_shared/llm/__init__.py`
- Modify: `services/worker/tests/test_llm_service.py` (registry tests → catalog tests)
- Create: `services/shared/tests/test_llm_catalog.py`
- Modify: `services/shared/pyproject.toml` + `services/worker/pyproject.toml` (add `openai>=1.50` to shared; worker inherits via gulp-shared)

**Interfaces (produced):**
- `gulp_shared.llm.catalog`: `ModelInfo(id: str, label: str)`, `ProviderSpec(name, adapter: LLMProvider, base_url: str | None, capabilities: frozenset[str], models: tuple[ModelInfo, ...])`, `PROVIDERS: dict[str, ProviderSpec]`, `get_spec(name: str) -> ProviderSpec` (raises `LLMError`), `check_capabilities(spec, messages, tools) -> None` (raises `LLMCapabilityError`)
- `gulp_shared.llm.service.get_provider(name) -> LLMProvider` (thin wrapper over `get_spec(name).adapter`); `register_provider` **deleted**

**Consumes:** Task 1 types. Note: catalog imports `OpenAICompatProvider` which is created in Task 4 — in THIS task stub it as a class with the two protocol methods raising `NotImplementedError("Task 4")` in a new `services/shared/gulp_shared/llm/openai_compat.py`, so the catalog is complete and Task 4 only fills the file in.

- [ ] **Step 1: Write the failing test** — `services/shared/tests/test_llm_catalog.py`:

```python
"""Provider catalog: four providers, two adapters, capability gating."""

import pytest
from gulp_shared.llm.anthropic_provider import AnthropicProvider
from gulp_shared.llm.base import ChatMessage, ImagePart, LLMCapabilityError, LLMError, TextPart, ToolSpec
from gulp_shared.llm.catalog import PROVIDERS, check_capabilities, get_spec
from gulp_shared.llm.openai_compat import OpenAICompatProvider


def test_catalog_covers_four_providers_with_two_adapters() -> None:
    assert set(PROVIDERS) == {"anthropic", "openai", "deepseek", "qwen"}
    assert isinstance(get_spec("anthropic").adapter, AnthropicProvider)
    for name in ("openai", "deepseek", "qwen"):
        assert isinstance(get_spec(name).adapter, OpenAICompatProvider)
    assert get_spec("deepseek").base_url == "https://api.deepseek.com"
    for spec in PROVIDERS.values():
        assert spec.models, f"{spec.name} needs a curated model list"


def test_get_spec_unknown_raises() -> None:
    with pytest.raises(LLMError):
        get_spec("nope")


def test_capability_gate_blocks_images_for_deepseek() -> None:
    img_msg = [ChatMessage(role="user", content=[TextPart(text="?"), ImagePart(media_type="image/png", data_b64="aGk=")])]
    with pytest.raises(LLMCapabilityError):
        check_capabilities(get_spec("deepseek"), img_msg, None)
    check_capabilities(get_spec("qwen"), img_msg, None)  # vision-capable: no raise


def test_capability_gate_allows_tools_everywhere() -> None:
    tools = [ToolSpec(name="t", description="d", input_schema={"type": "object"})]
    for spec in PROVIDERS.values():
        check_capabilities(spec, [ChatMessage(role="user", content="hi")], tools)
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest services/shared/tests/test_llm_catalog.py -v` → FAIL (no module `catalog`).

- [ ] **Step 3: Implement.** Create `services/shared/gulp_shared/llm/openai_compat.py` stub:

```python
"""OpenAI-compatible adapter — one wire format covers OpenAI, DeepSeek, and
Qwen (DashScope compatible-mode). Filled in by the adapter task."""

from collections.abc import AsyncIterator
from typing import Any

from gulp_shared.llm.base import ChatMessage, ModelConfig, StreamEvent, ToolSpec


class OpenAICompatProvider:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def stream_chat(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None,
        config: ModelConfig,
    ) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError
        yield  # pragma: no cover — makes this an async generator
```

Create `services/shared/gulp_shared/llm/catalog.py`:

```python
"""Static provider catalog (spec 2026-07-13 §3.4): adapter, base_url,
capabilities, curated models. Capability checks run before any network call."""

from dataclasses import dataclass

from gulp_shared.llm.anthropic_provider import AnthropicProvider
from gulp_shared.llm.base import (
    ChatMessage,
    ImagePart,
    LLMCapabilityError,
    LLMError,
    LLMProvider,
    ToolSpec,
)
from gulp_shared.llm.openai_compat import OpenAICompatProvider


@dataclass(frozen=True)
class ModelInfo:
    id: str
    label: str


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    adapter: LLMProvider
    base_url: str | None
    capabilities: frozenset[str]  # subset of {"json", "stream", "tools", "vision"}
    models: tuple[ModelInfo, ...]


_ANTHROPIC = AnthropicProvider()
_OPENAI_COMPAT = OpenAICompatProvider()
_FULL = frozenset({"json", "stream", "tools", "vision"})

PROVIDERS: dict[str, ProviderSpec] = {
    "anthropic": ProviderSpec(
        name="anthropic",
        adapter=_ANTHROPIC,
        base_url=None,  # official SDK default
        capabilities=_FULL,
        models=(
            ModelInfo("claude-sonnet-4-6", "Claude Sonnet 4.6"),
            ModelInfo("claude-haiku-4-5", "Claude Haiku 4.5"),
        ),
    ),
    "openai": ProviderSpec(
        name="openai",
        adapter=_OPENAI_COMPAT,
        base_url="https://api.openai.com/v1",
        capabilities=_FULL,
        models=(ModelInfo("gpt-4.1", "GPT-4.1"), ModelInfo("gpt-4.1-mini", "GPT-4.1 mini")),
    ),
    "deepseek": ProviderSpec(
        name="deepseek",
        adapter=_OPENAI_COMPAT,
        base_url="https://api.deepseek.com",
        capabilities=frozenset({"json", "stream", "tools"}),  # no vision
        models=(
            ModelInfo("deepseek-chat", "DeepSeek Chat"),
            ModelInfo("deepseek-reasoner", "DeepSeek Reasoner"),
        ),
    ),
    "qwen": ProviderSpec(
        name="qwen",
        adapter=_OPENAI_COMPAT,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        capabilities=_FULL,  # vision via the VL models
        models=(
            ModelInfo("qwen-plus", "Qwen Plus"),
            ModelInfo("qwen-max", "Qwen Max"),
            ModelInfo("qwen-vl-plus", "Qwen VL Plus"),
        ),
    ),
}


def get_spec(name: str) -> ProviderSpec:
    try:
        return PROVIDERS[name]
    except KeyError as exc:
        raise LLMError(f"unknown LLM provider {name!r}") from exc


def check_capabilities(
    spec: ProviderSpec, messages: list[ChatMessage], tools: list[ToolSpec] | None
) -> None:
    if tools and "tools" not in spec.capabilities:
        raise LLMCapabilityError(f"{spec.name} does not support tool use")
    for m in messages:
        if isinstance(m.content, list) and any(isinstance(p, ImagePart) for p in m.content):
            if "vision" not in spec.capabilities:
                raise LLMCapabilityError(f"{spec.name} does not support image input")
```

Rework `service.py` (full file):

```python
"""Validated `complete_structured` entry point over the provider catalog."""

from pydantic import BaseModel, ValidationError

from gulp_shared.llm.base import ChatMessage, LLMError, LLMProvider, ModelConfig
from gulp_shared.llm.catalog import check_capabilities, get_spec


def get_provider(name: str) -> LLMProvider:
    return get_spec(name).adapter


async def complete_structured[T: BaseModel](
    *,
    response_model: type[T],
    messages: list[ChatMessage],
    system: str | None = None,
    config: ModelConfig | None = None,
    provider: LLMProvider | None = None,
    max_attempts: int = 2,
) -> T:
    cfg = config or ModelConfig()
    if provider is None:
        spec = get_spec(cfg.provider)
        check_capabilities(spec, messages, None)
        prov: LLMProvider = spec.adapter
    else:
        prov = provider
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

Update `__init__.py` exports (drop `register_provider`/`Message`, add catalog + new base names; keep `AnthropicProvider`, add `OpenAICompatProvider`). Delete `test_registry_round_trips`/`test_get_provider_unknown_raises` from `services/worker/tests/test_llm_service.py` (superseded by catalog tests) and fix its `register_provider` import; `services/api/tests/test_pack_chat.py` line ~97 uses `register_provider("anthropic", FakeProvider())` — that test asserts default-provider wiring; rewrite it to pass `provider=FakeProvider()` explicitly instead. Add `"openai>=1.50"` to `services/shared/pyproject.toml` dependencies; run `uv sync`.

- [ ] **Step 4: Run tests** — shared + api + worker suites → PASS.
- [ ] **Step 5: Commit** — `feat(llm): static provider catalog (4 providers / 2 adapters) + capability gate`

### Task 3: Anthropic adapter — per-call key, error mapping, streaming

**Files:**
- Rewrite: `services/shared/gulp_shared/llm/anthropic_provider.py`
- Create: `services/shared/tests/test_llm_anthropic.py`

**Interfaces:**
- Consumes: Task 1 types; `anthropic` SDK.
- Produces: `AnthropicProvider(client: Any | None = None)` — stateless; builds `AsyncAnthropic(api_key=config.api_key.get_secret_value())` per call unless a test client is injected. Maps `anthropic.AuthenticationError → LLMAuthError`, `anthropic.RateLimitError → LLMRateLimitError`. **No `settings` import remains in this file.**

- [ ] **Step 1: Write the failing test** — `services/shared/tests/test_llm_anthropic.py`:

```python
"""Anthropic adapter: serialization, forced-tool JSON, stream events."""

from types import SimpleNamespace
from typing import Any

import pytest
from gulp_shared.llm.anthropic_provider import AnthropicProvider, _serialize
from gulp_shared.llm.base import (
    ChatMessage,
    DoneEvent,
    ImagePart,
    ModelConfig,
    TextDelta,
    TextPart,
    ToolCall,
    ToolCallEvent,
    UsageEvent,
)

CFG = ModelConfig(provider="anthropic", model="claude-sonnet-4-6", api_key="sk-test")


def test_serialize_multimodal_and_tool_turns() -> None:
    msgs = [
        ChatMessage(role="user", content=[TextPart(text="?"), ImagePart(media_type="image/png", data_b64="aGk=")]),
        ChatMessage(role="assistant", content="using tool", tool_calls=[ToolCall(id="c1", name="t", arguments={"a": 1})]),
        ChatMessage(role="tool", content="result", tool_call_id="c1"),
    ]
    out = _serialize(msgs)
    assert out[0]["content"][1]["source"] == {"type": "base64", "media_type": "image/png", "data": "aGk="}
    assert out[1]["content"][-1] == {"type": "tool_use", "id": "c1", "name": "t", "input": {"a": 1}}
    assert out[2] == {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "result"}]}


class FakeMessages:
    def __init__(self, response: Any = None, stream: Any = None) -> None:
        self._response, self._stream = response, stream
        self.last_kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return self._response

    def stream(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return self._stream


class FakeStream:
    """Mimics the SDK's MessageStreamManager: async context + async iterator."""

    def __init__(self, events: list[Any], final: Any) -> None:
        self._events, self._final = events, final

    async def __aenter__(self) -> "FakeStream":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    def __aiter__(self) -> Any:
        async def gen() -> Any:
            for e in self._events:
                yield e

        return gen()

    async def get_final_message(self) -> Any:
        return self._final


def _tool_use_block(input_: dict[str, Any]) -> Any:
    return SimpleNamespace(type="tool_use", id="tu1", name="emit", input=input_)


async def test_complete_json_forces_tool_and_extracts_input() -> None:
    resp = SimpleNamespace(content=[_tool_use_block({"answer": "42"})])
    fake = SimpleNamespace(messages=FakeMessages(response=resp))
    out = await AnthropicProvider(client=fake).complete_json(
        system="s", messages=[ChatMessage(role="user", content="q")],
        json_schema={"type": "object"}, config=CFG,
    )
    assert out == {"answer": "42"}
    assert fake.messages.last_kwargs["tool_choice"] == {"type": "tool", "name": "emit"}


async def test_stream_chat_yields_deltas_toolcalls_usage_done() -> None:
    events = [
        SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type="text_delta", text="Hel")),
        SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type="text_delta", text="lo")),
    ]
    final = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", id="tu1", name="search", input={"q": "x"})],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        stop_reason="tool_use",
    )
    fake = SimpleNamespace(messages=FakeMessages(stream=FakeStream(events, final)))
    got = [e async for e in AnthropicProvider(client=fake).stream_chat(
        system=None, messages=[ChatMessage(role="user", content="q")], tools=None, config=CFG)]
    assert [e.type for e in got] == ["text_delta", "text_delta", "tool_call", "usage", "done"]
    assert isinstance(got[0], TextDelta) and got[0].text == "Hel"
    assert isinstance(got[2], ToolCallEvent) and got[2].tool_call.name == "search"
    assert isinstance(got[3], UsageEvent) and got[3].input_tokens == 10
    assert isinstance(got[4], DoneEvent) and got[4].stop_reason == "tool_use"
```

(Note: shared tests run with `asyncio_mode=auto` if configured — check `services/shared` pytest config; if not configured, add `@pytest.mark.asyncio`-free plain `anyio`/`asyncio` style used by `services/worker/tests/test_llm_service.py` — mirror whatever makes `async def test_` collect there, likely `[tool.pytest.ini_options] asyncio_mode = "auto"` in the worker `pyproject.toml`; copy that into `services/shared/pyproject.toml` if missing.)

- [ ] **Step 2: Run to verify failure** — FAIL (`_serialize` not defined).

- [ ] **Step 3: Rewrite `anthropic_provider.py`:**

```python
"""Anthropic adapter — structured output via forced tool use; streaming via the
Messages streaming API. Clients build per call from `config.api_key` (BYOK);
tests inject a fake via `client`."""

from collections.abc import AsyncIterator
from typing import Any, cast

import anthropic
from anthropic import AsyncAnthropic

from gulp_shared.llm.base import (
    ChatMessage,
    DoneEvent,
    LLMAuthError,
    LLMError,
    LLMRateLimitError,
    ModelConfig,
    StreamEvent,
    TextDelta,
    TextPart,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
    UsageEvent,
)

_TOOL_NAME = "emit"
_STOP_REASONS = {"end_turn": "stop", "tool_use": "tool_use", "max_tokens": "max_tokens"}


def _content_blocks(msg: ChatMessage) -> str | list[dict[str, Any]]:
    if isinstance(msg.content, str):
        return msg.content
    blocks: list[dict[str, Any]] = []
    for part in msg.content:
        if isinstance(part, TextPart):
            blocks.append({"type": "text", "text": part.text})
        else:
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": part.media_type,
                        "data": part.data_b64,
                    },
                }
            )
    return blocks


def _serialize(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            raise LLMError("system prompts go in the `system` parameter, not messages")
        if m.role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id,
                            "content": m.content if isinstance(m.content, str) else "",
                        }
                    ],
                }
            )
        elif m.role == "assistant" and m.tool_calls:
            blocks: list[dict[str, Any]] = []
            if isinstance(m.content, str) and m.content:
                blocks.append({"type": "text", "text": m.content})
            blocks += [
                {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                for c in m.tool_calls
            ]
            out.append({"role": "assistant", "content": blocks})
        else:
            out.append({"role": m.role, "content": _content_blocks(m)})
    return out


class AnthropicProvider:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def _get_client(self, config: ModelConfig) -> Any:
        if self._client is not None:
            return self._client
        return AsyncAnthropic(api_key=config.api_key.get_secret_value())

    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
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
            "messages": _serialize(messages),
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": _TOOL_NAME},
        }
        if system is not None:
            kwargs["system"] = system
        try:
            resp = await self._get_client(config).messages.create(**kwargs)
        except anthropic.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                return cast(dict[str, Any], block.input)
        raise LLMError("Anthropic response contained no tool_use block")

    async def stream_chat(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None,
        config: ModelConfig,
    ) -> AsyncIterator[StreamEvent]:
        kwargs: dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "messages": _serialize(messages),
        }
        if system is not None:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]
        try:
            async with self._get_client(config).messages.stream(**kwargs) as stream:
                async for event in stream:
                    if (
                        getattr(event, "type", None) == "content_block_delta"
                        and getattr(event.delta, "type", None) == "text_delta"
                    ):
                        yield TextDelta(text=event.delta.text)
                final = await stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        for block in final.content:
            if getattr(block, "type", None) == "tool_use":
                yield ToolCallEvent(
                    tool_call=ToolCall(
                        id=block.id, name=block.name, arguments=cast(dict[str, Any], block.input)
                    )
                )
        usage = getattr(final, "usage", None)
        if usage is not None:
            yield UsageEvent(input_tokens=usage.input_tokens, output_tokens=usage.output_tokens)
        stop = final.stop_reason or "stop"
        yield DoneEvent(stop_reason=_STOP_REASONS.get(stop, stop))
```

- [ ] **Step 4: Run tests** — the new file + full shared/api/worker suites → PASS.
- [ ] **Step 5: Commit** — `feat(llm): anthropic adapter — per-call BYOK client, error mapping, streaming`

### Task 4: OpenAI-compatible adapter (OpenAI / DeepSeek / Qwen)

**Files:**
- Rewrite: `services/shared/gulp_shared/llm/openai_compat.py` (replace Task 2 stub)
- Create: `services/shared/tests/test_llm_openai_compat.py`

**Interfaces:**
- Consumes: Task 1 types; `openai` SDK.
- Produces: `OpenAICompatProvider(client: Any | None = None)`; builds `AsyncOpenAI(api_key=..., base_url=config.base_url)` per call. Maps `openai.AuthenticationError → LLMAuthError`, `openai.RateLimitError → LLMRateLimitError`. Streaming aggregates function-call fragments by `index` into complete `ToolCallEvent`s; requests usage via `stream_options={"include_usage": True}`.

- [ ] **Step 1: Write the failing test** — `services/shared/tests/test_llm_openai_compat.py`:

```python
"""OpenAI-compatible adapter: serialization, forced function call, stream aggregation."""

from types import SimpleNamespace
from typing import Any

from gulp_shared.llm.base import ChatMessage, ImagePart, ModelConfig, TextPart, ToolCall
from gulp_shared.llm.openai_compat import OpenAICompatProvider, _serialize

CFG = ModelConfig(provider="deepseek", model="deepseek-chat", api_key="sk-test", base_url="https://api.deepseek.com")


def test_serialize_system_images_and_tool_turns() -> None:
    msgs = [
        ChatMessage(role="user", content=[TextPart(text="?"), ImagePart(media_type="image/png", data_b64="aGk=")]),
        ChatMessage(role="assistant", content="", tool_calls=[ToolCall(id="c1", name="t", arguments={"a": 1})]),
        ChatMessage(role="tool", content="res", tool_call_id="c1"),
    ]
    out = _serialize("sys", msgs)
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[1]["content"][1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGk="}}
    assert out[2]["tool_calls"][0]["function"] == {"name": "t", "arguments": '{"a": 1}'}
    assert out[3] == {"role": "tool", "tool_call_id": "c1", "content": "res"}


class FakeCompletions:
    def __init__(self, result: Any) -> None:
        self._result = result
        self.last_kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return self._result


def _fake_client(result: Any) -> Any:
    return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(result)))


async def test_complete_json_parses_forced_function_call() -> None:
    resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[
        SimpleNamespace(function=SimpleNamespace(name="emit", arguments='{"answer": "42"}'))
    ]))])
    fake = _fake_client(resp)
    out = await OpenAICompatProvider(client=fake).complete_json(
        system="s", messages=[ChatMessage(role="user", content="q")],
        json_schema={"type": "object"}, config=CFG,
    )
    assert out == {"answer": "42"}
    assert fake.chat.completions.last_kwargs["tool_choice"]["function"]["name"] == "emit"


def _chunk(content: str | None = None, tool_calls: Any = None, finish: str | None = None, usage: Any = None) -> Any:
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(delta=delta, finish_reason=finish)
    return SimpleNamespace(choices=[choice] if (content or tool_calls or finish) else [], usage=usage)


async def _agen(items: list[Any]) -> Any:
    for item in items:
        yield item


async def test_stream_chat_aggregates_tool_call_fragments() -> None:
    frag1 = [SimpleNamespace(index=0, id="c1", function=SimpleNamespace(name="search", arguments='{"q":'))]
    frag2 = [SimpleNamespace(index=0, id=None, function=SimpleNamespace(name=None, arguments='"x"}'))]
    chunks = [
        _chunk(content="Hi"),
        _chunk(tool_calls=frag1),
        _chunk(tool_calls=frag2),
        _chunk(finish="tool_calls"),
        _chunk(usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3)),
    ]
    fake = _fake_client(_agen(chunks))
    got = [e async for e in OpenAICompatProvider(client=fake).stream_chat(
        system=None, messages=[ChatMessage(role="user", content="q")], tools=None, config=CFG)]
    assert [e.type for e in got] == ["text_delta", "tool_call", "usage", "done"]
    assert got[1].tool_call == ToolCall(id="c1", name="search", arguments={"q": "x"})
    assert got[3].stop_reason == "tool_use"
```

- [ ] **Step 2: Run to verify failure** — FAIL (`_serialize` missing / NotImplementedError).

- [ ] **Step 3: Implement** (full file replace):

```python
"""OpenAI-compatible adapter — one wire format covers OpenAI, DeepSeek, and
Qwen (DashScope compatible-mode). Structured output via a forced function
call; clients build per call from `config` (BYOK)."""

import json
from collections.abc import AsyncIterator
from typing import Any, cast

import openai
from openai import AsyncOpenAI

from gulp_shared.llm.base import (
    ChatMessage,
    DoneEvent,
    LLMAuthError,
    LLMError,
    LLMRateLimitError,
    ModelConfig,
    StreamEvent,
    TextDelta,
    TextPart,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
    UsageEvent,
)

_TOOL_NAME = "emit"
_STOP_REASONS = {"stop": "stop", "tool_calls": "tool_use", "length": "max_tokens"}


def _content(msg: ChatMessage) -> Any:
    if isinstance(msg.content, str):
        return msg.content
    parts: list[dict[str, Any]] = []
    for part in msg.content:
        if isinstance(part, TextPart):
            parts.append({"type": "text", "text": part.text})
        else:
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{part.media_type};base64,{part.data_b64}"},
                }
            )
    return parts


def _serialize(system: str | None, messages: list[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if system is not None:
        out.append({"role": "system", "content": system})
    for m in messages:
        if m.role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id,
                    "content": m.content if isinstance(m.content, str) else "",
                }
            )
        elif m.role == "assistant" and m.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": m.content if isinstance(m.content, str) else None,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                        }
                        for c in m.tool_calls
                    ],
                }
            )
        else:
            out.append({"role": m.role, "content": _content(m)})
    return out


def _tool_param(t: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {"name": t.name, "description": t.description, "parameters": t.input_schema},
    }


class OpenAICompatProvider:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def _get_client(self, config: ModelConfig) -> Any:
        if self._client is not None:
            return self._client
        return AsyncOpenAI(api_key=config.api_key.get_secret_value(), base_url=config.base_url)

    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]:
        tool = {
            "type": "function",
            "function": {
                "name": _TOOL_NAME,
                "description": "Return the structured result for this task.",
                "parameters": json_schema,
            },
        }
        try:
            resp = await self._get_client(config).chat.completions.create(
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                messages=_serialize(system, messages),
                tools=[tool],
                tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
            )
        except openai.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except openai.RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        for call in resp.choices[0].message.tool_calls or []:
            if call.function.name == _TOOL_NAME:
                return cast(dict[str, Any], json.loads(call.function.arguments))
        raise LLMError("response contained no forced function call")

    async def stream_chat(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None,
        config: ModelConfig,
    ) -> AsyncIterator[StreamEvent]:
        kwargs: dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "messages": _serialize(system, messages),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = [_tool_param(t) for t in tools]
        pending: dict[int, dict[str, Any]] = {}
        finish = "stop"
        usage: Any = None
        try:
            stream = await self._get_client(config).chat.completions.create(**kwargs)
            async for chunk in stream:
                usage = getattr(chunk, "usage", None) or usage
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if getattr(choice.delta, "content", None):
                    yield TextDelta(text=choice.delta.content)
                for tc in getattr(choice.delta, "tool_calls", None) or []:
                    slot = pending.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                    slot["id"] = tc.id or slot["id"]
                    if tc.function is not None:
                        slot["name"] = tc.function.name or slot["name"]
                        slot["arguments"] += tc.function.arguments or ""
                if choice.finish_reason:
                    finish = choice.finish_reason
        except openai.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except openai.RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        for i in sorted(pending):
            slot = pending[i]
            yield ToolCallEvent(
                tool_call=ToolCall(
                    id=slot["id"], name=slot["name"], arguments=json.loads(slot["arguments"] or "{}")
                )
            )
        if usage is not None:
            yield UsageEvent(input_tokens=usage.prompt_tokens, output_tokens=usage.completion_tokens)
        yield DoneEvent(stop_reason=_STOP_REASONS.get(finish, finish))
```

- [ ] **Step 4: Run tests** — new file + all three Python suites → PASS.
- [ ] **Step 5: Commit** — `feat(llm): openai-compatible adapter for openai/deepseek/qwen`

### Task 5: Key resolution entry point + wire it into chat and pipeline

**Files:**
- Create: `services/shared/gulp_shared/llm/resolve.py`
- Modify: `services/shared/gulp_shared/llm/__init__.py` (export `resolve_model_config`)
- Modify: `services/api/app/services/chat.py`, `services/api/app/main.py`
- Modify: `services/worker/app/pipeline/run.py`, `services/worker/app/pipeline/cards.py`, `services/worker/app/pipeline/digest.py` (drop `settings.llm_*` defaults)
- Create: `services/shared/tests/test_llm_resolve.py`
- Modify: `services/api/tests/test_pack_chat.py` (fake provider path unaffected — verify)

**Interfaces:**
- Produces: `resolve_model_config(db: Session, user_id: uuid.UUID) -> ModelConfig` (raises `LLMNotConfiguredError`) — slice 1 body is env-fallback only; Task 8 adds the DB lookup. Internal helper `_env_fallback() -> ModelConfig`.
- API error mapping (in `main.py`): `LLMNotConfiguredError → 409 {"detail": "llm_not_configured"}`, `LLMAuthError → 409 {"detail": "llm_key_invalid"}`, `LLMRateLimitError → 429 {"detail": "llm_rate_limited"}`.

- [ ] **Step 1: Write the failing test** — `services/shared/tests/test_llm_resolve.py`:

```python
"""Key resolution: env fallback path (BYOK DB path arrives with its own tests)."""

import uuid

import pytest
from gulp_shared.llm.base import LLMNotConfiguredError
from gulp_shared.llm.resolve import resolve_model_config
from gulp_shared.settings import settings


def test_env_fallback_builds_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-env")
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "llm_model", "claude-sonnet-4-6")
    cfg = resolve_model_config(None, uuid.uuid4())  # type: ignore[arg-type]  # db unused in slice 1
    assert cfg.provider == "anthropic" and cfg.model == "claude-sonnet-4-6"
    assert cfg.api_key.get_secret_value() == "sk-env"


def test_no_key_raises_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(LLMNotConfiguredError):
        resolve_model_config(None, uuid.uuid4())  # type: ignore[arg-type]
```

- [ ] **Step 2: Run to verify failure** — FAIL (no module `resolve`).

- [ ] **Step 3: Implement.** `services/shared/gulp_shared/llm/resolve.py`:

```python
"""Resolve which model + key a call should use (spec 2026-07-13 §5.1). The
single entry point for API and worker; per-user BYOK credentials land here in
the BYOK slice — until then the env key is the only (dev) path."""

import uuid

from pydantic import SecretStr
from sqlalchemy.orm import Session

from gulp_shared.llm.base import LLMNotConfiguredError, ModelConfig
from gulp_shared.llm.catalog import get_spec
from gulp_shared.settings import settings


def resolve_model_config(db: Session, user_id: uuid.UUID) -> ModelConfig:
    return _env_fallback()


def _env_fallback() -> ModelConfig:
    if not settings.anthropic_api_key:
        raise LLMNotConfiguredError("no LLM credentials configured")
    spec = get_spec(settings.llm_provider)
    return ModelConfig(
        provider=spec.name,
        model=settings.llm_model,
        api_key=SecretStr(settings.anthropic_api_key),
        base_url=spec.base_url,
    )
```

Wire-in edits:

1. `services/api/app/services/chat.py::answer_question` — replace the `config=ModelConfig(provider=settings.llm_provider, ...)` call with:

```python
    source = db.get(Source, snapshot_id)
    cfg = ModelConfig() if provider is not None else resolve_model_config(db, source.owner_id)
    result = await complete_structured(
        response_model=ChatAnswer,
        messages=messages,
        system=system,
        config=cfg,
        provider=provider,
    )
```

(import `resolve_model_config` from `gulp_shared.llm`; drop the now-unused `settings` import.)

2. `services/api/app/main.py` — register handlers after `app = FastAPI(...)`:

```python
from gulp_shared.llm.base import LLMAuthError, LLMNotConfiguredError, LLMRateLimitError
from starlette.responses import JSONResponse


@app.exception_handler(LLMNotConfiguredError)
async def _llm_not_configured(request: Request, exc: LLMNotConfiguredError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "llm_not_configured"})


@app.exception_handler(LLMAuthError)
async def _llm_auth(request: Request, exc: LLMAuthError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "llm_key_invalid"})


@app.exception_handler(LLMRateLimitError)
async def _llm_rate_limited(request: Request, exc: LLMRateLimitError) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "llm_rate_limited"})
```

3. `services/worker/app/pipeline/run.py::process_source` — inside the `try`, after genre detection and before `build_pack_draft` (import `SourceGenre` and `resolve_model_config`):

```python
        if provider is None and config is None and source.genre is SourceGenre.paper:
            config = resolve_model_config(db, source.owner_id)
```

4. `services/worker/app/pipeline/cards.py::generate_cards_for_source` — first line inside its `try` (import `resolve_model_config`):

```python
        if provider is None and config is None:
            config = resolve_model_config(db, source.owner_id)
```

5. `digest.py::run_digest` and `cards.py::run_cards`: change `cfg = config or ModelConfig(provider=settings.llm_provider, model=settings.llm_model)` → `cfg = config or ModelConfig()`; drop `settings` imports if now unused.

- [ ] **Step 4: Run all Python suites + `just lint`** → PASS (pipeline tests inject fake providers so the resolver is bypassed).
- [ ] **Step 5: Commit** — `feat(llm): resolve_model_config entry point; wire chat + pipeline; API error mapping`

---

## Slice 2 — BYOK: encrypted credentials, /me/llm API, settings page

### Task 6: Credential encryption + `credential_secret` setting

**Files:**
- Create: `services/shared/gulp_shared/llm/crypto.py`
- Modify: `services/shared/gulp_shared/settings.py` (add `credential_secret: str = "change-me-too"`), `.env.example`, `services/shared/pyproject.toml` (add `"cryptography>=43"`)
- Create: `services/shared/tests/test_llm_crypto.py`

**Interfaces (produced):** `encrypt_key(plaintext: str) -> bytes`, `decrypt_key(token: bytes) -> str` (raises `LLMError` on tamper/secret change), `mask_key(plaintext: str) -> str` (`"…" + last 4 chars`).

- [ ] **Step 1: Write the failing test** — `services/shared/tests/test_llm_crypto.py`:

```python
"""Fernet round-trip + masking for stored provider keys."""

import pytest
from gulp_shared.llm.base import LLMError
from gulp_shared.llm.crypto import decrypt_key, encrypt_key, mask_key


def test_encrypt_decrypt_round_trip() -> None:
    token = encrypt_key("sk-secret-1234")
    assert isinstance(token, bytes) and b"sk-secret" not in token
    assert decrypt_key(token) == "sk-secret-1234"


def test_decrypt_garbage_raises_llm_error() -> None:
    with pytest.raises(LLMError):
        decrypt_key(b"not-a-fernet-token")


def test_mask_key_shows_last_four_only() -> None:
    assert mask_key("sk-abcdefgh1234") == "…1234"
    assert mask_key("abc") == "…"  # too short to reveal anything
```

- [ ] **Step 2: Run to verify failure** — FAIL (no module `crypto`).

- [ ] **Step 3: Implement.** Add `"cryptography>=43"` to shared deps, `uv sync`. `services/shared/gulp_shared/llm/crypto.py`:

```python
"""Fernet encryption for stored provider keys (spec 2026-07-13 §4.2). Keyed by
`settings.credential_secret` — independent of `auth_secret` so they rotate
independently. Plaintext exists in memory only at call time."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from gulp_shared.llm.base import LLMError
from gulp_shared.settings import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.credential_secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_key(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt_key(token: bytes) -> str:
    try:
        return _fernet().decrypt(token).decode()
    except InvalidToken as exc:
        raise LLMError("stored credential cannot be decrypted") from exc


def mask_key(plaintext: str) -> str:
    if len(plaintext) <= 4:
        return "…"
    return f"…{plaintext[-4:]}"
```

Settings: add `credential_secret: str = "change-me-too"` next to `auth_secret`. `.env.example`: under the Auth block add `CREDENTIAL_SECRET=change-me-too` with comment `# Encrypts stored BYOK provider keys (spec 2026-07-13). Rotate independently of AUTH_SECRET.`; amend the LLM block comment to `# Dev fallback only — users bring their own keys (BYOK). Leave unset in production.`

- [ ] **Step 4: Run tests** → PASS. **Step 5: Commit** — `feat(llm): fernet credential encryption + credential_secret setting`

### Task 7: `UserLLMCredential` model + user default columns + migration

**Files:**
- Create: `services/shared/gulp_shared/models/user_llm_credential.py`
- Modify: `services/shared/gulp_shared/models/user.py` (add `llm_provider`, `llm_model`), `services/shared/gulp_shared/models/__init__.py` (export)
- Create: `services/api/alembic/versions/c3d4e5f6a7b8_byok_llm_credentials.py`
- Create: `services/shared/tests/test_user_llm_credential.py`

**Interfaces (produced):** `UserLLMCredential(user_id: uuid, provider: str, api_key_encrypted: bytes)` — table `user_llm_credentials`, unique `(user_id, provider)`; `User.llm_provider: str | None`, `User.llm_model: str | None`.

- [ ] **Step 1: Write the failing test** — `services/shared/tests/test_user_llm_credential.py` (mirror the session fixture style of `services/shared/tests/test_user_model.py` / its conftest):

```python
"""BYOK credential rows + the user's default provider/model columns."""

import pytest
from gulp_shared.models.user import User
from gulp_shared.models.user_llm_credential import UserLLMCredential
from sqlalchemy.exc import IntegrityError


def test_credential_row_and_user_defaults(session) -> None:  # type: ignore[no-untyped-def]
    user = User(display_name="A")
    session.add(user)
    session.flush()
    assert user.llm_provider is None and user.llm_model is None
    cred = UserLLMCredential(user_id=user.id, provider="deepseek", api_key_encrypted=b"tok")
    session.add(cred)
    session.flush()
    assert cred.id is not None and cred.created_at is not None
    user.llm_provider, user.llm_model = "deepseek", "deepseek-chat"
    session.flush()


def test_one_row_per_user_provider(session) -> None:  # type: ignore[no-untyped-def]
    user = User(display_name="B")
    session.add(user)
    session.flush()
    session.add(UserLLMCredential(user_id=user.id, provider="openai", api_key_encrypted=b"a"))
    session.flush()
    session.add(UserLLMCredential(user_id=user.id, provider="openai", api_key_encrypted=b"b"))
    with pytest.raises(IntegrityError):
        session.flush()
```

(Use the existing shared-tests `session`/db fixture name — check `services/shared/tests/conftest.py` and match it exactly.)

- [ ] **Step 2: Run to verify failure** — FAIL (no module `user_llm_credential`).

- [ ] **Step 3: Implement.** `services/shared/gulp_shared/models/user_llm_credential.py`:

```python
"""UserLLMCredential — one encrypted BYOK API key per (user, provider)
(spec 2026-07-13 §4.1). The plaintext never leaves `gulp_shared.llm.crypto`."""

import uuid

from sqlalchemy import ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class UserLLMCredential(TimestampedBase, Base):
    __tablename__ = "user_llm_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_llm_credentials_user_provider"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String)
    api_key_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
```

`user.py` — add below `gulp_session_minutes`:

```python
    # BYOK default model selection (spec 2026-07-13 §4.1); NULL = not configured.
    llm_provider: Mapped[str | None] = mapped_column(String, default=None)
    llm_model: Mapped[str | None] = mapped_column(String, default=None)
```

Export `UserLLMCredential` from `models/__init__.py` (match existing style). Migration `services/api/alembic/versions/c3d4e5f6a7b8_byok_llm_credentials.py` (head confirmed `a9b0c1d2e3f4`):

```python
"""byok: user_llm_credentials table + users default provider/model

Revision ID: c3d4e5f6a7b8
Revises: a9b0c1d2e3f4
"""

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_llm_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("api_key_encrypted", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_llm_credentials_user_provider"),
    )
    op.create_index(
        op.f("ix_user_llm_credentials_user_id"), "user_llm_credentials", ["user_id"]
    )
    op.add_column("users", sa.Column("llm_provider", sa.String(), nullable=True))
    op.add_column("users", sa.Column("llm_model", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "llm_model")
    op.drop_column("users", "llm_provider")
    op.drop_index(op.f("ix_user_llm_credentials_user_id"), table_name="user_llm_credentials")
    op.drop_table("user_llm_credentials")
```

- [ ] **Step 4: Run tests + apply migration** — suites PASS; `just migrate-up` succeeds (requires `just up` infra); `cd services/api && uv run alembic heads` shows `c3d4e5f6a7b8`.
- [ ] **Step 5: Commit** — `feat(llm): user_llm_credentials table + user default provider/model`

### Task 8: Full BYOK resolution + credential ping

**Files:**
- Modify: `services/shared/gulp_shared/llm/resolve.py`
- Modify: `services/shared/tests/test_llm_resolve.py` (extend)

**Interfaces:**
- Consumes: Tasks 6-7 (`crypto`, `UserLLMCredential`, user columns).
- Produces: `resolve_model_config` now: user default + decrypted credential → `ModelConfig`; else env fallback; else `LLMNotConfiguredError`. New `async ping_credential(provider_name: str, api_key: str) -> None` — cheapest live call (`max_tokens=1` stream), raising `LLMAuthError` on a bad key. Both exported from `gulp_shared.llm`.

- [ ] **Step 1: Extend the test** (uses a sqlite session fixture like Task 7 plus monkeypatched settings):

```python
def test_byok_credential_wins_over_env(session, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from gulp_shared.llm.crypto import encrypt_key
    from gulp_shared.models.user import User
    from gulp_shared.models.user_llm_credential import UserLLMCredential

    monkeypatch.setattr(settings, "anthropic_api_key", "sk-env")
    user = User(display_name="C", llm_provider="deepseek", llm_model="deepseek-chat")
    session.add(user)
    session.flush()
    session.add(
        UserLLMCredential(
            user_id=user.id, provider="deepseek", api_key_encrypted=encrypt_key("sk-user")
        )
    )
    session.flush()
    cfg = resolve_model_config(session, user.id)
    assert cfg.provider == "deepseek" and cfg.model == "deepseek-chat"
    assert cfg.api_key.get_secret_value() == "sk-user"
    assert cfg.base_url == "https://api.deepseek.com"


def test_default_without_credential_falls_back(session, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from gulp_shared.models.user import User

    monkeypatch.setattr(settings, "anthropic_api_key", "sk-env")
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    user = User(display_name="D", llm_provider="qwen", llm_model="qwen-plus")  # no key row
    session.add(user)
    session.flush()
    assert resolve_model_config(session, user.id).api_key.get_secret_value() == "sk-env"


async def test_ping_credential_hits_stream_once() -> None:
    from gulp_shared.llm import catalog
    from gulp_shared.llm.resolve import ping_credential

    calls: list[str] = []

    class PingFake:
        async def complete_json(self, **kw):  # type: ignore[no-untyped-def]
            raise AssertionError("ping must stream")

        async def stream_chat(self, *, system, messages, tools, config):  # type: ignore[no-untyped-def]
            calls.append(config.api_key.get_secret_value())
            yield TextDelta(text="ok")

    spec = catalog.PROVIDERS["deepseek"]
    fake_spec = catalog.ProviderSpec(
        name=spec.name, adapter=PingFake(), base_url=spec.base_url,
        capabilities=spec.capabilities, models=spec.models,
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(catalog.PROVIDERS, "deepseek", fake_spec)
        await ping_credential("deepseek", "sk-ping")
    assert calls == ["sk-ping"]
```

- [ ] **Step 2: Run to verify failure** — the BYOK tests FAIL (env config returned / `ping_credential` missing).

- [ ] **Step 3: Implement** — replace `resolve_model_config` body and append `ping_credential`:

```python
def resolve_model_config(db: Session, user_id: uuid.UUID) -> ModelConfig:
    user = db.get(User, user_id)
    if user is not None and user.llm_provider and user.llm_model:
        cred = db.scalar(
            select(UserLLMCredential).where(
                UserLLMCredential.user_id == user_id,
                UserLLMCredential.provider == user.llm_provider,
                UserLLMCredential.deleted_at.is_(None),
            )
        )
        if cred is not None:
            spec = get_spec(user.llm_provider)
            return ModelConfig(
                provider=spec.name,
                model=user.llm_model,
                api_key=SecretStr(decrypt_key(cred.api_key_encrypted)),
                base_url=spec.base_url,
            )
    return _env_fallback()


async def ping_credential(provider_name: str, api_key: str) -> None:
    """Cheapest possible live call; raises LLMAuthError when the key is bad."""
    spec = get_spec(provider_name)
    cfg = ModelConfig(
        provider=spec.name,
        model=spec.models[0].id,
        api_key=SecretStr(api_key),
        base_url=spec.base_url,
        max_tokens=1,
    )
    events = spec.adapter.stream_chat(
        system=None,
        messages=[ChatMessage(role="user", content="ping")],
        tools=None,
        config=cfg,
    )
    async for _ in events:
        break
```

(new imports: `select` from sqlalchemy, `User`, `UserLLMCredential`, `decrypt_key`, `ChatMessage`; export `ping_credential` in `llm/__init__.py`. NB the docstring of the module: drop the "until then" sentence.)

- [ ] **Step 4: Run suites** → PASS. **Step 5: Commit** — `feat(llm): per-user BYOK resolution + credential ping`

### Task 9: `/me/llm` API (schemas, service, router)

**Files:**
- Create: `services/api/app/schemas/llm.py`, `services/api/app/services/llm_settings.py`, `services/api/app/routers/llm.py`
- Modify: `services/api/app/main.py` (include router), `services/api/app/routers/__init__.py` if routers are re-exported there (mirror existing pattern)
- Create: `services/api/tests/test_llm_settings.py`

**Interfaces:**
- Produces (wire): `GET /me/llm → LLMSettingsOut{default_provider, default_model, credentials: [CredentialOut{provider, masked_key}], catalog: [ProviderCatalogOut{provider, capabilities, models: [ModelInfoOut{id, label}]}]}`; `PUT /me/llm/credentials/{provider}` body `{api_key}` → `CredentialOut` (400 `invalid_key`, 404 unknown provider); `DELETE /me/llm/credentials/{provider}` → 204 (404 if none; clears default if it pointed there); `PUT /me/llm/default` body `{provider, model}` → 204 (409 `no_credential`, 422 unknown model, 404 unknown provider).
- Produces (python): `app.services.llm_settings.{get_llm_settings, set_credential, delete_credential, set_default}`; `set_credential` is async and calls `ping_credential` (monkeypatch target: `app.services.llm_settings.ping_credential`).

- [ ] **Step 1: Write the failing test** — `services/api/tests/test_llm_settings.py`:

```python
"""BYOK settings endpoints: masked listing, validated save, default rules."""

import pytest
from app.deps import get_db
from app.main import app
from fastapi.testclient import TestClient
from gulp_shared.llm.base import LLMAuthError


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def ping_ok(monkeypatch):  # type: ignore[no-untyped-def]
    async def _ok(provider: str, api_key: str) -> None:
        return None

    monkeypatch.setattr("app.services.llm_settings.ping_credential", _ok)


def test_get_settings_empty_state_serves_catalog(client) -> None:  # type: ignore[no-untyped-def]
    body = client.get("/me/llm").json()
    assert body["default_provider"] is None and body["credentials"] == []
    providers = {c["provider"] for c in body["catalog"]}
    assert providers == {"anthropic", "openai", "deepseek", "qwen"}
    deepseek = next(c for c in body["catalog"] if c["provider"] == "deepseek")
    assert "vision" not in deepseek["capabilities"] and deepseek["models"]


def test_put_credential_validates_and_masks(client, ping_ok) -> None:  # type: ignore[no-untyped-def]
    r = client.put("/me/llm/credentials/deepseek", json={"api_key": "sk-abcdef123456"})
    assert r.status_code == 200
    assert r.json() == {"provider": "deepseek", "masked_key": "…3456"}
    listed = client.get("/me/llm").json()["credentials"]
    assert listed == [{"provider": "deepseek", "masked_key": "…3456"}]
    assert "sk-abcdef123456" not in listed[0]["masked_key"]


def test_put_credential_bad_key_rejected_not_stored(client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def _bad(provider: str, api_key: str) -> None:
        raise LLMAuthError("nope")

    monkeypatch.setattr("app.services.llm_settings.ping_credential", _bad)
    r = client.put("/me/llm/credentials/openai", json={"api_key": "sk-bad"})
    assert r.status_code == 400 and r.json()["detail"] == "invalid_key"
    assert client.get("/me/llm").json()["credentials"] == []


def test_put_credential_unknown_provider_404(client, ping_ok) -> None:  # type: ignore[no-untyped-def]
    assert client.put("/me/llm/credentials/copilot", json={"api_key": "x"}).status_code == 404


def test_default_requires_credential_and_known_model(client, ping_ok) -> None:  # type: ignore[no-untyped-def]
    assert client.put("/me/llm/default", json={"provider": "deepseek", "model": "deepseek-chat"}).status_code == 409
    client.put("/me/llm/credentials/deepseek", json={"api_key": "sk-abcdef123456"})
    assert client.put("/me/llm/default", json={"provider": "deepseek", "model": "gpt-4.1"}).status_code == 422
    assert client.put("/me/llm/default", json={"provider": "deepseek", "model": "deepseek-chat"}).status_code == 204
    body = client.get("/me/llm").json()
    assert (body["default_provider"], body["default_model"]) == ("deepseek", "deepseek-chat")


def test_delete_credential_clears_matching_default(client, ping_ok) -> None:  # type: ignore[no-untyped-def]
    client.put("/me/llm/credentials/deepseek", json={"api_key": "sk-abcdef123456"})
    client.put("/me/llm/default", json={"provider": "deepseek", "model": "deepseek-chat"})
    assert client.delete("/me/llm/credentials/deepseek").status_code == 204
    body = client.get("/me/llm").json()
    assert body["credentials"] == [] and body["default_provider"] is None
    assert client.delete("/me/llm/credentials/deepseek").status_code == 404
```

- [ ] **Step 2: Run to verify failure** — 404s (no routes).

- [ ] **Step 3: Implement.** `app/schemas/llm.py`:

```python
"""BYOK LLM settings contract — becomes the OpenAPI types the web client reads."""

from pydantic import BaseModel


class ModelInfoOut(BaseModel):
    id: str
    label: str


class ProviderCatalogOut(BaseModel):
    provider: str
    capabilities: list[str]
    models: list[ModelInfoOut]


class CredentialOut(BaseModel):
    provider: str
    masked_key: str


class LLMSettingsOut(BaseModel):
    default_provider: str | None
    default_model: str | None
    credentials: list[CredentialOut]
    catalog: list[ProviderCatalogOut]


class CredentialIn(BaseModel):
    api_key: str


class DefaultIn(BaseModel):
    provider: str
    model: str
```

`app/services/llm_settings.py`:

```python
"""BYOK credential + default-model management (spec 2026-07-13 §4). The
plaintext key is validated with a live ping, encrypted at rest, and only ever
surfaced masked."""

from gulp_shared.llm.catalog import PROVIDERS, get_spec
from gulp_shared.llm.crypto import decrypt_key, encrypt_key, mask_key
from gulp_shared.llm.resolve import ping_credential
from gulp_shared.models.user import User
from gulp_shared.models.user_llm_credential import UserLLMCredential
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.llm import CredentialOut, LLMSettingsOut, ModelInfoOut, ProviderCatalogOut


def _catalog() -> list[ProviderCatalogOut]:
    return [
        ProviderCatalogOut(
            provider=spec.name,
            capabilities=sorted(spec.capabilities),
            models=[ModelInfoOut(id=m.id, label=m.label) for m in spec.models],
        )
        for spec in PROVIDERS.values()
    ]


def _find(db: Session, user: User, provider: str) -> UserLLMCredential | None:
    return db.scalar(
        select(UserLLMCredential).where(
            UserLLMCredential.user_id == user.id,
            UserLLMCredential.provider == provider,
            UserLLMCredential.deleted_at.is_(None),
        )
    )


def get_llm_settings(db: Session, user: User) -> LLMSettingsOut:
    rows = db.scalars(
        select(UserLLMCredential)
        .where(UserLLMCredential.user_id == user.id, UserLLMCredential.deleted_at.is_(None))
        .order_by(UserLLMCredential.provider)
    )
    return LLMSettingsOut(
        default_provider=user.llm_provider,
        default_model=user.llm_model,
        credentials=[
            CredentialOut(provider=c.provider, masked_key=mask_key(decrypt_key(c.api_key_encrypted)))
            for c in rows
        ],
        catalog=_catalog(),
    )


async def set_credential(db: Session, user: User, provider: str, api_key: str) -> CredentialOut:
    get_spec(provider)  # unknown provider -> LLMError -> 404 in the router
    await ping_credential(provider, api_key)  # bad key -> LLMAuthError -> 400
    cred = _find(db, user, provider)
    if cred is None:
        db.add(
            UserLLMCredential(
                user_id=user.id, provider=provider, api_key_encrypted=encrypt_key(api_key)
            )
        )
    else:
        cred.api_key_encrypted = encrypt_key(api_key)
    db.commit()
    return CredentialOut(provider=provider, masked_key=mask_key(api_key))


def delete_credential(db: Session, user: User, provider: str) -> None:
    cred = _find(db, user, provider)
    if cred is None:
        raise LookupError("credential not found")
    db.delete(cred)
    if user.llm_provider == provider:
        user.llm_provider = None
        user.llm_model = None
    db.commit()


def set_default(db: Session, user: User, provider: str, model: str) -> None:
    spec = get_spec(provider)  # unknown provider -> LLMError -> 404
    if model not in {m.id for m in spec.models}:
        raise ValueError(f"unknown model {model!r} for {provider}")
    if _find(db, user, provider) is None:
        raise LookupError(f"no credential stored for {provider}")
    user.llm_provider = provider
    user.llm_model = model
    db.commit()
```

`app/routers/llm.py`:

```python
"""BYOK LLM settings routes — thin over services.llm_settings."""

from fastapi import APIRouter, Depends, HTTPException
from gulp_shared.llm.base import LLMAuthError, LLMError
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.llm import CredentialIn, CredentialOut, DefaultIn, LLMSettingsOut
from app.services.llm_settings import (
    delete_credential,
    get_llm_settings,
    set_credential,
    set_default,
)

router = APIRouter(prefix="/me/llm")


@router.get("", response_model=LLMSettingsOut)
def get_settings_route(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LLMSettingsOut:
    return get_llm_settings(db, user)


@router.put("/credentials/{provider}", response_model=CredentialOut)
async def put_credential_route(
    provider: str,
    body: CredentialIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CredentialOut:
    try:
        return await set_credential(db, user, provider, body.api_key)
    except LLMAuthError:
        raise HTTPException(status_code=400, detail="invalid_key") from None
    except LLMError:
        raise HTTPException(status_code=404, detail="unknown provider") from None


@router.delete("/credentials/{provider}", status_code=204)
def delete_credential_route(
    provider: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        delete_credential(db, user, provider)
    except LookupError:
        raise HTTPException(status_code=404, detail="credential not found") from None


@router.put("/default", status_code=204)
def put_default_route(
    body: DefaultIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        set_default(db, user, body.provider, body.model)
    except LLMError:
        raise HTTPException(status_code=404, detail="unknown provider") from None
    except ValueError:
        raise HTTPException(status_code=422, detail="unknown model") from None
    except LookupError:
        raise HTTPException(status_code=409, detail="no_credential") from None
```

Register in `main.py`: import `llm` in the routers import block; `app.include_router(llm.router, tags=["llm"])` after `library`. **Gotcha:** the app-level `LLMAuthError` handler (Task 5) returns 409 — the router's explicit `except LLMAuthError` catches first, so the save path still returns 400; keep both.

- [ ] **Step 4: Run api suite** → PASS. **Step 5: Commit** — `feat(api): /me/llm BYOK settings endpoints`

### Task 10: Regenerate client + typed helpers

**Files:**
- Regenerate: `packages/api-client/src/schema.gen.ts` (`just gen-client`)
- Modify: `packages/api-client/src/index.ts`

**Interfaces (produced, consumed by Task 11):**

```ts
export type LLMSettingsOut = paths["/me/llm"]["get"]["responses"]["200"]["content"]["application/json"];
export async function getLLMSettings(options?: ApiRequestOptions): Promise<LLMSettingsOut>;
export async function putLLMCredential(provider: string, apiKey: string): Promise<void>;
export async function deleteLLMCredential(provider: string): Promise<void>;
export async function putLLMDefault(provider: string, model: string): Promise<void>;
```

- [ ] **Step 1: Regenerate** — `just gen-client` (check the recipe; it may need the api venv). Diff `schema.gen.ts` — `/me/llm` paths present.
- [ ] **Step 2: Add helpers** to `packages/api-client/src/index.ts` (follow the existing helper style exactly):

```ts
export type LLMSettingsOut =
  paths["/me/llm"]["get"]["responses"]["200"]["content"]["application/json"];

export async function getLLMSettings(
  options?: ApiRequestOptions,
): Promise<LLMSettingsOut> {
  const { data, error } = await client.GET("/me/llm", {
    cache: "no-store",
    headers: options?.headers,
  });
  if (error || !data) throw new Error("llm settings fetch failed");
  return data;
}

export async function putLLMCredential(
  provider: string,
  apiKey: string,
): Promise<void> {
  const { error, response } = await client.PUT("/me/llm/credentials/{provider}", {
    params: { path: { provider } },
    body: { api_key: apiKey },
  });
  if (error) {
    throw new Error(response?.status === 400 ? "invalid_key" : "credential save failed");
  }
}

export async function deleteLLMCredential(provider: string): Promise<void> {
  const { error } = await client.DELETE("/me/llm/credentials/{provider}", {
    params: { path: { provider } },
  });
  if (error) throw new Error("credential delete failed");
}

export async function putLLMDefault(provider: string, model: string): Promise<void> {
  const { error } = await client.PUT("/me/llm/default", {
    body: { provider, model },
  });
  if (error) throw new Error("default save failed");
}
```

- [ ] **Step 3: Verify** — `pnpm --filter @gulp/api-client exec tsc --noEmit` shows ONLY the 2 pre-existing dup-identifier errors; `just lint` green.
- [ ] **Step 4: Commit** — `feat(api-client): /me/llm settings helpers`

### Task 11: Web "AI models" settings page

**Files:**
- Create: `apps/web/app/settings/ai/page.tsx`, `apps/web/components/settings/AISettings.tsx`, `apps/web/components/settings/AISettings.module.css`, `apps/web/components/settings/AISettings.test.tsx`
- Modify: `apps/web/components/shell/AccountMenu.tsx` (link above logout)

**Interfaces:** Consumes Task 10 helpers. Route `/settings/ai` renders inside the normal Shell (App Router default layout).

- [ ] **Step 1: Write the failing test** — `apps/web/components/settings/AISettings.test.tsx`:

```tsx
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AISettings } from "./AISettings";

const settings = {
  default_provider: null as string | null,
  default_model: null as string | null,
  credentials: [] as { provider: string; masked_key: string }[],
  catalog: [
    {
      provider: "anthropic",
      capabilities: ["json", "stream", "tools", "vision"],
      models: [{ id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" }],
    },
    {
      provider: "deepseek",
      capabilities: ["json", "stream", "tools"],
      models: [{ id: "deepseek-chat", label: "DeepSeek Chat" }],
    },
  ],
};

const getLLMSettings = vi.fn();
const putLLMCredential = vi.fn();
const deleteLLMCredential = vi.fn();
const putLLMDefault = vi.fn();

vi.mock("@gulp/api-client", () => ({
  getLLMSettings: (...a: unknown[]) => getLLMSettings(...a),
  putLLMCredential: (...a: unknown[]) => putLLMCredential(...a),
  deleteLLMCredential: (...a: unknown[]) => deleteLLMCredential(...a),
  putLLMDefault: (...a: unknown[]) => putLLMDefault(...a),
}));

beforeEach(() => {
  vi.clearAllMocks();
  getLLMSettings.mockResolvedValue(structuredClone(settings));
});

describe("AISettings", () => {
  it("renders a card per catalog provider", async () => {
    render(<AISettings />);
    expect(await screen.findByText("Anthropic")).toBeInTheDocument();
    expect(screen.getByText("DeepSeek")).toBeInTheDocument();
  });

  it("saves a key then refreshes", async () => {
    putLLMCredential.mockResolvedValue(undefined);
    render(<AISettings />);
    const card = (await screen.findByText("DeepSeek")).closest("section")!;
    const { getByPlaceholderText, getByRole } = within(card);
    await userEvent.type(getByPlaceholderText("API key"), "sk-x");
    await userEvent.click(getByRole("button", { name: "Save key" }));
    await waitFor(() => expect(putLLMCredential).toHaveBeenCalledWith("deepseek", "sk-x"));
    expect(getLLMSettings).toHaveBeenCalledTimes(2);
  });

  it("shows masked key + delete for configured providers", async () => {
    getLLMSettings.mockResolvedValue({
      ...structuredClone(settings),
      credentials: [{ provider: "deepseek", masked_key: "…3456" }],
    });
    render(<AISettings />);
    expect(await screen.findByText("…3456")).toBeInTheDocument();
  });

  it("saves the default provider+model", async () => {
    getLLMSettings.mockResolvedValue({
      ...structuredClone(settings),
      credentials: [{ provider: "deepseek", masked_key: "…3456" }],
    });
    putLLMDefault.mockResolvedValue(undefined);
    render(<AISettings />);
    await screen.findByText("DeepSeek");
    await userEvent.selectOptions(screen.getByLabelText("Default provider"), "deepseek");
    await userEvent.selectOptions(screen.getByLabelText("Default model"), "deepseek-chat");
    await userEvent.click(screen.getByRole("button", { name: "Save default" }));
    await waitFor(() => expect(putLLMDefault).toHaveBeenCalledWith("deepseek", "deepseek-chat"));
  });
});
```

(import `within` from `@testing-library/react`.)

- [ ] **Step 2: Run to verify failure** — `pnpm --filter @gulp/web test -- AISettings` → FAIL (module missing).

- [ ] **Step 3: Implement.** `components/settings/AISettings.tsx` (client component; labels: `PROVIDER_LABELS = { anthropic: "Anthropic", openai: "OpenAI", deepseek: "DeepSeek", qwen: "Qwen" }`):

```tsx
"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  deleteLLMCredential,
  getLLMSettings,
  putLLMCredential,
  putLLMDefault,
  type LLMSettingsOut,
} from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import styles from "./AISettings.module.css";

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  deepseek: "DeepSeek",
  qwen: "Qwen",
};

export function AISettings() {
  const [data, setData] = useState<LLMSettingsOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [defProvider, setDefProvider] = useState("");
  const [defModel, setDefModel] = useState("");

  const refresh = useCallback(async () => {
    try {
      const s = await getLLMSettings();
      setData(s);
      setDefProvider(s.default_provider ?? "");
      setDefModel(s.default_model ?? "");
    } catch {
      setError("Couldn't load AI settings.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (error) return <p className={styles.error}>{error}</p>;
  if (!data) return <p className={styles.muted}>Loading…</p>;

  const configured = new Set(data.credentials.map((c) => c.provider));
  const masked = new Map(data.credentials.map((c) => [c.provider, c.masked_key]));
  const models =
    data.catalog.find((c) => c.provider === defProvider)?.models ?? [];

  async function act(fn: () => Promise<void>, failMsg: string) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e instanceof Error && e.message === "invalid_key"
        ? "That key was rejected by the provider."
        : failMsg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.root}>
      <h1 className={styles.title}>AI models</h1>
      <p className={styles.muted}>
        Bring your own API keys. Gulp calls providers with your key and never
        shows it again after saving.
      </p>
      {data.catalog.map((p) => (
        <section key={p.provider} className={styles.card}>
          <header className={styles.cardHeader}>
            <h2>{PROVIDER_LABELS[p.provider] ?? p.provider}</h2>
            <span className={styles.caps}>{p.capabilities.join(" · ")}</span>
          </header>
          {configured.has(p.provider) ? (
            <div className={styles.row}>
              <code>{masked.get(p.provider)}</code>
              <Button
                disabled={busy}
                onClick={() =>
                  void act(
                    () => deleteLLMCredential(p.provider),
                    "Couldn't delete the key.",
                  )
                }
              >
                Delete key
              </Button>
            </div>
          ) : (
            <div className={styles.row}>
              <input
                className={styles.input}
                type="password"
                placeholder="API key"
                value={drafts[p.provider] ?? ""}
                onChange={(e) =>
                  setDrafts((d) => ({ ...d, [p.provider]: e.target.value }))
                }
              />
              <Button
                disabled={busy || !(drafts[p.provider] ?? "").trim()}
                onClick={() =>
                  void act(async () => {
                    await putLLMCredential(p.provider, drafts[p.provider].trim());
                    setDrafts((d) => ({ ...d, [p.provider]: "" }));
                  }, "Couldn't save the key.")
                }
              >
                Save key
              </Button>
            </div>
          )}
        </section>
      ))}
      <section className={styles.card}>
        <h2>Default model</h2>
        <div className={styles.row}>
          <label htmlFor="def-provider">Default provider</label>
          <select
            id="def-provider"
            value={defProvider}
            onChange={(e) => {
              setDefProvider(e.target.value);
              setDefModel("");
            }}
          >
            <option value="">—</option>
            {[...configured].map((p) => (
              <option key={p} value={p}>
                {PROVIDER_LABELS[p] ?? p}
              </option>
            ))}
          </select>
          <label htmlFor="def-model">Default model</label>
          <select
            id="def-model"
            value={defModel}
            onChange={(e) => setDefModel(e.target.value)}
          >
            <option value="">—</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
          <Button
            disabled={busy || !defProvider || !defModel}
            onClick={() =>
              void act(
                () => putLLMDefault(defProvider, defModel),
                "Couldn't save the default.",
              )
            }
          >
            Save default
          </Button>
        </div>
        {!configured.size && (
          <p className={styles.muted}>Add a key first to pick a default.</p>
        )}
      </section>
    </div>
  );
}
```

`AISettings.module.css` — follow tokens from `@gulp/ui` usage in sibling modules (simple stack: `.root{max-width:640px;margin:0 auto;display:flex;flex-direction:column;gap:16px}` etc.). `app/settings/ai/page.tsx`:

```tsx
import React from "react";
import { AISettings } from "@/components/settings/AISettings";

export const metadata = { title: "AI models — Gulp" };

export default function AISettingsPage() {
  return <AISettings />;
}
```

`AccountMenu.tsx`: add `import Link from "next/link";` and a menu entry `<Link className={styles.item} href="/settings/ai">AI models</Link>` above the logout button (add a matching `.item` style; update `AccountMenu.test.tsx` to assert the link renders).

- [ ] **Step 4: Run tests** — `pnpm --filter @gulp/web test` → PASS; `just lint` green.
- [ ] **Step 5: Commit** — `feat(web): AI models settings page (BYOK keys + default model)`

---

## Slice 3 — streaming reader chat

### Task 12: `MarkerFilter` + streaming chat service

**Files:**
- Modify: `services/api/app/services/chat.py` (add `MarkerFilter`, `answer_stream`; delete `answer_question` + `ChatAnswer`; extend `_grounding_system` with a citable-block catalog)
- Modify: `services/api/tests/test_pack_chat.py` (rework)

**Interfaces:**
- Produces: `MarkerFilter` — `feed(chunk: str) -> str` (clean text to forward), `flush() -> str`, `.text: str` (full clean text), `.refs: list[uuid.UUID]` (cited ids in order, deduped); `answer_stream(db, snapshot_id, question, block_refs=None, *, provider=None) -> AsyncIterator[dict]` yielding `{"type": "delta", "text"}`, then `{"type": "done", "message": {id, role, content, block_refs, created_at}}`, or `{"type": "error", "code"}` (codes: `llm_not_configured`, `llm_key_invalid`, `llm_rate_limited`, `llm_error`).
- Consumes: `resolve_model_config`, `get_spec`, stream events (Task 1/5).

- [ ] **Step 1: Write the failing tests** (add to `test_pack_chat.py`; keep the `_pack` fixture; the fake gains `stream_chat`):

```python
class FakeStreamProvider:
    def __init__(self, *chunks: str) -> None:
        self.chunks = chunks
        self.last_system: str | None = None

    async def complete_json(self, **kw: Any) -> dict[str, Any]:
        raise AssertionError("streaming path must not call complete_json")

    async def stream_chat(self, *, system, messages, tools, config):  # type: ignore[no-untyped-def]
        self.last_system = system
        for c in self.chunks:
            yield TextDelta(text=c)
        yield DoneEvent(stop_reason="stop")


def test_marker_filter_strips_split_markers() -> None:
    from app.services.chat import MarkerFilter

    bid = "11111111-1111-1111-1111-111111111111"
    mf = MarkerFilter()
    out = mf.feed("Attention is [[bl") + mf.feed(f"ock:{bid}]] key.") + mf.flush()
    assert out == "Attention is  key."
    assert mf.text == "Attention is  key."
    assert [str(r) for r in mf.refs] == [bid]


def test_marker_filter_passes_plain_double_brackets() -> None:
    from app.services.chat import MarkerFilter

    mf = MarkerFilter()
    out = mf.feed("a [[note]] b") + mf.flush()
    assert out == "a [[note]] b" and mf.refs == []


def test_answer_stream_persists_thread_with_refs(db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack(db)
    fake = FakeStreamProvider("The answer ", f"[[block:{ids['block']}]]", "is 42.")

    async def run() -> list[dict[str, Any]]:
        return [e async for e in answer_stream(db, ids["snap"], "Why?", provider=fake)]

    events = asyncio.run(run())
    assert events[-1]["type"] == "done"
    deltas = "".join(e["text"] for e in events if e["type"] == "delta")
    assert deltas == "The answer is 42."
    msgs = list_messages(db, ids["snap"])
    assert [m.role.value for m in msgs] == ["user", "assistant"]
    assert msgs[1].content == "The answer is 42."
    assert msgs[1].block_refs == [str(ids["block"])]
    assert events[-1]["message"]["content"] == "The answer is 42."


def test_answer_stream_drops_unknown_block_refs(db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack(db)
    fake = FakeStreamProvider("Hi [[block:99999999-9999-9999-9999-999999999999]] there.")

    async def run() -> list[dict[str, Any]]:
        return [e async for e in answer_stream(db, ids["snap"], "Q", provider=fake)]

    events = asyncio.run(run())
    msgs = list_messages(db, ids["snap"])
    assert msgs[1].block_refs == []


def test_answer_stream_system_lists_citable_blocks(db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack(db)
    fake = FakeStreamProvider("ok")
    asyncio.run(_drain(answer_stream(db, ids["snap"], "Q", provider=fake)))
    assert str(ids["block"]) in fake.last_system
    assert "[[block:" in fake.last_system  # citation instruction present


async def _drain(agen) -> None:  # type: ignore[no-untyped-def]
    async for _ in agen:
        pass
```

Also REWRITE the old `answer_question` tests to go through `answer_stream` (grounding/attached-block assertions port over: attached-block text must appear in `fake.last_system`). Delete the `register_provider`-based default-wiring test if it still exists.

- [ ] **Step 2: Run to verify failure** — FAIL (no `MarkerFilter` / `answer_stream`).

- [ ] **Step 3: Implement** in `chat.py`. Remove `ChatAnswer`, `complete_structured` import, and `answer_question`. Add:

```python
_MARKER_RE = re.compile(r"\[\[block:([0-9a-fA-F-]{36})\]\]")
_MAX_HOLDBACK = 48  # longest possible partial marker


class MarkerFilter:
    """Incrementally strip [[block:<uuid>]] citation markers from a token
    stream, collecting the cited ids. Text that merely looks like the start of
    a marker is held back until it resolves."""

    def __init__(self) -> None:
        self.refs: list[uuid.UUID] = []
        self.text = ""
        self._buf = ""

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        out: list[str] = []
        while True:
            m = _MARKER_RE.search(self._buf)
            if m:
                out.append(self._buf[: m.start()])
                ref = uuid.UUID(m.group(1))
                if ref not in self.refs:
                    self.refs.append(ref)
                self._buf = self._buf[m.end() :]
                continue
            idx = self._buf.rfind("[[")
            if idx != -1 and len(self._buf) - idx < _MAX_HOLDBACK:
                out.append(self._buf[:idx])
                self._buf = self._buf[idx:]
            else:
                out.append(self._buf)
                self._buf = ""
            break
        clean = "".join(out)
        self.text += clean
        return clean

    def flush(self) -> str:
        tail, self._buf = self._buf, ""
        self.text += tail
        return tail
```

`_grounding_system` additions (after the attached-blocks part, before the source excerpt):

```python
    citable = _pack_blocks(db, snapshot_id)
    if citable:
        listing = "\n".join(
            f"- {b.id} ({b.block_type.value}) {_block_text(b)[:80]}" for b in citable[:60]
        )
        parts.append("Blocks you may cite:\n" + listing)
        parts.append(
            "When a sentence draws on a specific block, cite it inline as "
            "[[block:<id>]] immediately after that sentence, using only ids "
            "from the list above."
        )
```

with the reusable query helper:

```python
def _pack_blocks(db: Session, snapshot_id: uuid.UUID) -> list[PackBlock]:
    return list(
        db.scalars(
            select(PackBlock)
            .join(PackSection, PackBlock.section_id == PackSection.id)
            .join(KnowledgePack, PackSection.pack_id == KnowledgePack.id)
            .where(
                PackBlock.deleted_at.is_(None),
                KnowledgePack.snapshot_id == snapshot_id,
                KnowledgePack.deleted_at.is_(None),
            )
            .order_by(PackBlock.position)
        )
    )
```

(Check `PackBlock` for the real ordering column — use whatever `pack.py` service uses; fall back to `created_at` if there is no `position`.) Then:

```python
async def answer_stream(
    db: Session,
    snapshot_id: uuid.UUID,
    question: str,
    block_refs: list[uuid.UUID] | None = None,
    *,
    provider: LLMProvider | None = None,
) -> AsyncIterator[dict[str, Any]]:
    refs = [uuid.UUID(str(r)) for r in (block_refs or [])]
    attached = _attached_blocks(db, snapshot_id, refs)
    source = db.get(Source, snapshot_id)

    user_msg = PackMessage(
        snapshot_id=snapshot_id,
        role=ChatRole.user,
        content=question,
        block_refs=[str(r) for r in refs],
    )
    db.add(user_msg)
    db.flush()

    history = list_messages(db, snapshot_id)
    messages = [ChatMessage(role=m.role.value, content=m.content) for m in history]
    system = _grounding_system(db, snapshot_id, attached)
    mf = MarkerFilter()
    try:
        cfg = ModelConfig() if provider is not None else resolve_model_config(db, source.owner_id)
        prov = provider if provider is not None else get_spec(cfg.provider).adapter
        async for ev in prov.stream_chat(system=system, messages=messages, tools=None, config=cfg):
            if isinstance(ev, TextDelta):
                clean = mf.feed(ev.text)
                if clean:
                    yield {"type": "delta", "text": clean}
        tail = mf.flush()
        if tail:
            yield {"type": "delta", "text": tail}
    except LLMNotConfiguredError:
        db.rollback()
        yield {"type": "error", "code": "llm_not_configured"}
        return
    except LLMAuthError:
        db.rollback()
        yield {"type": "error", "code": "llm_key_invalid"}
        return
    except LLMRateLimitError:
        db.rollback()
        yield {"type": "error", "code": "llm_rate_limited"}
        return
    except LLMError:
        db.rollback()
        yield {"type": "error", "code": "llm_error"}
        return

    valid = {b.id for b in _pack_blocks(db, snapshot_id)}
    assistant_msg = PackMessage(
        snapshot_id=snapshot_id,
        role=ChatRole.assistant,
        content=mf.text,
        block_refs=[str(r) for r in mf.refs if r in valid],
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    yield {
        "type": "done",
        "message": {
            "id": str(assistant_msg.id),
            "role": "assistant",
            "content": assistant_msg.content,
            "block_refs": assistant_msg.block_refs,
            "created_at": assistant_msg.created_at.isoformat(),
        },
    }
```

(new imports: `re`, `AsyncIterator` from `collections.abc`, plus `ChatMessage, LLMAuthError, LLMError, LLMNotConfiguredError, LLMRateLimitError, ModelConfig, TextDelta` from `gulp_shared.llm.base`, `get_spec` from `gulp_shared.llm.catalog`, `resolve_model_config` from `gulp_shared.llm`.)

- [ ] **Step 4: Run api suite** → PASS. **Step 5: Commit** — `feat(api): streaming chat service with inline block-citation markers`

### Task 13: SSE endpoint replaces the JSON message POST

**Files:**
- Modify: `services/api/app/routers/pack.py` (replace `post_message_route` with `stream_message_route`)
- Modify: `services/api/tests/test_pack_chat.py` or router-level test file for the endpoint (follow where existing route tests live — likely `test_pack_chat.py`)
- Regenerate: `packages/api-client/src/schema.gen.ts` (`just gen-client`); remove `postPackMessage` helper from `index.ts`; add `streamPackMessage` + `ChatStreamEvent`

**Interfaces:**
- Produces (wire): `POST /snapshots/{snapshot_id}/messages/stream` (body = existing `MessageCreate`) → `text/event-stream` of `data: <json>\n\n` frames matching Task 12 events.
- Produces (TS): `type ChatStreamEvent = {type:"delta";text:string} | {type:"done";message:MessageOut} | {type:"error";code:string}`; `async function* streamPackMessage(snapshotId: string, body: {content: string; block_refs: string[]}): AsyncGenerator<ChatStreamEvent>`.

- [ ] **Step 1: Write the failing endpoint test:**

```python
def test_stream_endpoint_emits_sse(client_with_db, db) -> None:  # type: ignore[no-untyped-def]
    # build the pack via _pack(db); monkeypatch answer_stream? No — inject via
    # provider is service-level. Route test goes end-to-end with a fake:
    # monkeypatch app.routers.pack.answer_stream with a stub async generator.
    import app.routers.pack as pack_router

    async def fake_stream(db_, snap_id, content, refs):  # type: ignore[no-untyped-def]
        yield {"type": "delta", "text": "hi"}
        yield {"type": "done", "message": {"id": "x", "role": "assistant", "content": "hi", "block_refs": [], "created_at": "2026-07-13T00:00:00"}}

    ...
```

Concretely (final form):

```python
def test_stream_endpoint_emits_sse(db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import app.routers.pack as pack_router
    from app.deps import get_db
    from app.main import app
    from fastapi.testclient import TestClient

    ids = _pack(db)

    def fake_answer_stream(db_, snapshot_id, content, block_refs):  # type: ignore[no-untyped-def]
        async def gen():
            yield {"type": "delta", "text": "hi"}
            yield {"type": "done", "message": {"id": "x", "role": "assistant", "content": "hi", "block_refs": [], "created_at": "t"}}

        return gen()

    monkeypatch.setattr(pack_router, "answer_stream", fake_answer_stream)
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            with client.stream(
                "POST", f"/snapshots/{ids['snap']}/messages/stream", json={"content": "q"}
            ) as r:
                assert r.status_code == 200
                assert r.headers["content-type"].startswith("text/event-stream")
                frames = [line for line in r.iter_lines() if line.startswith("data: ")]
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert '"type": "delta"' in frames[0] and '"type": "done"' in frames[1]


def test_old_json_post_is_gone(db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.deps import get_db
    from app.main import app
    from fastapi.testclient import TestClient

    ids = _pack(db)
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            assert client.post(f"/snapshots/{ids['snap']}/messages", json={"content": "q"}).status_code == 405
    finally:
        app.dependency_overrides.pop(get_db, None)
```

- [ ] **Step 2: Run to verify failure** — 404 on `/messages/stream`.

- [ ] **Step 3: Implement** in `routers/pack.py` — delete `post_message_route`, add:

```python
@router.post("/snapshots/{snapshot_id}/messages/stream")
async def stream_message_route(
    snapshot_id: uuid.UUID,
    body: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    _owned_snapshot(db, snapshot_id, user)

    async def gen() -> AsyncIterator[str]:
        async for ev in answer_stream(db, snapshot_id, body.content, body.block_refs):
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

(imports: `json`, `AsyncIterator`, `StreamingResponse` from `fastapi.responses`, `answer_stream` replaces `answer_question`.) Then `just gen-client`; in `packages/api-client/src/index.ts` remove `postPackMessage` (keep `MessageOut` type — still derived from the GET) and add:

```ts
export type ChatStreamEvent =
  | { type: "delta"; text: string }
  | { type: "done"; message: MessageOut }
  | { type: "error"; code: string };

// SSE is outside the OpenAPI surface; hand-rolled on purpose.
export async function* streamPackMessage(
  snapshotId: string,
  body: { content: string; block_refs: string[] },
): AsyncGenerator<ChatStreamEvent> {
  const res = await fetch(`${baseUrl}/snapshots/${snapshotId}/messages/stream`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error("chat stream failed");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (line) yield JSON.parse(line.slice(6)) as ChatStreamEvent;
    }
  }
}
```

- [ ] **Step 4: Run api suite + web/api-client type check** → PASS (web build will fail if anything still imports `postPackMessage` — Task 14 fixes ChatPanel; if the web test suite breaks here, fold the minimal ChatPanel compile fix forward and note it in the Task 14 commit instead — otherwise do Tasks 13+14 as one commit).
- [ ] **Step 5: Commit** — `feat(api): SSE streaming chat endpoint (replaces JSON message POST)` (or combined with Task 14 — see Step 4).

### Task 14: ChatPanel streams incrementally

**Files:**
- Modify: `apps/web/components/snapshot/ChatPanel.tsx`, `apps/web/components/snapshot/ChatPanel.test.tsx`

**Interfaces:** Consumes `streamPackMessage`/`ChatStreamEvent` (Task 13). Error copy: `llm_not_configured` → "Add an AI provider key in Settings → AI models first."; `llm_key_invalid` → "Your AI key was rejected — check Settings → AI models."; `llm_rate_limited` → "The provider rate-limited this key — try again shortly."; other → "Couldn't send — try again."

- [ ] **Step 1: Update the tests** — replace `postPackMessage` mocks with a `streamPackMessage` async-generator mock:

```tsx
const streamPackMessage = vi.fn();
vi.mock("@gulp/api-client", () => ({
  getPackMessages: (...a: unknown[]) => getPackMessages(...a),
  streamPackMessage: (...a: unknown[]) => streamPackMessage(...a),
}));

function stream(events: unknown[]) {
  return (async function* () {
    for (const e of events) yield e;
  })();
}

it("renders deltas incrementally then the final message", async () => {
  getPackMessages.mockResolvedValue([]);
  streamPackMessage.mockReturnValue(
    stream([
      { type: "delta", text: "Hel" },
      { type: "delta", text: "lo" },
      { type: "done", message: { id: "m1", role: "assistant", content: "Hello", block_refs: [], created_at: "t" } },
    ]),
  );
  // render, type into the textarea, click send; then:
  expect(await screen.findByText("Hello")).toBeInTheDocument();
  expect(streamPackMessage).toHaveBeenCalledWith("snap-1", { content: "hi", block_refs: [] });
});

it("surfaces llm_not_configured with settings pointer", async () => {
  getPackMessages.mockResolvedValue([]);
  streamPackMessage.mockReturnValue(stream([{ type: "error", code: "llm_not_configured" }]));
  // send; then:
  expect(await screen.findByText(/Settings → AI models/)).toBeInTheDocument();
});
```

(Adapt render/act details to the existing test file's helpers — keep its patterns.)

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement** — in `ChatPanel.tsx` replace the `postPackMessage` import with `streamPackMessage, type ChatStreamEvent`; add `const [streamText, setStreamText] = useState<string | null>(null);` and rework `send()`:

```tsx
const ERROR_COPY: Record<string, string> = {
  llm_not_configured: "Add an AI provider key in Settings → AI models first.",
  llm_key_invalid: "Your AI key was rejected — check Settings → AI models.",
  llm_rate_limited: "The provider rate-limited this key — try again shortly.",
};

async function send() {
  const q = draft.trim();
  if (!q || sending) return;
  const refs = attachments.map((a) => a.id);
  setError(null);
  setSending(true);
  setDraft("");
  const optimistic: MessageOut = {
    id: `tmp-${tmpIdRef.current++}`,
    role: "user",
    content: q,
    block_refs: refs,
    created_at: "",
  };
  setMessages((m) => [...m, optimistic]);
  let failed: string | null = null;
  try {
    setStreamText("");
    let acc = "";
    for await (const ev of streamPackMessage(snapshotId, { content: q, block_refs: refs })) {
      if (ev.type === "delta") {
        acc += ev.text;
        setStreamText(acc);
      } else if (ev.type === "done") {
        setMessages((m) => [...m, ev.message]);
      } else {
        failed = ERROR_COPY[ev.code] ?? "Couldn't send — try again.";
      }
    }
  } catch {
    failed = "Couldn't send — try again.";
  } finally {
    setStreamText(null);
    setSending(false);
  }
  if (failed) {
    setMessages((m) => m.filter((x) => x.id !== optimistic.id));
    setDraft(q);
    setError(failed);
  }
}
```

and render the in-flight bubble in the message list (reuse the assistant-message styles):

```tsx
{streamText !== null && streamText !== "" && (
  <div className={styles.assistant} aria-live="polite">
    {streamText}
  </div>
)}
```

(match the actual class/structure used for assistant messages in the existing JSX.)

- [ ] **Step 4: Run web suite + `just lint`** → PASS. Manual check (optional, needs running stack + a real key): send a chat message in the reader; text arrives incrementally.
- [ ] **Step 5: Commit** — `feat(web): reader chat renders the answer as it streams`

---

## Slice 4 — tool loop mechanism

### Task 15: `run_tool_loop`

**Files:**
- Create: `services/shared/gulp_shared/llm/loop.py`
- Modify: `services/shared/gulp_shared/llm/__init__.py` (export)
- Create: `services/shared/tests/test_llm_loop.py`

**Interfaces (produced):** `ToolExecutor = Callable[[ToolCall], Awaitable[str]]`; `run_tool_loop(*, system, messages, tools, executor, config, provider=None, max_iters=8) -> AsyncIterator[StreamEvent]` — forwards `TextDelta`/`ToolCallEvent`/`UsageEvent`, swallows per-round `DoneEvent`s, appends assistant/tool turns to the conversation, re-calls until no tool calls or `max_iters` (then `DoneEvent(stop_reason="max_iters")`).

- [ ] **Step 1: Write the failing test** — `services/shared/tests/test_llm_loop.py`:

```python
"""Tool loop: execute calls, feed results back, stop on plain answer / max_iters."""

from typing import Any

from gulp_shared.llm.base import (
    ChatMessage,
    DoneEvent,
    ModelConfig,
    TextDelta,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
)
from gulp_shared.llm.loop import run_tool_loop

CFG = ModelConfig(provider="anthropic", api_key="sk-test")
TOOLS = [ToolSpec(name="search", description="d", input_schema={"type": "object"})]


class ScriptedProvider:
    """Each round yields the next scripted event list; records the convo."""

    def __init__(self, rounds: list[list[Any]]) -> None:
        self.rounds = rounds
        self.seen: list[list[ChatMessage]] = []

    async def complete_json(self, **kw: Any) -> dict[str, Any]:
        raise AssertionError("loop must stream")

    async def stream_chat(self, *, system, messages, tools, config):  # type: ignore[no-untyped-def]
        self.seen.append(list(messages))
        for ev in self.rounds[len(self.seen) - 1]:
            yield ev


async def test_loop_executes_tools_then_finishes() -> None:
    call = ToolCall(id="c1", name="search", arguments={"q": "x"})
    prov = ScriptedProvider(
        [
            [ToolCallEvent(tool_call=call), DoneEvent(stop_reason="tool_use")],
            [TextDelta(text="answer"), DoneEvent(stop_reason="stop")],
        ]
    )
    executed: list[ToolCall] = []

    async def executor(c: ToolCall) -> str:
        executed.append(c)
        return "result-1"

    events = [
        e
        async for e in run_tool_loop(
            system="s",
            messages=[ChatMessage(role="user", content="q")],
            tools=TOOLS,
            executor=executor,
            config=CFG,
            provider=prov,
        )
    ]
    assert executed == [call]
    assert [e.type for e in events] == ["tool_call", "text_delta", "done"]
    assert events[-1].stop_reason == "stop"
    # round 2 saw: user, assistant(tool_calls), tool(result)
    round2 = prov.seen[1]
    assert round2[1].tool_calls == [call]
    assert round2[2].role == "tool" and round2[2].content == "result-1"
    assert round2[2].tool_call_id == "c1"


async def test_loop_stops_at_max_iters() -> None:
    call = ToolCall(id="c1", name="search", arguments={})
    prov = ScriptedProvider(
        [[ToolCallEvent(tool_call=call), DoneEvent(stop_reason="tool_use")]] * 3
    )

    async def executor(c: ToolCall) -> str:
        return "r"

    events = [
        e
        async for e in run_tool_loop(
            system=None,
            messages=[ChatMessage(role="user", content="q")],
            tools=TOOLS,
            executor=executor,
            config=CFG,
            provider=prov,
            max_iters=3,
        )
    ]
    assert events[-1] == DoneEvent(stop_reason="max_iters")
    assert len(prov.seen) == 3
```

- [ ] **Step 2: Run to verify failure** — no module `loop`.

- [ ] **Step 3: Implement** `services/shared/gulp_shared/llm/loop.py`:

```python
"""Provider-agnostic tool-use loop (spec 2026-07-13 §3.6). Pure logic: streams
each model turn, executes requested tools, feeds results back, and stops when
the model answers without tools or `max_iters` is exhausted."""

from collections.abc import AsyncIterator, Awaitable, Callable

from gulp_shared.llm.base import (
    ChatMessage,
    DoneEvent,
    LLMProvider,
    ModelConfig,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
)
from gulp_shared.llm.catalog import get_spec

ToolExecutor = Callable[[ToolCall], Awaitable[str]]


async def run_tool_loop(
    *,
    system: str | None,
    messages: list[ChatMessage],
    tools: list[ToolSpec],
    executor: ToolExecutor,
    config: ModelConfig,
    provider: LLMProvider | None = None,
    max_iters: int = 8,
) -> AsyncIterator[StreamEvent]:
    prov = provider if provider is not None else get_spec(config.provider).adapter
    convo = list(messages)
    for _ in range(max_iters):
        calls: list[ToolCall] = []
        text_parts: list[str] = []
        stop = "stop"
        async for ev in prov.stream_chat(system=system, messages=convo, tools=tools, config=config):
            if isinstance(ev, TextDelta):
                text_parts.append(ev.text)
                yield ev
            elif isinstance(ev, ToolCallEvent):
                calls.append(ev.tool_call)
                yield ev
            elif isinstance(ev, DoneEvent):
                stop = ev.stop_reason  # forwarded only when the loop ends
            else:
                yield ev
        if not calls:
            yield DoneEvent(stop_reason=stop)
            return
        convo.append(ChatMessage(role="assistant", content="".join(text_parts), tool_calls=calls))
        for call in calls:
            result = await executor(call)
            convo.append(ChatMessage(role="tool", content=result, tool_call_id=call.id))
    yield DoneEvent(stop_reason="max_iters")
```

Export `run_tool_loop` (and `ToolExecutor`) from `gulp_shared/llm/__init__.py`.

- [ ] **Step 4: Run all suites** → PASS. **Step 5: Commit** — `feat(llm): provider-agnostic tool-use loop`

---

## Final verification (before declaring done)

- [ ] `just lint` — green.
- [ ] `uv run pytest services/shared services/api` and `cd services/worker && uv run --package gulp-worker pytest` — green.
- [ ] `pnpm turbo run test` — green.
- [ ] `pnpm --filter @gulp/web exec tsc --noEmit` / `--filter @gulp/api-client` — only the 2 known `schema.gen.ts` dup errors.
- [ ] Spec coverage sweep: §3 contract ✓ (T1-4), §3.6 loop ✓ (T15), §4 BYOK ✓ (T6-11), §5.1 resolve ✓ (T5, T8), §5.2 streaming chat ✓ (T12-14), §5.3 worker ✓ (T5), §6 errors ✓ (T1, T5, T9, T12), §7 tests ✓ (each task), §8 slices ✓.
- [ ] Update memory + suggest merge/PR next steps (finishing-a-development-branch skill).
