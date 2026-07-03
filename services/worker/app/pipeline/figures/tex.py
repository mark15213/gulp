# services/worker/app/pipeline/figures/tex.py
"""Best-effort TeX scanning: ordered \\includegraphics refs + figure captions.

Not a real TeX parser — deliberately small and forgiving. Feeds the hybrid
extractor (spec §8); the tarball file-scan fallback covers whatever this misses.
"""

import re

from app.pipeline.figures.types import TexRef

_COMMENT = re.compile(r"(?<!\\)%.*")
_INCLUDE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
_FIGURE_ENV = re.compile(r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}", re.DOTALL)
_CAPTION = re.compile(r"\\caption\{([^}]*)\}")
_LABEL = re.compile(r"\\label\{([^}]+)\}")
_GRAPHICSPATH = re.compile(r"\\graphicspath\{((?:\{[^}]*\})+)\}")
_PATH_ITEM = re.compile(r"\{([^}]*)\}")


def _strip_comments(tex: str) -> str:
    return "\n".join(_COMMENT.sub("", line) for line in tex.splitlines())


def parse_graphicspath(tex: str) -> list[str]:
    m = _GRAPHICSPATH.search(_strip_comments(tex))
    return _PATH_ITEM.findall(m.group(1)) if m else []


def parse_tex_refs(tex: str) -> list[TexRef]:
    body = _strip_comments(tex)
    # Map each figure-env includegraphics span to that env's caption/label.
    env_meta: dict[int, tuple[str | None, str | None]] = {}
    for env in _FIGURE_ENV.finditer(body):
        cap = _CAPTION.search(env.group(1))
        lab = _LABEL.search(env.group(1))
        caption = cap.group(1).strip() if cap else None
        label = lab.group(1).strip() if lab else None
        for inc in _INCLUDE.finditer(env.group(1)):
            env_meta[env.start(1) + inc.start()] = (caption, label)

    refs: list[TexRef] = []
    for inc in _INCLUDE.finditer(body):
        caption, label = env_meta.get(inc.start(), (None, None))
        refs.append(TexRef(path=inc.group(1).strip(), label=label,
                           caption=caption, order=len(refs)))
    return refs
