import gzip
import io
import tarfile

from app.pipeline.figures.tarball import read_tar_gz, resolve_member


def _targz(files: dict[str, bytes], *, unsafe_name: str | None = None) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        if unsafe_name:
            info = tarfile.TarInfo(unsafe_name)
            info.size = 3
            tar.addfile(info, io.BytesIO(b"bad"))
    return gzip.compress(raw.getvalue())


def test_reads_members_and_skips_traversal() -> None:
    blob = _targz({"main.tex": b"hi", "fig/a.png": b"PNG"}, unsafe_name="../evil.png")
    members = read_tar_gz(blob, max_total=1_000_000)
    names = {m.name for m in members}
    assert "main.tex" in names and "fig/a.png" in names
    assert "../evil.png" not in names  # path traversal rejected


def test_resolve_by_extension_and_graphicspath() -> None:
    blob = _targz({"figs/arch.pdf": b"%PDF", "plot.png": b"PNG"})
    members = read_tar_gz(blob, max_total=1_000_000)
    # ref omits extension and lives under graphicspath "figs/"
    assert resolve_member("arch", ["figs/"], members).name == "figs/arch.pdf"
    # exact-with-extension
    assert resolve_member("plot.png", [], members).name == "plot.png"
    # basename fallback
    assert resolve_member("sub/arch", [], members).name == "figs/arch.pdf"
    assert resolve_member("missing", [], members) is None
