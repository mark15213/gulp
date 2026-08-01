"""Normalise the API's OpenAPI document for swift-openapi-generator.

FastAPI emits an optional field as an OpenAPI 3.1 union with the null type::

    "answer": {"anyOf": [{"type": "string"}, {"type": "null"}]}

swift-openapi-generator (1.13) does not support ``type: "null"`` and responds by
dropping the **whole property**, silently. On this API that loses 73 fields,
34 of them required — including ``SessionCardOut.answer`` and
``.explanation``, which the session's reveal screen is built on, and the entire
body of ``GET /gulp/sessions/current``.

So before generating, rewrite every ``anyOf`` that contains the null type down
to its non-null branch, and drop the property from its parent's ``required``
list. A field that could be null becomes a Swift optional — the same meaning,
in a shape the generator understands.

The result is written next to the Swift package and committed, exactly like the
generated sources. Run via ``just gen-client-swift``; never hand-edit the output.

One case this cannot express: a *response body* that is nullable
(``GET /gulp/sessions/current`` returns ``SessionOut | None``). OpenAPI has no
"optional body", so the body normalises to ``SessionOut`` and the client has to
treat a literal ``null`` payload as "no session" — see ``Net/Sessions.swift``.
Making that endpoint answer 204 would remove the wart for every typed client.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

NULL_SCHEMA = {"type": "null"}


def _strip_null(node: dict[str, Any]) -> bool:
    """Collapse ``anyOf``/``oneOf`` unions containing the null type.

    Returns True when this node was nullable, so the caller can relax
    ``required``.
    """
    was_nullable = False
    for key in ("anyOf", "oneOf"):
        branches = node.get(key)
        if not isinstance(branches, list):
            continue
        kept = [b for b in branches if b != NULL_SCHEMA]
        if len(kept) == len(branches):
            continue
        was_nullable = True
        del node[key]
        if len(kept) == 1:
            only = kept[0]
            if "$ref" in only:
                # A $ref alongside siblings confuses the generator; the ref
                # alone carries everything a client needs.
                node.clear()
                node["$ref"] = only["$ref"]
            else:
                for k, v in only.items():
                    node.setdefault(k, v)
        elif kept:
            node[key] = kept
    return was_nullable


def _walk(node: Any) -> None:
    if isinstance(node, list):
        for item in node:
            _walk(item)
        return
    if not isinstance(node, dict):
        return

    properties = node.get("properties")
    if isinstance(properties, dict):
        required = node.get("required")
        for name, schema in properties.items():
            if isinstance(schema, dict) and _strip_null(schema):
                if isinstance(required, list) and name in required:
                    required.remove(name)
        if isinstance(required, list) and not required:
            node.pop("required", None)

    _strip_null(node)

    for value in node.values():
        _walk(value)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: openapi_for_swift.py <source.json> <dest.json>", file=sys.stderr)
        return 2
    source, dest = Path(sys.argv[1]), Path(sys.argv[2])
    document = json.loads(source.read_text())
    _walk(document)
    dest.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    print(f"normalised {source} -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
