from app.api.sessions import _merge_parameter_hints as merge_session_hints
from app.mcp.server import _merge_parameter_hints as merge_mcp_hints


def _build_case_data():
    capability_hints = {
        "id": {
            "name": "id",
            "location": "path",
            "type": "str",
            "required": True,
        }
    }
    backed_by_routes = [{"route_id": "GET:/api/users/{id}"}]
    route_hints_by_route_id = {
        "GET:/api/users/{id}": {
            "id@path": {
                "name": "id",
                "location": "path",
                "type": "str",
                "required": True,
            },
            "id@query": {
                "name": "id",
                "location": "query",
                "type": "str",
                "required": False,
            },
            "expand": {
                "name": "expand",
                "location": "query",
                "type": "str",
                "required": False,
            },
        }
    }
    return capability_hints, backed_by_routes, route_hints_by_route_id


def test_sessions_merge_keeps_same_name_different_locations():
    capability_hints, backed_by_routes, route_hints_by_route_id = _build_case_data()

    merged = merge_session_hints(capability_hints, backed_by_routes, route_hints_by_route_id)

    assert "id" in merged
    assert merged["id"]["location"] == "path"
    assert "id@query" in merged
    assert merged["id@query"]["location"] == "query"
    assert "expand" in merged


def test_mcp_merge_keeps_same_name_different_locations():
    capability_hints, backed_by_routes, route_hints_by_route_id = _build_case_data()

    merged = merge_mcp_hints(capability_hints, backed_by_routes, route_hints_by_route_id)

    assert "id" in merged
    assert merged["id"]["location"] == "path"
    assert "id@query" in merged
    assert merged["id@query"]["location"] == "query"
    assert "expand" in merged
