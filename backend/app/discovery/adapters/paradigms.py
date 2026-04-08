"""
AST routing paradigm constants shared by all adapters.
"""

from __future__ import annotations

AST_PARADIGM_DECORATOR_METADATA = "decorator_metadata"
AST_PARADIGM_CALL_REGISTRATION = "call_registration"
AST_PARADIGM_ROUTE_TABLE = "route_table"
AST_PARADIGM_IMPERATIVE_DISPATCH = "imperative_dispatch"

AST_PARADIGM_DESCRIPTIONS: dict[str, str] = {
    AST_PARADIGM_DECORATOR_METADATA: "Metadata/annotation driven routes (@Get, [HttpGet], decorators)",
    AST_PARADIGM_CALL_REGISTRATION: "Call-expression registration (app.get, router.POST, MapGet)",
    AST_PARADIGM_ROUTE_TABLE: "Centralized route tables or declarative URL lists (urlpatterns)",
    AST_PARADIGM_IMPERATIVE_DISPATCH: "Imperative control flow dispatch (if/switch on method+path)",
}

ALL_AST_PARADIGMS: tuple[str, ...] = tuple(AST_PARADIGM_DESCRIPTIONS.keys())


def normalize_ast_paradigms(values: list[str] | tuple[str, ...]) -> list[str]:
    """Return deduplicated, validated paradigm names while preserving order."""
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        key = (item or "").strip()
        if not key or key in seen:
            continue
        if key not in AST_PARADIGM_DESCRIPTIONS:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized
