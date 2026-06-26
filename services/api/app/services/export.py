"""Export endpoints' business logic (S2 export executor)."""

import io
import json
import os
import zipfile

from gulp_shared.settings import settings


def job_path(snapshot_id: str) -> str:
    return os.path.join(settings.export_dir, f"{snapshot_id}.zip")


def result_path(snapshot_id: str) -> str:
    return os.path.join(settings.export_dir, f"{snapshot_id}-result.zip")


def _find(zf: zipfile.ZipFile, suffix: str) -> str | None:
    for name in zf.namelist():
        if name == suffix or name.endswith("/" + suffix):
            return name
    return None


def shallow_check(data: bytes, *, snapshot_id: str, owner_id: str) -> None:
    """Stdlib-only sanity check; raises ValueError with a reason on failure."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            man_name = _find(zf, "manifest.json")
            if man_name is None:
                raise ValueError("archive has no manifest.json")
            try:
                man = json.loads(zf.read(man_name))
            except json.JSONDecodeError as exc:
                raise ValueError("manifest.json is not valid JSON") from exc
            if man.get("snapshot_id") != snapshot_id:
                raise ValueError("manifest snapshot_id does not match this snapshot")
            if man.get("owner_id") != owner_id:
                raise ValueError("manifest owner_id does not match")
            if _find(zf, "result/pack.json") is None:
                raise ValueError("archive has no result/pack.json")
    except zipfile.BadZipFile as exc:
        raise ValueError("upload is not a valid zip") from exc


def stash_result(data: bytes, snapshot_id: str) -> str:
    os.makedirs(settings.export_dir, exist_ok=True)
    path = result_path(snapshot_id)
    with open(path, "wb") as f:
        f.write(data)
    return path
