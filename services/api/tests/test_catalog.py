import json
import pathlib

from app.services.catalog import search_catalog

CATALOG = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "routes_slice.json").read_text()
)


def test_search_by_namespace_name():
    items, count = search_catalog("github", catalog=CATALOG)
    assert [i.route_path for i in items] == ["/github/activity/:user", "/github/notifications"]
    assert count == 2
    assert items[0].heat == 4835 and items[0].require_config is False
    assert items[1].require_config is True


def test_search_matches_chinese_namespace():
    items, _ = search_catalog("少数派", catalog=CATALOG)
    assert items[0].route_path == "/sspai/index" and items[0].parameters is None


def test_search_by_route_name():
    items, _ = search_catalog("Activities", catalog=CATALOG)
    assert items[0].route_name == "User Activities"


def test_empty_query_returns_top_heat():
    items, count = search_catalog("", catalog=CATALOG, limit=2)
    assert [i.route_path for i in items] == ["/sspai/index", "/v2ex/topics/:type"]
    assert count == 4


def test_search_paginates_without_losing_total_count():
    items, count = search_catalog("", catalog=CATALOG, limit=2, offset=2)
    assert [i.route_path for i in items] == [
        "/github/activity/:user",
        "/github/notifications",
    ]
    assert count == 4


def test_no_match_is_empty():
    assert search_catalog("zzzznope", catalog=CATALOG) == ([], 0)


def test_object_valued_parameters_flatten_to_strings():
    items, _ = search_catalog("Notifications", catalog=CATALOG)
    assert items[0].parameters == {"type": "Event type (issue / discussion)"}
