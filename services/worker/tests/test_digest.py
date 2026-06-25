from typing import Any

from app.llm.base import Message, ModelConfig
from app.pipeline.digest import MAX_DIGEST_CHARS, run_digest
from app.pipeline.normdoc import Anchor, NormBlock, NormDoc
from app.pipeline.schemas import DigestResult


class FakeProvider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.last_body: str | None = None

    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[Message],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]:
        self.last_body = messages[0]["content"]
        return self.payload


def _doc(body: str) -> NormDoc:
    return NormDoc(
        title="T",
        lang="en",
        media_type="article",
        content_body=body,
        blocks=[NormBlock(text=body, anchor=Anchor(start=0, end=len(body)))],
    )


_PAYLOAD = {
    "summary": "s",
    "background": None,
    "confidence": 0.9,
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "facets": [{"element_type": "claim", "text": "x"}],
}


async def test_run_digest_returns_validated_result() -> None:
    prov = FakeProvider(_PAYLOAD)
    out = await run_digest(_doc("short body"), provider=prov)
    assert isinstance(out, DigestResult)
    assert out.summary == "s" and out.confidence == 0.9
    assert "short body" in prov.last_body  # not truncated


async def test_over_budget_content_is_truncated_and_confidence_clamped() -> None:
    prov = FakeProvider(_PAYLOAD)  # provider reports confidence 0.9
    big = "x" * (MAX_DIGEST_CHARS + 500)
    out = await run_digest(_doc(big), provider=prov)
    assert prov.last_body is not None and len(prov.last_body) <= MAX_DIGEST_CHARS + 100
    assert big[:MAX_DIGEST_CHARS] in prov.last_body  # truncated body was sent
    assert out.confidence == 0.5  # clamped down because we dropped content
