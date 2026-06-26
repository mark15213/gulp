"""Generated archive text — reuses the inline digest prompt (one source of truth)."""

from typing import Any

from app.pipeline.schemas import DigestResult
from app.prompts.digest import _SYSTEM


def pack_schema() -> dict[str, Any]:
    return DigestResult.model_json_schema()


def claude_md() -> str:
    return f"""# Gulp digest job (offline executor)

You are executing one Gulp **digest** job offline — the same task Gulp normally
runs against the Anthropic API. Read `input/norm_doc.json` (a `NormDoc`: title +
`content_body` + structured `blocks`) and write the result as JSON to
`result/pack.json`, matching `schema/pack.schema.json` exactly.

{_SYSTEM}

## Files
- Input:  `input/norm_doc.json`
- Schema: `schema/pack.schema.json`  (your output must validate against this)
- Output: `result/pack.json`         (write your Knowledge Pack here)

When done, validate `result/pack.json` against the schema, then stop. Re-zip this
folder and upload it back into Gulp.
"""


def readme_md() -> str:
    return """# Run this Gulp job in Claude Code

1. `cd` into this folder and launch Claude Code.
2. Say: "Do the Gulp digest job described in CLAUDE.md."
3. When `result/pack.json` is written, re-zip this folder and upload it in Gulp
   (the **Upload result** button on this snapshot).

No API key or network is needed — Claude Code does the reasoning itself.
"""
