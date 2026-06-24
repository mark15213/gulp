# services/worker — async AI pipeline

Where the heavy, slow, AI work runs so the API never blocks (docs/04 S1/S2). Queue-fed by the API.

## Layout

- `app/pipeline/` — the S2 stages: fetch → parse → chunk → generate pack → draft cards → link concepts.
- `app/prompts/` — LLM prompt templates (kept out of code).
- `app/llm/` — model/provider clients.
- `app/tasks/` — arq job definitions; `app/tasks/__main__.py` boots the worker.
- `app/eval/` — card-quality eval harness (an open S2 question, docs/04 §4).
- Persistence is shared: read/write the `gulp_shared` models, don't redefine them.

## Commands

- `just worker` — boot the worker
- `uv run pytest` (via `just test`)
