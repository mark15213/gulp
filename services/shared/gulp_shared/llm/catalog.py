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
