"""Canonicalize a URL for dedupe (spec C2). Pure; no network."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"fbclid", "gclid", "ref", "ref_src"}


def normalize_url(raw: str) -> str:
    parts = urlsplit(raw.strip(), scheme="https")
    # urlsplit puts "a.com/x" into .path when no "//"; re-parse with a scheme prefix.
    if not parts.netloc:
        parts = urlsplit(f"https://{raw.strip()}")
    scheme = (parts.scheme or "https").lower()
    host = (parts.hostname or "").lower()
    try:
        if parts.port:
            host = f"{host}:{parts.port}"
    except ValueError:
        pass  # bad port (e.g. "notaport") — treat as no port
    path = parts.path.rstrip("/") or "/"
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query)
        if not k.lower().startswith(_TRACKING_PREFIXES) and k.lower() not in _TRACKING_KEYS
    ]
    return urlunsplit((scheme, host, path, urlencode(kept), ""))


def is_http_url(raw: str) -> bool:
    """True iff `raw` (https:// assumed if scheme-less) is an http(s) URL with a plausible host."""
    s = raw.strip()
    if not s or any(c.isspace() for c in s):
        return False
    parts = urlsplit(s if "//" in s else f"https://{s}")
    if parts.scheme not in ("http", "https"):
        return False
    host = parts.hostname or ""
    return bool(host) and ("." in host or host == "localhost")
