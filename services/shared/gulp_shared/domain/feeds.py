"""Feed-address rules (spec 2026-07-09 §1.1/§2): canonical storage form is
Folo's instance-independent `rsshub://ns/path`, or a plain http(s) feed URL."""

import hashlib

RSSHUB_SCHEME = "rsshub://"


def normalize_feed_url(raw: str) -> str:
    """Canonicalize user input; raises ValueError on unusable addresses."""
    s = raw.strip()
    if s.startswith(RSSHUB_SCHEME):
        rest = s[len(RSSHUB_SCHEME) :].strip().strip("/")
        if not rest:
            raise ValueError("empty rsshub:// route")
        return RSSHUB_SCHEME + rest
    if s.startswith("/"):
        rest = s.strip("/")
        if not rest:
            raise ValueError("empty route path")
        return RSSHUB_SCHEME + rest
    if s.startswith(("http://", "https://")) and len(s) > 8:
        return s
    raise ValueError("feed address must be rsshub://…, /route/path, or http(s)://…")


def resolve_feed_url(feed_url: str, rsshub_base_url: str) -> str:
    """Turn the stored form into a fetchable URL against the configured instance."""
    if feed_url.startswith(RSSHUB_SCHEME):
        return rsshub_base_url.rstrip("/") + "/" + feed_url[len(RSSHUB_SCHEME) :]
    return feed_url


def entry_guid(entry_id: str | None, link: str | None, title: str | None) -> str:
    """Feed-provided id, else a stable hash of link+title (spec §1.4)."""
    if entry_id and entry_id.strip():
        return entry_id.strip()[:512]
    basis = f"{(link or '').strip()}|{(title or '').strip()}"
    return "sha256:" + hashlib.sha256(basis.encode()).hexdigest()
