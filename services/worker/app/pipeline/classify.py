"""Genre detection — what kind of knowledge artifact a source is.

Pure heuristics, zero LLM: the preserve strategy is the safe fallback for
anything ambiguous, and a wrong call is user-correctable (Source.genre is
editable; re-processing then takes the corrected path).
"""

from gulp_shared.models.source import SourceGenre
from gulp_shared.urls import host_of

# Hosts whose content is (approximately always) an academic paper.
_PAPER_HOSTS = ("arxiv.org", "openreview.net")


def detect_genre(origin_url: str | None, media_type: str) -> SourceGenre:
    if origin_url is None:
        return SourceGenre.note
    host = (host_of(origin_url) or "").lower()
    if any(host == h or host.endswith("." + h) for h in _PAPER_HOSTS):
        return SourceGenre.paper
    # In this product's context a captured PDF is nearly always a paper;
    # non-paper PDFs are corrected by editing the genre.
    if media_type == "pdf":
        return SourceGenre.paper
    return SourceGenre.article
