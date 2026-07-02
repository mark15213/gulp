"""The job manifest — identity + integrity for a job/result archive."""

import json
from typing import Any

FORMAT_VERSION = 1
_REQUIRED = ("format_version", "job_kind", "snapshot_id", "owner_id")


def build_manifest(
    *, snapshot_id: str, owner_id: str, input_sha256: str, created_at: str
) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "job_kind": "digest",
        "snapshot_id": snapshot_id,
        "owner_id": owner_id,
        "input_sha256": input_sha256,
        "created_at": created_at,
    }


def parse_manifest(data: bytes) -> dict[str, Any]:
    try:
        m = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError("manifest is not valid JSON") from exc
    if not isinstance(m, dict) or any(k not in m for k in _REQUIRED):
        raise ValueError("manifest missing required fields")
    if m["job_kind"] != "digest":
        raise ValueError(f"unsupported job_kind {m['job_kind']!r}")
    if m["format_version"] != FORMAT_VERSION:
        raise ValueError(f"unsupported format_version {m['format_version']!r}")
    return m
