"""Generated archive text — reuses the inline digest prompt (one source of truth)."""

from typing import Any

from gulp_shared.contracts.cards import CardsPayload

from app.pipeline.schemas import PaperReport
from app.prompts.digest import _SYSTEM


def pack_schema() -> dict[str, Any]:
    return PaperReport.model_json_schema()


def cards_schema() -> dict[str, Any]:
    """The cards.json import contract — shipped so external card authoring has it at hand."""
    return CardsPayload.model_json_schema()


def prompt_md() -> str:
    return _SYSTEM + "\n"


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
