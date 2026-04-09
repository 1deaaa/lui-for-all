from app.graph.nodes_agentic import _find_route_parameter_hints, _resolve_param_hint


def test_find_route_parameter_hints_prefers_route_level_map():
    state = {
        "route_hints_by_route_id": {
            "GET:/api/users": {
                "limit": {
                    "name": "limit",
                    "location": "query",
                }
            }
        },
        "available_capabilities": [
            {
                "backed_by_routes": [{"route_id": "GET:/api/users"}],
                "parameter_hints": {
                    "limit": {
                        "name": "limit",
                        "location": "body",
                    }
                },
            }
        ],
    }

    hints = _find_route_parameter_hints(state, "GET:/api/users")

    assert hints["limit"]["location"] == "query"


def test_resolve_param_hint_prefers_method_aware_location():
    route_hints = {
        "id@query": {"name": "id", "location": "query"},
        "id@body": {"name": "id", "location": "body"},
    }

    get_hint = _resolve_param_hint(route_hints, "id", "GET")
    post_hint = _resolve_param_hint(route_hints, "id", "POST")

    assert get_hint is not None
    assert post_hint is not None
    assert get_hint["location"] == "query"
    assert post_hint["location"] == "body"
