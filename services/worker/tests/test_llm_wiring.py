import gulp_shared.llm as llm
from gulp_shared.llm import AnthropicProvider, get_provider
from gulp_shared.settings import settings


def test_anthropic_is_registered_by_default() -> None:
    assert isinstance(get_provider("anthropic"), AnthropicProvider)


def test_public_surface_is_exported() -> None:
    for name in ("complete_structured", "ModelConfig", "LLMError", "get_provider"):
        assert hasattr(llm, name)


def test_settings_have_llm_defaults() -> None:
    assert settings.llm_provider == "anthropic"
    assert settings.llm_model == "claude-sonnet-4-6"
