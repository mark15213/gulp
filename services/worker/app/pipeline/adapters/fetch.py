"""The one network boundary: fetch a URL into bytes + content-type."""

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class FetchedDoc:
    content: bytes
    content_type: str


async def fetch_document(url: str) -> FetchedDoc:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url, headers={"User-Agent": "GulpBot/1.0"})
        resp.raise_for_status()
        return FetchedDoc(content=resp.content, content_type=resp.headers.get("content-type", ""))


def is_pdf(doc: FetchedDoc) -> bool:
    return "application/pdf" in doc.content_type.lower()
