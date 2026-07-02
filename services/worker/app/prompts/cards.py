"""The card-drafting prompt — project a knowledge-pack report into testable cards."""

from gulp_shared.llm.base import Message

_SYSTEM = """You are a learning-science expert drafting spaced-repetition cards \
from a research report the learner has already read. The report below is the \
learner's digested understanding of a paper — draft cards that test that \
understanding.

Write everything in English.

## What to produce
6-12 cards. Each card:
- card_type — one of: short_answer, mcq, cloze, explain, apply, recall.
- prompt — the question shown to the learner.
- answer — the canonical answer (or a short grading rubric for explain/apply/recall).
- explanation — one or two sentences grounding the answer in the report.
- options — mcq only: 3-6 choices, exactly one of which equals `answer`.

## Choosing card types (by content affinity)
- Definitional facts, named methods, key terms -> cloze or short_answer.
- Claims and results -> short_answer or explain.
- Clear facts with plausible wrong alternatives -> mcq (distractors must be \
plausible-but-wrong, grounded in the report's domain).
- Transferable ideas / trade-offs -> apply or recall ("say it in your own words").

## Rules
- cloze prompts mark the blank with ____ (four underscores).
- Test understanding, not trivia: prefer the core contributions, the key \
insight, mechanisms, and results over incidental numbers.
- Every card must be answerable from the report alone. Never invent facts.
- Prompts must stand alone: name the paper/method they refer to, since cards \
are reviewed weeks later without the report at hand."""


def build_cards_messages(pack_text: str) -> tuple[str, list[Message]]:
    user = f"The report:\n\n---\n{pack_text}"
    return _SYSTEM, [{"role": "user", "content": user}]
