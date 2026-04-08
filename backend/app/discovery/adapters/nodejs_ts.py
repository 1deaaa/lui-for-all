"""
Node.js / TypeScript 适配器（Tree-sitter 版）
============================================

覆盖：NestJS（装饰器）、Express、Fastify、Koa Router、Hono 等主流路由风格。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.discovery.adapters.base import FrameAdapter, RouteSnippet, join_paths, normalize_path


_TS_EXTENSIONS = {".ts", ".js", ".tsx", ".mts", ".mjs", ".cjs", ".cts"}

_KNOWN_FRAMEWORKS = frozenset(
    {
        "express",
        "@nestjs/core",
        "@nestjs/common",
        "fastify",
        "koa",
        "@koa/router",
        "hono",
        "elysia",
        "restify",
        "@hapi/hapi",
        "hapi",
    }
)

_CALL_ROUTE_RE = re.compile(
    r"\.\s*(?P<verb>get|post|put|delete|patch|options|head)\s*\(\s*(?P<q>['\"`])(?P<path>/[^'\"`]*)(?P=q)",
    re.IGNORECASE,
)

_NEST_DECORATOR_RE = re.compile(
    r"@(?P<verb>Get|Post|Put|Delete|Patch|Options|Head|All)\s*\((?P<args>.*?)\)\s*$",
    re.IGNORECASE | re.DOTALL,
)

_NEST_REQUEST_MAPPING_RE = re.compile(
    r"@RequestMapping\s*\((?P<args>.*?)\)\s*$",
    re.IGNORECASE | re.DOTALL,
)

_CONTROLLER_PREFIX_RE = re.compile(
    r"@Controller\s*\((?P<args>.*?)\)",
    re.IGNORECASE | re.DOTALL,
)

_STRING_RE = re.compile(r"['\"`]([^'\"`]+)['\"`]")
_REQUEST_METHOD_RE = re.compile(r"RequestMethod\.([A-Za-z]+)")
_HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]


def _find_ancestor(node: Any, wanted_types: set[str]) -> Any | None:
    cur = node
    while cur is not None:
        if cur.type in wanted_types:
            return cur
        cur = cur.parent
    return None


def _extract_path_from_args(args: str) -> str:
    key_match = re.search(r"(?:path|value|url)\s*:\s*['\"`]([^'\"`]+)['\"`]", args)
    if key_match:
        return normalize_path(key_match.group(1))
    text_match = _STRING_RE.search(args)
    if text_match:
        return normalize_path(text_match.group(1))
    return "/"


class NodejsTypescriptAdapter(FrameAdapter):
    """Node.js / TS 路由适配器。"""

    NAME = "nodejs_typescript"
    LANGUAGES = sorted(_TS_EXTENSIONS)
    TREE_SITTER_LANGUAGES = ["typescript", "javascript"]

    @classmethod
    def can_handle(cls, source_path: Path) -> bool:
        for pkg_path in list(source_path.rglob("package.json"))[:8]:
            if "node_modules" in pkg_path.parts:
                continue
            try:
                pkg = json.loads(pkg_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            deps: dict[str, str] = {}
            deps.update(pkg.get("dependencies", {}))
            deps.update(pkg.get("devDependencies", {}))
            if any(name in deps for name in _KNOWN_FRAMEWORKS):
                return True

        return any(
            file_path.suffix.lower() in _TS_EXTENSIONS
            for file_path in source_path.rglob("*")
            if file_path.is_file() and "node_modules" not in file_path.parts
        )

    def get_tree_sitter_query(self) -> str:
        return """
