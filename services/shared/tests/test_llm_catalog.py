"""Provider catalog: four providers, two adapters, capability gating."""

import pytest
from gulp_shared.llm.anthropic_provider import AnthropicProvider
from gulp_shared.llm.base import (
    ChatMessage,
    ImagePart,
    LLMCapabilityError,
    LLMError,
    TextPart,
    ToolSpec,
)
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
    img_msg = [
        ChatMessage(
            role="user",
            content=[TextPart(text="?"), ImagePart(media_type="image/png", data_b64="aGk=")],
        )
    ]
    with pytest.raises(LLMCapabilityError):
        check_capabilities(get_spec("deepseek"), img_msg, None)
    check_capabilities(get_spec("qwen"), img_msg, None)  # vision-capable: no raise


def test_capability_gate_allows_tools_everywhere() -> None:
    tools = [ToolSpec(name="t", description="d", input_schema={"type": "object"})]
    for spec in PROVIDERS.values():
        check_capabilities(spec, [ChatMessage(role="user", content="hi")], tools)
