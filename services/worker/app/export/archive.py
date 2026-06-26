"""Safe zip read/write for export job + result archives."""

import io
import zipfile
from pathlib import PurePosixPath

_DEFAULT_MAX_TOTAL = 26_214_400  # 25 MiB uncompressed, total


def write_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def read_zip(data: bytes, *, max_total: int = _DEFAULT_MAX_TOTAL) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    total = 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            parts = PurePosixPath(name).parts
            if name.startswith("/") or ".." in parts:
                raise ValueError(f"unsafe zip entry: {name!r}")
            total += info.file_size
            if total > max_total:
                raise ValueError("archive exceeds size cap")
            out[name] = zf.read(info)
    return out


def find_entry(files: dict[str, bytes], suffix: str) -> bytes:
    for name, content in files.items():
        if name == suffix or name.endswith("/" + suffix):
            return content
    raise KeyError(suffix)