(call_expression) @call
(decorator) @decorator
(method_definition) @method
(class_declaration) @class
"""

    def _extract_controller_prefix(self, source_bytes: bytes, method_node: Any) -> str:
        class_node = _find_ancestor(method_node, {"class_declaration"})
        if class_node is None:
            return "/"
        class_text = source_bytes[class_node.start_byte : class_node.end_byte].decode(
            "utf-8", errors="replace"
        )
        m = _CONTROLLER_PREFIX_RE.search(class_text)
        if not m:
            return "/"
        return _extract_path_from_args(m.group("args") or "")

    def _parse_decorator_routes(
        self,
        decorator_text: str,
        source_bytes: bytes,
        decorator_node: Any,
    ) -> list[tuple[str, str, Any]]:
        text = decorator_text.strip()

        method_node = _find_ancestor(
            decorator_node,
            {"method_definition", "public_field_definition", "method_signature"},
        )
        snippet_node = method_node or decorator_node
        prefix = self._extract_controller_prefix(source_bytes, method_node) if method_node else "/"

        direct_match = _NEST_DECORATOR_RE.match(text)
        if direct_match:
            verb = (direct_match.group("verb") or "GET").upper()
            args = direct_match.group("args") or ""
            sub_path = _extract_path_from_args(args)
            full_path = join_paths(prefix, sub_path)

            if verb == "ALL":
                return [(method, full_path, snippet_node) for method in _HTTP_METHODS]
            return [(verb, full_path, snippet_node)]

        req_match = _NEST_REQUEST_MAPPING_RE.match(text)
        if req_match:
            args = req_match.group("args") or ""
            sub_path = _extract_path_from_args(args)
            full_path = join_paths(prefix, sub_path)
            methods = [m.upper() for m in _REQUEST_METHOD_RE.findall(args)]
            valid_methods = [m for m in methods if m in _HTTP_METHODS] or ["GET"]
            return [(method, full_path, snippet_node) for method in valid_methods]

        return []

    def _parse_call_routes(self, call_text: str, call_node: Any) -> list[tuple[str, str, Any]]:
        routes: list[tuple[str, str, Any]] = []
        for hit in _CALL_ROUTE_RE.finditer(call_text):
            method = hit.group("verb").upper()
            path = normalize_path(hit.group("path"))
            snippet_node = call_node
            if call_node.parent is not None and call_node.parent.type in {
                "expression_statement",
                "lexical_declaration",
                "variable_declaration",
                "statement_block",
            }:
                snippet_node = call_node.parent
            routes.append((method, path, snippet_node))
        return routes

    def _extract_routes_from_tree(
        self,
        source_file: Path,
        source_bytes: bytes,
        root_node: Any,
        captures: list[tuple[Any, str]],
    ) -> list[RouteSnippet]:
        _ = root_node

        snippets: list[RouteSnippet] = []

        for node, cap_name in captures:
            if cap_name == "decorator":
                dec_text = source_bytes[node.start_byte : node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                for method, path, snippet_node in self._parse_decorator_routes(
                    dec_text,
                    source_bytes,
                    node,
                ):
                    snippets.append(
                        self._make_snippet(
                            method=method,
                            path=path,
                            source_file=source_file,
                            source_bytes=source_bytes,
                            node=snippet_node,
                        )
                    )

            elif cap_name == "call":
                call_text = source_bytes[node.start_byte : node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                for method, path, snippet_node in self._parse_call_routes(call_text, node):
                    snippets.append(
                        self._make_snippet(
                            method=method,
                            path=path,
                            source_file=source_file,
                            source_bytes=source_bytes,
                            node=snippet_node,
                        )
                    )

        return snippets

    def _fallback_extract_all_routes(self) -> list[RouteSnippet]:
        """Tree-sitter 缺失时回退到正则扫描。"""
        snippets: list[RouteSnippet] = []

        for ts_file in self._iter_source_files():
            try:
                content = ts_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = content.splitlines()
            try:
                rel_path = str(ts_file.relative_to(self.source_path))
            except ValueError:
                rel_path = str(ts_file)

            for idx, line in enumerate(lines):
                for hit in _CALL_ROUTE_RE.finditer(line):
                    method = hit.group("verb").upper()
                    path = normalize_path(hit.group("path"))
                    snippets.append(
                        RouteSnippet(
                            route_id=f"{method}:{path}",
                            file_path=rel_path,
                            start_line=idx + 1,
                            end_line=idx + 1,
                            code=line,
                            adapter_name=self.NAME,
                            method=method,
                            path=path,
                        )
                    )

                dec_match = _NEST_DECORATOR_RE.search(line.strip())
                if not dec_match:
                    continue

                method = dec_match.group("verb").upper()
                path = _extract_path_from_args(dec_match.group("args") or "")
                methods = _HTTP_METHODS if method == "ALL" else [method]

                start = idx
                end = idx
                for j in range(idx, min(idx + 12, len(lines))):
                    if "{" in lines[j]:
                        depth = lines[j].count("{") - lines[j].count("}")
                        end = j
                        k = j + 1
                        while k < len(lines) and depth > 0:
                            depth += lines[k].count("{") - lines[k].count("}")
                            end = k
                            k += 1
                        break

                code = "\n".join(lines[start : end + 1])
                for m in methods:
                    snippets.append(
                        RouteSnippet(
                            route_id=f"{m}:{path}",
                            file_path=rel_path,
                            start_line=start + 1,
                            end_line=end + 1,
                            code=code,
                            adapter_name=self.NAME,
                            method=m,
                            path=path,
                        )
                    )

        return snippets
