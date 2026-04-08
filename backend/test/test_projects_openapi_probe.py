from app.api.projects import (
    _build_openapi_probe_urls,
    _extract_routes_from_openapi_spec,
    _is_valid_openapi_spec,
)


def test_build_openapi_probe_urls_with_docs_base():
    urls = _build_openapi_probe_urls("http://localhost:6688/docs", None)

    assert "http://localhost:6688/docs/openapi.json" in urls
    assert "http://localhost:6688/openapi.json" in urls
    assert "http://localhost:6688/api/openapi.json" in urls


def test_openapi_spec_validation_rejects_non_spec_json():
    assert _is_valid_openapi_spec([{"error": "Not found"}, 404]) is False
    assert _is_valid_openapi_spec({"ok": True}) is False

    valid_spec = {
        "openapi": "3.1.0",
        "paths": {
            "/users": {
                "get": {
                    "summary": "list users"
                }
            }
        },
    }
    assert _is_valid_openapi_spec(valid_spec) is True


def test_extract_routes_handles_non_spec_payload_safely():
    assert _extract_routes_from_openapi_spec([]) == []
    assert _extract_routes_from_openapi_spec({"paths": []}) == []
