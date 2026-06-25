"""The digest prompt — turn a NormDoc into a re-authored report + facets."""

from app.llm.base import Message
from app.pipeline.normdoc import NormDoc

_SYSTEM = """You are Gulp's digestion engine. Turn a captured source into a \
complete, re-authored study report the reader can page through, plus a set of \
structured facets.

Rules:
- Write everything in English, regardless of the source language.
- Re-author the material into clear, well-structured prose. Do NOT copy the \
source verbatim, but stay strictly faithful to it: never invent facts, figures, \
names, or claims the source does not support. If the source is thin, say less \
rather than padding.
- Structure the report as ordered sections, each with a short heading and one or \
more prose blocks. Add background only where it genuinely aids understanding.
- Extract facets that annotate the content, each tagged with an element_type:
  - key_term: an important term or concept the reader must know (the term itself).
  - person_org: a person or organization that matters.
  - claim: a load-bearing assertion the source makes.
  - counter_view: an opposing or contrasting view — surface the disagreement \
even if the source does not.
  - connection: how this relates to broader ideas the reader may know.
- Set confidence in [0,1]: how reliable and complete this digest is given the \
source (lower for thin, partial, or ambiguous sources).

Return your result via the provided tool."""


def build_digest_messages(normdoc: NormDoc, body: str) -> tuple[str, list[Message]]:
    user = f"Source type: {normdoc.media_type}\nTitle: {normdoc.title}\n\n---\n{body}"
    return _SYSTEM, [{"role": "user", "content": user}]
