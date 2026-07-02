"""CardsPayload — the single card contract for both supplies.

The worker's generation turn emits it (structured output) and the API's import
endpoint validates it (spec: docs/superpowers/specs/
2026-07-02-card-generation-and-import-design.md §①). Kept in gulp_shared so
neither side redefines the shape.
"""

from pydantic import BaseModel, Field, field_validator, model_validator

from gulp_shared.models.card import CardType

MCQ_MIN_OPTIONS = 3
MCQ_MAX_OPTIONS = 6
MAX_CARDS_PER_PAYLOAD = 100


class CardDraft(BaseModel):
    card_type: CardType
    prompt: str = Field(min_length=1)
    answer: str | None = None
    explanation: str | None = None
    options: list[str] | None = None

    @field_validator("prompt")
    @classmethod
    def _prompt_non_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("prompt must not be blank")
        return v

    @model_validator(mode="after")
    def _per_type_rules(self) -> "CardDraft":
        if self.card_type is CardType.mcq:
            if not self.options or not (
                MCQ_MIN_OPTIONS <= len(self.options) <= MCQ_MAX_OPTIONS
            ):
                raise ValueError(
                    f"mcq requires options ({MCQ_MIN_OPTIONS}-{MCQ_MAX_OPTIONS} entries)"
                )
            if self.answer not in self.options:
                raise ValueError("mcq answer must be one of the options")
        elif self.options is not None:
            raise ValueError(f"options are mcq-only, not for {self.card_type.value}")
        if self.card_type is CardType.cloze and "____" not in self.prompt:
            raise ValueError("cloze prompt must contain a ____ blank")
        if self.card_type is CardType.flashcard and not (self.answer or "").strip():
            raise ValueError("flashcard requires an answer (the back)")
        return self


class CardsPayload(BaseModel):
    cards: list[CardDraft] = Field(min_length=1, max_length=MAX_CARDS_PER_PAYLOAD)
