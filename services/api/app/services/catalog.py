"""RSSHub route catalog (spec 2026-07-09 §3.1): the official routes.json,
Redis-cached for 7 days, searched in-process. This is the one API-side
network fetch — lazy, cached, and never on the subscription hot path."""

import json
import logging
import time
from typing import Any

import httpx
from gulp_shared.settings import settings
from redis import Redis

from app.schemas.feeds import CatalogRouteOut

logger = logging.getLogger("gulp.api")

_CACHE_KEY = "rsshub:catalog"
_REDIS_TTL = 7 * 24 * 3600
_MEMO_TTL = 3600.0

_memo: dict[str, Any] | None = None
_memo_at: float = 0.0


def _fetch_routes_json() -> bytes:
    resp = httpx.get(settings.rsshub_routes_url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def get_catalog() -> dict[str, Any]:
    global _memo, _memo_at
    if _memo is not None and time.monotonic() - _memo_at < _MEMO_TTL:
        return _memo
    raw: bytes | None = None
    try:
        r = Redis.from_url(settings.redis_url)
        raw = r.get(_CACHE_KEY)
        if raw is None:
            raw = _fetch_routes_json()
            r.set(_CACHE_KEY, raw, ex=_REDIS_TTL)
    except httpx.HTTPError:
        raise
    except Exception as exc:  # Redis down — fetch straight through
        logger.warning("catalog cache unavailable (%s); fetching direct", exc)
        raw = _fetch_routes_json()
    _memo = json.loads(raw)
    _memo_at = time.monotonic()
    return _memo


def search_catalog(
    q: str, limit: int = 30, catalog: dict[str, Any] | None = None
) -> list[CatalogRouteOut]:
    data = catalog if catalog is not None else get_catalog()
    ql = q.strip().lower()
    hits: list[CatalogRouteOut] = []
    for ns_key, ns in data.items():
        ns_name = str(ns.get("name") or ns_key)
        ns_match = not ql or ql in ns_key.lower() or ql in ns_name.lower()
        for route_path, route in (ns.get("routes") or {}).items():
            route_name = route.get("name")
            if not (
                ns_match
                or ql in route_path.lower()
                or (route_name and ql in route_name.lower())
            ):
                continue
            features = route.get("features") or {}
            hits.append(
                CatalogRouteOut(
                    namespace=ns_key,
                    namespace_name=ns_name,
                    route_path=route_path,
                    route_name=route_name,
                    example=route.get("example"),
                    parameters=route.get("parameters") or None,
                    require_config=bool(features.get("requireConfig")),
                    heat=int(route.get("heat") or 0),
                )
            )
    hits.sort(key=lambda h: h.heat, reverse=True)
    return hits[:limit]
