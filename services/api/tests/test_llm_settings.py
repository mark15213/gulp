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
    r = client.put("/me/llm/default", json={"provider": "deepseek", "model": "deepseek-chat"})
    assert r.status_code == 409
    client.put("/me/llm/credentials/deepseek", json={"api_key": "sk-abcdef123456"})
    r = client.put("/me/llm/default", json={"provider": "deepseek", "model": "gpt-4.1"})
    assert r.status_code == 422
    r = client.put("/me/llm/default", json={"provider": "deepseek", "model": "deepseek-chat"})
    assert r.status_code == 204
    body = client.get("/me/llm").json()
    assert (body["default_provider"], body["default_model"]) == ("deepseek", "deepseek-chat")


def test_delete_credential_clears_matching_default(client, ping_ok) -> None:  # type: ignore[no-untyped-def]
    client.put("/me/llm/credentials/deepseek", json={"api_key": "sk-abcdef123456"})
    client.put("/me/llm/default", json={"provider": "deepseek", "model": "deepseek-chat"})
    assert client.delete("/me/llm/credentials/deepseek").status_code == 204
    body = client.get("/me/llm").json()
    assert body["credentials"] == [] and body["default_provider"] is None
    assert client.delete("/me/llm/credentials/deepseek").status_code == 404
