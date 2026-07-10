"""arxiv adapter — resolve the canonical paper title from the abstract page.

arxiv PDFs frequently carry no /Title metadata and lead with a license header,
so the generic PDF heuristic mis-titles them. The abstract page exposes a clean
<meta name="citation_title">, which we use instead — for arxiv URLs only.
"""

import logging
import re
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from app.pipeline.adapters.fetch import FetchedDoc, fetch_document

FetchFn = Callable[[str], Awaitable[FetchedDoc]]
logger = logging.getLogger("gulp.worker")

_ARXIV_HOSTS = {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}
_ARXIV_PATH = re.compile(r"^/(?:pdf|abs)/(.+?)(?:\.pdf)?$", re.IGNORECASE)
_CITATION_TITLE = re.compile(
    r'<meta[^>]+name=["\']citation_title["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def arxiv_id(url: str) -> str | None:
    parts = urlsplit(url)
    if (parts.hostname or "").lower() not in _ARXIV_HOSTS:
        return None
    path = parts.path.rstrip("/")  # tolerate a trailing slash
    m = _ARXIV_PATH.match(path)
    if not m:
        return None
    ident = m.group(1)
    return ident or None


def arxiv_abs_url(url: str) -> str | None:
    ident = arxiv_id(url)
    return f"https://arxiv.org/abs/{ident}" if ident else None


def arxiv_eprint_url(url: str) -> str | None:
    ident = arxiv_id(url)
    return f"https://arxiv.org/e-print/{ident}" if ident else None


def is_arxiv(url: str) -> bool:
    return arxiv_id(url) is not None


async def arxiv_title(url: str, *, fetch: FetchFn = fetch_document) -> str | None:
    abs_url = arxiv_abs_url(url)
    if abs_url is None:
        return None
    try:
        doc = await fetch(abs_url)
        html = doc.content.decode("utf-8", errors="replace")
    except Exception:
        logger.debug("arxiv_title: failed to fetch abstract for %s", url, exc_info=True)
        return None
    m = _CITATION_TITLE.search(html)
    return m.group(1).strip() if m else None
