"""Parse + validate an uploaded result archive into a DigestResult."""

import json

from app.export.archive import find_entry, read_zip
from app.pipeline.schemas import DigestResult


def import_result_archive(data: bytes) -> DigestResult:
    files = read_zip(data)
    try:
        raw = find_entry(files, "result/pack.json")
    except KeyError as exc:
        raise ValueError("archive has no result/pack.json") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("result/pack.json is not valid JSON") from exc
    return DigestResult.model_validate(payload)
