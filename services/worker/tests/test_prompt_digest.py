from app.pipeline.normdoc import Anchor, NormBlock, NormDoc
from app.prompts.digest import build_digest_messages


def _doc() -> NormDoc:
    body = "Attention weighs tokens by relevance."
    return NormDoc(
        title="Attention",
        lang="en",
        media_type="article",
        content_body=body,
        blocks=[NormBlock(text=body, anchor=Anchor(start=0, end=len(body)))],
    )


def test_system_prompt_states_the_rules() -> None:
    system, _ = build_digest_messages(_doc(), "Attention weighs tokens by relevance.")
    low = system.lower()
    assert "english" in low
    assert "report" in low
    assert "faithful" in low or "do not invent" in low or "never invent" in low
    # facet vocabulary is described
    for t in ("key_term", "person_org", "claim", "counter_view", "connection"):
        assert t in system
    assert "confidence" in low


def test_user_message_carries_title_media_type_and_body() -> None:
    _, messages = build_digest_messages(_doc(), "BODY-CONTENT-HERE")
    assert len(messages) == 1 and messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert "Attention" in content        # title
    assert "article" in content          # media_type hint
    assert "BODY-CONTENT-HERE" in content  # the body we passed (not normdoc.content_body)
