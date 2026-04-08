"""
ASP.NET Core 适配器（Tree-sitter 版）
===================================

覆盖：
- Controller 属性路由：[HttpGet] / [Route]
- Minimal API：app.MapGet / MapPost / MapMethods
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.discovery.adapters.base import FrameAdapter, join_paths, normalize_path
from app.discovery.adapters.paradigms import (
    AST_PARADIGM_CALL_REGISTRATION,
    AST_PARADIGM_DECORATOR_METADATA,
)


_HTTP_ATTR_RE = re.compile(
    r"\[Http(?P<verb>Get|Post|Put|Delete|Patch|Head|Options)(?:\(\s*\"(?P<path>[^\"]*)\"\s*\))?\]",
    re.IGNORECASE,
)
_ROUTE_ATTR_RE = re.compile(r"\[Route\(\s*\"(?P<path>[^\"]+)\"\s*\)\]", re.IGNORECASE)
_CLASS_NAME_RE = re.compile(r"class\s+(?P<name>[A-Za-z_]\w*)")
_MAP_CALL_RE = re.compile(
    r"\.Map(?P<verb>Get|Post|Put|Delete|Patch|Head|Options)\s*\(\s*\"(?P<path>[^\"]+)\"",
    re.IGNORECASE,
)
_MAP_METHODS_RE = re.compile(
    r"\.MapMethods\s*\(\s*\"(?P<path>[^\"]+)\"\s*,\s*new\s*\[\]\s*\{(?P<methods>[^\}]*)\}",
    re.IGNORECASE | re.DOTALL,
)


class AspNetCoreAdapter(FrameAdapter):
    """C# ASP.NET Core 路由适配器。"""

    NAME = "aspnet_core"
    LANGUAGES = [".cs"]
    TREE_SITTER_LANGUAGES = ["c_sharp", "csharp", "c-sharp"]
    AST_PARADIGMS = [AST_PARADIGM_DECORATOR_METADATA, AST_PARADIGM_CALL_REGISTRATION]
    SUPPORTED_FRAMEWORKS = ["aspnet-core-controller", "aspnet-core-minimal-api"]

    @classmethod
    def can_handle(cls, source_path: Path) -> bool:
        for csproj in source_path.rglob("*.csproj"):
            try:
                text = csproj.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lowered = text.lower()
            if "microsoft.aspnetcore" in lowered or "web sdk" in lowered:
                return True

        scanned = 0
        for cs_file in source_path.rglob("*.cs"):
            if scanned >= 60:
                break
            scanned += 1
            try:
                content = cs_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if "[ApiController]" in content or "MapGet(" in content or "HttpGet" in content:
                return True

        return False

    def get_tree_sitter_query(self) -> str:
        return """
(class_declaration) @class
(method_declaration) @method
(invocation_expression) @call
"""

    def _extract_class_prefix(self, source_bytes: bytes, class_node: Any) -> str:
        class_text = source_bytes[class_node.start_byte : class_node.end_byte].decode(
            "utf-8", errors="replace"
        )

        route_match = _ROUTE_ATTR_RE.search(class_text)
        if not route_match:
            return "/"

        raw = route_match.group("path")
        class_name_match = _CLASS_NAME_RE.search(class_text)
        if class_name_match:
            class_name = class_name_match.group("name")
            if class_name.lower().endswith("controller"):
                class_name = class_name[: -len("controller")]
            raw = raw.replace("[controller]", class_name)

        return normalize_path(raw)

    def _extract_routes_from_tree(
        self,
        source_file: Path,
        source_bytes: bytes,
        root_node: Any,
        captures: list[tuple[Any, str]],
    ):
        _ = root_node

        class_nodes = [node for node, name in captures if name == "class"]
        method_nodes = [node for node, name in captures if name == "method"]
        call_nodes = [node for node, name in captures if name == "call"]

        class_prefix_cache: dict[tuple[int, int], str] = {}
        for class_node in class_nodes:
            key = (class_node.start_byte, class_node.end_byte)
            class_prefix_cache[key] = self._extract_class_prefix(source_bytes, class_node)

        snippets = []

        # 1) Controller 属性路由
        for method_node in method_nodes:
            method_text = source_bytes[
                method_node.start_byte : method_node.end_byte
            ].decode("utf-8", errors="replace")

            prefix = "/"
            for class_node in class_nodes:
                if (
                    class_node.start_byte <= method_node.start_byte
                    and class_node.end_byte >= method_node.end_byte
                ):
                    prefix = class_prefix_cache.get(
                        (class_node.start_byte, class_node.end_byte),
                        "/",
                    )
                    break

            method_route = None
            route_attr = _ROUTE_ATTR_RE.search(method_text)
            if route_attr:
                method_route = normalize_path(route_attr.group("path"))

            for hit in _HTTP_ATTR_RE.finditer(method_text):
                method = hit.group("verb").upper()
                attr_path = hit.group("path")
                sub_path = normalize_path(attr_path) if attr_path else (method_route or "/")
                full_path = join_paths(prefix, sub_path)
                snippets.append(
                    self._make_snippet(
                        method=method,
                        path=full_path,
                        source_file=source_file,
                        source_bytes=source_bytes,
                        node=method_node,
                    )
                )

        # 2) Minimal API
        for call_node in call_nodes:
            call_text = source_bytes[
                call_node.start_byte : call_node.end_byte
            ].decode("utf-8", errors="replace")

            for hit in _MAP_CALL_RE.finditer(call_text):
                method = hit.group("verb").upper()
                path = normalize_path(hit.group("path"))
                node_for_snippet = call_node.parent if call_node.parent is not None else call_node
                snippets.append(
                    self._make_snippet(
                        method=method,
                        path=path,
                        source_file=source_file,
                        source_bytes=source_bytes,
                        node=node_for_snippet,
                    )
                )

            for hit in _MAP_METHODS_RE.finditer(call_text):
                path = normalize_path(hit.group("path"))
                methods_text = hit.group("methods")
                methods = [m.upper() for m in re.findall(r'"([A-Za-z]+)"', methods_text)]
                methods = [m for m in methods if m in {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}]
                if not methods:
                    continue

                node_for_snippet = call_node.parent if call_node.parent is not None else call_node
                for method in methods:
                    snippets.append(
                        self._make_snippet(
                            method=method,
                            path=path,
                            source_file=source_file,
                            source_bytes=source_bytes,
                            node=node_for_snippet,
                        )
                    )

        return snippets
