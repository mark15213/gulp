"""Safe read of an arXiv e-print tarball into in-memory members + ref resolution.

Never extractall; never touch the filesystem. Reject members whose names escape
the archive root (path traversal), and cap cumulative bytes."""

import gzip
import io
import posixpath
import tarfile
from dataclasses import dataclass

_CANDIDATE_EXTS = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".eps")


@dataclass(frozen=True)
class TarMember:
    name: str
    data: bytes


def _is_safe(name: str) -> bool:
    if name.startswith("/") or ".." in name.split("/"):
        return False
    return not posixpath.isabs(name)


def read_tar_gz(blob: bytes, *, max_total: int) -> list[TarMember]:
    if blob[:2] == b"\x1f\x8b":
        blob = gzip.decompress(blob)
    members: list[TarMember] = []
    total = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tar:
            for info in tar.getmembers():
                if not info.isfile() or not _is_safe(info.name):
                    continue
                f = tar.extractfile(info)
                if f is None:
                    continue
                data = f.read()
                total += len(data)
                if total > max_total:
                    break
                members.append(TarMember(name=info.name, data=data))
    except tarfile.TarError:
        return []
    return members


def resolve_member(
    ref_path: str, graphicspath: list[str], members: list[TarMember]
) -> TarMember | None:
    by_name = {m.name: m for m in members}
    prefixes = ["", *graphicspath]
    candidates: list[str] = []
    for prefix in prefixes:
        base = f"{prefix}{ref_path}"
        candidates.append(base)
        if "." not in posixpath.basename(base):
            candidates += [base + ext for ext in _CANDIDATE_EXTS]
    for cand in candidates:
        if cand in by_name:
            return by_name[cand]
    # basename fallback (with/without extension)
    want = posixpath.basename(ref_path)
    for m in members:
        mb = posixpath.basename(m.name)
        if mb == want or mb.rsplit(".", 1)[0] == want:
            return m
    return None
