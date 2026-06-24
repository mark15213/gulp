"""Dump the API's OpenAPI schema to stdout.

`just gen-client` pipes this into packages/api-client to regenerate the TS
types — the cross-language contract flow (docs/05 §4)."""

import json

from app.main import app

if __name__ == "__main__":
    print(json.dumps(app.openapi()))
