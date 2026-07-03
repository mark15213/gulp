"""Generated archive text — reuses the inline prompts (one source of truth)."""

from typing import Any

from gulp_shared.contracts.cards import CardsPayload

from app.pipeline.schemas import PaperReport
from app.prompts.cards import _SYSTEM as _CARDS_SYSTEM
from app.prompts.digest import _SYSTEM


def pack_schema() -> dict[str, Any]:
    return PaperReport.model_json_schema()


def cards_schema() -> dict[str, Any]:
    """The cards.json import contract — shipped so external card authoring has it at hand."""
    return CardsPayload.model_json_schema()


def prompt_md() -> str:
    return _SYSTEM + "\n"


def cards_prompt_md() -> str:
    return _CARDS_SYSTEM + "\n"


def claude_md() -> str:
    return """# Gulp paper-digest job

Turn a captured paper into a structured, technically deep research report,
written as JSON to `result/pack.json` and validating against
`schema/pack.schema.json`.

## How to run this job
1. Read `input/norm_doc.json` (a NormDoc: `title`, `content_body`, `blocks`).
2. Author the report by following `prompt.md` exactly.
3. Write the result to `result/pack.json`.
4. Validate `result/pack.json` against `schema/pack.schema.json`. Fix until it
   validates, then stop.

## Files
- Input:        `input/norm_doc.json`
- Instructions: `prompt.md`                (how to write the report)
- Schema:       `schema/pack.schema.json`  (output MUST validate against this)
- Output:       `result/pack.json`

When done, re-zip this folder and upload it back into Gulp.
"""


def cards_claude_md() -> str:
    return """# Gulp card-generation job

Design spaced-repetition cards that will best help THIS learner master the
knowledge pack, written as JSON to `result/cards.json` and validating against
`schema/cards.schema.json`.

## How to run this job
1. Read `input/pack.md` (the digested knowledge) and, if present,
   `input/conversation.md` (the learner's questions while reading — weight
   what confused or interested them).
2. Follow `prompt.md` exactly: first reason a short curriculum for this
   learner (your private thinking), then author the cards.
3. Write ONLY the cards to `result/cards.json` as `{"cards": [...]}`.
4. Validate `result/cards.json` against `schema/cards.schema.json`. Fix until
   it validates, then stop.

## Files
- Input:        `input/pack.md` (+ `input/conversation.md` if present)
- Instructions: `prompt.md`                 (how to design + write the cards)
- Schema:       `schema/cards.schema.json`  (output MUST validate against this)
- Output:       `result/cards.json`

When done, open `result/cards.json` and paste its contents into Gulp's
"Import cards" dialog.
"""
