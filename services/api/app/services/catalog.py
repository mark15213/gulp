"""RSSHub route catalog — stub; filled in by the catalog task (spec §3.1)."""

from app.schemas.feeds import CatalogRouteOut


def search_catalog(q: str, limit: int = 30) -> list[CatalogRouteOut]:
    return []
