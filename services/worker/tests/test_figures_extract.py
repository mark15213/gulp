import gzip
import io
import tarfile

from app.pipeline.figures.extract import extract_figures


def _targz(files: dict[str, bytes]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(raw.getvalue())


_PNG = b"\x89PNG\r\n\x1a\n" + b"rest"


def test_tex_driven_order_and_captions() -> None:
    tex = (r"\begin{figure}\includegraphics{a}\caption{First}\end{figure}"
           r"\includegraphics{b.png}")
    blob = _targz({"main.tex": tex.encode(), "a.png": _PNG, "b.png": _PNG})
    figs = extract_figures(blob)
    assert [f.order for f in figs] == [0, 1]
    assert figs[0].caption == "First" and figs[0].ext == "png"


def test_file_scan_fallback_when_no_tex_refs() -> None:
    blob = _targz({"main.tex": b"no includes here", "z.png": _PNG})
    figs = extract_figures(blob)
    assert len(figs) == 1 and figs[0].ext == "png"


def test_no_images_returns_empty() -> None:
    assert extract_figures(_targz({"main.tex": b"text only"})) == []


def test_same_member_referenced_twice_is_deduped() -> None:
    tex = r"\includegraphics{a.png}\includegraphics{a.png}"
    figs = extract_figures(_targz({"main.tex": tex.encode(), "a.png": _PNG}))
    assert len(figs) == 1


def test_oversized_image_is_skipped(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("app.pipeline.figures.extract.MAX_IMAGE_BYTES", 4)
    tex = r"\includegraphics{a.png}"
    figs = extract_figures(_targz({"main.tex": tex.encode(), "a.png": _PNG}))  # _PNG is >4 bytes
    assert figs == []


def test_respects_max_figures_cap(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("app.pipeline.figures.extract.MAX_FIGURES", 1)
    tex = r"\includegraphics{a.png}\includegraphics{b.png}"
    figs = extract_figures(_targz({"main.tex": tex.encode(), "a.png": _PNG, "b.png": _PNG}))
    assert len(figs) == 1
