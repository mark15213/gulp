"""CardsPayload contract — both supplies validate against this one schema."""

import pytest
from gulp_shared.contracts.cards import CardDraft, CardsPayload
from pydantic import ValidationError


def _draft(**overrides):
    base = {
        "card_type": "short_answer",
        "prompt": "What does BERT stand for?",
        "answer": "Bidirectional Encoder Representations from Transformers",
        "explanation": "Stated in the abstract.",
    }
    base.update(overrides)
    return base


def test_valid_mixed_payload_round_trips():
    payload = CardsPayload.model_validate(
        {
            "cards": [
                _draft(),
                _draft(
                    card_type="mcq",
                    prompt="Which objective does BERT pre-train with?",
                    answer="Masked LM",
                    options=["Masked LM", "Causal LM", "Translation"],
                ),
                _draft(
                    card_type="cloze",
                    prompt="BERT uses a ____ encoder.",
                    answer="bidirectional",
                ),
                _draft(card_type="explain", answer=None),
            ]
        }
    )
    assert len(payload.cards) == 4
    assert payload.cards[1].options == ["Masked LM", "Causal LM", "Translation"]


def test_mcq_requires_options():
    with pytest.raises(ValidationError, match="options"):
        CardDraft.model_validate(_draft(card_type="mcq"))


def test_mcq_options_bounds():
    with pytest.raises(ValidationError):
        CardDraft.model_validate(
            _draft(card_type="mcq", answer="A", options=["A", "B"])  # < 3
        )
    with pytest.raises(ValidationError):
        CardDraft.model_validate(
            _draft(card_type="mcq", answer="A", options=list("ABCDEFG"))  # > 6
        )


def test_mcq_answer_must_be_an_option():
    with pytest.raises(ValidationError, match="answer"):
        CardDraft.model_validate(
            _draft(card_type="mcq", answer="not there", options=["A", "B", "C"])
        )


def test_non_mcq_must_not_carry_options():
    with pytest.raises(ValidationError, match="options"):
        CardDraft.model_validate(_draft(options=["A", "B", "C"]))


def test_cloze_prompt_must_contain_blank():
    with pytest.raises(ValidationError, match="____"):
        CardDraft.model_validate(_draft(card_type="cloze", prompt="No blank here."))


def test_short_answer_requires_answer():
    with pytest.raises(ValidationError, match="answer"):
        CardDraft.model_validate(_draft(answer=None))


def test_free_response_types_allow_missing_answer():
    for card_type in ("explain", "apply", "recall"):
        draft = CardDraft.model_validate(_draft(card_type=card_type, answer=None))
        assert draft.answer is None


def test_prompt_must_be_non_empty():
    with pytest.raises(ValidationError):
        CardDraft.model_validate(_draft(prompt="   "))


def test_payload_bounds():
    with pytest.raises(ValidationError):
        CardsPayload.model_validate({"cards": []})
    with pytest.raises(ValidationError):
        CardsPayload.model_validate({"cards": [_draft()] * 101})


def test_json_schema_is_exportable():
    schema = CardsPayload.model_json_schema()
    assert "cards" in schema["properties"]
