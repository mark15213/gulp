from typing import Any

from app.pipeline.digest import MAX_DIGEST_CHARS, run_digest
from app.pipeline.normdoc import Anchor, NormBlock, NormDoc
from app.pipeline.schemas import PaperReport
from gulp_shared.llm.base import ChatMessage, ModelConfig


class FakeProvider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.last_body: str | None = None

    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]:
        self.last_body = messages[0].content
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
    "title": "T",
    "core_contributions": ["c1"],
    "key_insight": "k",
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "references": [],
}


async def test_run_digest_returns_validated_result() -> None:
    prov = FakeProvider(_PAYLOAD)
    out = await run_digest(_doc("short body"), provider=prov)
    assert isinstance(out, PaperReport)
    assert out.title == "T" and out.core_contributions == ["c1"]
    assert prov.last_body is not None and "short body" in prov.last_body  # not truncated


async def test_over_budget_content_is_truncated() -> None:
    prov = FakeProvider(_PAYLOAD)
    big = "x" * (MAX_DIGEST_CHARS + 500)
    out = await run_digest(_doc(big), provider=prov)
    assert prov.last_body is not None and len(prov.last_body) <= MAX_DIGEST_CHARS + 100
    assert big[:MAX_DIGEST_CHARS] in prov.last_body  # truncated body was sent
    assert isinstance(out, PaperReport)
