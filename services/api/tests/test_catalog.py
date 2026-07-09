import json
import pathlib

from app.services.catalog import search_catalog

CATALOG = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "routes_slice.json").read_text()
)


def test_search_by_namespace_name():
    items = search_catalog("github", catalog=CATALOG)
    assert [i.route_path for i in items] == ["/github/activity/:user", "/github/notifications"]
    assert items[0].heat == 4835 and items[0].require_config is False
    assert items[1].require_config is True


def test_search_matches_chinese_namespace():
    items = search_catalog("少数派", catalog=CATALOG)
    assert items[0].route_path == "/sspai/index" and items[0].parameters is None


def test_search_by_route_name():
    assert search_catalog("Activities", catalog=CATALOG)[0].route_name == "User Activities"


def test_empty_query_returns_top_heat():
    items = search_catalog("", catalog=CATALOG, limit=2)
    assert [i.route_path for i in items] == ["/sspai/index", "/v2ex/topics/:type"]


def test_no_match_is_empty():
    assert search_catalog("zzzznope", catalog=CATALOG) == []


def test_object_valued_parameters_flatten_to_strings():
    items = search_catalog("Notifications", catalog=CATALOG)
    assert items[0].parameters == {"type": "Event type (issue / discussion)"}
