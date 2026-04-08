from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.discovery.route_extractor import RouteExtractor


def _route_id(method: str, path: str) -> str:
    return f"{method.upper()}:{path}"


def _pairs_from_route_ids(route_ids: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for route_id in route_ids:
        method, path = route_id.split(":", 1)
        pairs.append((method, path))
    return pairs


REPRESENTATIVE_CASES = [
    {
        "name": "fastapi_sample",
        "adapter": "python_decorator",
        "paradigms": ["decorator_metadata"],
        "path": REPO_ROOT / "backend_for_test" / "fastapi_sample",
        "expected": [
            "GET:/health",
            "GET:/api/users",
            "POST:/api/users",
            "PUT:/api/users/{user_id}",
            "PATCH:/api/users/{user_id}",
            "DELETE:/api/users/{user_id}",
            "HEAD:/api/users",
            "OPTIONS:/api/users",
        ],
    },
    {
        "name": "node_sample",
        "adapter": "nodejs_typescript",
        "paradigms": ["call_registration"],
        "path": REPO_ROOT / "backend_for_test" / "node_sample",
        "expected": [
            "GET:/health",
            "GET:/api/users",
            "POST:/api/users",
            "PUT:/api/users/{userId}",
            "PATCH:/api/users/{userId}",
            "DELETE:/api/users/{userId}",
            "HEAD:/api/users",
            "OPTIONS:/api/users",
        ],
    },
    {
        "name": "django_sample",
        "adapter": "django_urlconf",
        "paradigms": ["route_table"],
        "path": REPO_ROOT / "backend_for_test" / "django_sample",
        "expected": [
            "GET:/api/items",
            "POST:/api/items",
            "PUT:/api/items",
            "PATCH:/api/items",
            "DELETE:/api/items",
            "GET:/api/status",
            "HEAD:/api/status",
            "GET:/api/health",
            "POST:/api/health",
            "PUT:/api/health",
            "PATCH:/api/health",
            "DELETE:/api/health",
            "HEAD:/api/health",
            "OPTIONS:/api/health",
        ],
    },
    {
        "name": "springboot_sample",
        "adapter": "java_spring",
        "paradigms": ["decorator_metadata"],
        "path": REPO_ROOT / "backend_for_test" / "springboot_sample",
        "expected": [
            "GET:/api/items",
            "POST:/api/items",
            "PUT:/api/items/{id}",
            "PATCH:/api/items/{id}",
            "DELETE:/api/items/{id}",
            "HEAD:/api/health",
            "OPTIONS:/api/health",
        ],
    },
    {
        "name": "aspnetcore_sample",
        "adapter": "aspnet_core",
        "paradigms": ["call_registration", "decorator_metadata"],
        "path": REPO_ROOT / "backend_for_test" / "aspnetcore_sample",
        "expected": [
            "GET:/api/items",
            "POST:/api/items",
            "PUT:/api/items/{id}",
            "PATCH:/api/items/{id}",
            "DELETE:/api/items/{id}",
            "HEAD:/api/health",
            "OPTIONS:/api/health",
        ],
    },
    {
        "name": "go_gin_sample",
        "adapter": "go_web",
        "paradigms": ["call_registration"],
        "path": REPO_ROOT / "backend_for_test" / "go_gin_sample",
        "expected": [
            "GET:/api/items",
            "POST:/api/items",
            "PUT:/api/items/{id}",
            "PATCH:/api/items/{id}",
            "DELETE:/api/items/{id}",
            "HEAD:/api/health",
            "OPTIONS:/api/health",
        ],
    },
    {
        "name": "node_native_sample",
        "adapter": "nodejs_typescript",
        "paradigms": ["imperative_dispatch"],
        "path": REPO_ROOT / "backend_for_test" / "node_native_sample",
        "expected": [
            "GET:/api/items",
            "POST:/api/items",
            "PUT:/api/items/{id}",
            "PATCH:/api/items/{id}",
            "DELETE:/api/items/{id}",
            "HEAD:/api/health",
            "OPTIONS:/api/health",
        ],
    },
]


@pytest.mark.parametrize("case", REPRESENTATIVE_CASES, ids=[c["name"] for c in REPRESENTATIVE_CASES])
def test_representative_extract_all_routes(case: dict):
    source_path = case["path"]
    assert source_path.exists(), f"Sample path missing: {source_path}"

    extractor = RouteExtractor(str(source_path))
    assert extractor.adapter_name == case["adapter"]

    snippets = extractor.extract_all_routes()
    discovered_ids = {snippet.route_id for snippet in snippets}

    expected_ids = {_route_id(*pair) for pair in _pairs_from_route_ids(case["expected"])}
    missing = sorted(expected_ids - discovered_ids)

    assert not missing, (
        f"Missing route ids for {case['name']}: {missing}. "
        f"Discovered sample: {sorted(list(discovered_ids))[:30]}"
    )


@pytest.mark.parametrize("case", REPRESENTATIVE_CASES, ids=[c["name"] for c in REPRESENTATIVE_CASES])
def test_representative_adapter_ast_paradigms(case: dict):
    extractor = RouteExtractor(str(case["path"]))
    assert extractor.adapter_name == case["adapter"]

    paradigms = set(extractor.adapter_ast_paradigms)
    for expected_paradigm in case["paradigms"]:
        assert expected_paradigm in paradigms, (
            f"Adapter {case['adapter']} missing AST paradigm {expected_paradigm}; "
            f"actual={sorted(paradigms)}"
        )


@pytest.mark.parametrize("case", REPRESENTATIVE_CASES, ids=[c["name"] for c in REPRESENTATIVE_CASES])
def test_representative_extract_batch_returns_function_snippets(case: dict):
    source_path = case["path"]
    extractor = RouteExtractor(str(source_path))

    route_pairs = _pairs_from_route_ids(case["expected"])
    batch = extractor.extract_batch(route_pairs)

    missing = [route_id for route_id in case["expected"] if batch.get(route_id) is None]
    assert not missing, f"Missing function snippets for {case['name']}: {missing}"

    for route_id in case["expected"]:
        snippet = batch[route_id]
        assert snippet is not None
        assert snippet.code.strip(), f"Empty snippet code for {route_id}"
        assert snippet.start_line <= snippet.end_line
