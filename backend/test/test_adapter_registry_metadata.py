from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.discovery.adapters import list_adapters, list_ast_paradigms


EXPECTED_PARADIGMS = {
    "decorator_metadata",
    "call_registration",
    "route_table",
    "imperative_dispatch",
}


def test_ast_paradigm_catalog_is_complete() -> None:
    catalog = list_ast_paradigms()
    assert EXPECTED_PARADIGMS == set(catalog.keys())


def test_registered_adapters_publish_metadata() -> None:
    adapters = list_adapters()
    assert adapters, "adapter registry should not be empty"

    for item in adapters:
        assert item["name"]
        assert item["class"]
        assert isinstance(item["languages"], list)
        assert isinstance(item["tree_sitter_languages"], list)
        assert isinstance(item["ast_paradigms"], list)
        assert isinstance(item["supported_frameworks"], list)

        for paradigm in item["ast_paradigms"]:
            assert paradigm in EXPECTED_PARADIGMS
