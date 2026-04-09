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
from app.discovery.adapters.paradigms import (
    AST_PARADIGM_CALL_REGISTRATION,
    AST_PARADIGM_DECORATOR_METADATA,
    AST_PARADIGM_IMPERATIVE_DISPATCH,
)


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
    }
)

_CALL_ROUTE_RE = re.compile(
    r"\.\s*(?P<verb>get|post|put|delete|patch|options|head)\s*\(\s*(?P<q>['\"`])(?P<path>/[^'\"`]*)(?P=q)",
    re.IGNORECASE,
)

_IF_CONDITION_METHOD_RE = re.compile(
    r"(?:req\.(?:method|httpMethod)|method)\s*[=!]==?\s*['\"`](?P<left>[A-Za-z]+)['\"`]|['\"`](?P<right>[A-Za-z]+)['\"`]\s*[=!]==?\s*(?:req\.(?:method|httpMethod)|method)",
    re.IGNORECASE,
)
_IF_CONDITION_PATH_RE = re.compile(
    r"(?:req\.(?:url|path|pathname)|url|path|pathname)\s*[=!]==?\s*['\"`](?P<left>/[^'\"`]*)['\"`]|['\"`](?P<right>/[^'\"`]*)['\"`]\s*[=!]==?\s*(?:req\.(?:url|path|pathname)|url|path|pathname)",
    re.IGNORECASE,
)
_HANDLER_CALL_RE = re.compile(
    r"(?:return\s+)?(?P<handler>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\("
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
_HTTP_METHOD_SET = set(_HTTP_METHODS)


def _normalize_handler_candidate(raw: str | None) -> str | None:
    if not raw:
        return None

    candidate = (raw or "").strip()
    candidate = candidate.replace("?.", ".")
    candidate = re.sub(r"\s+", "", candidate)

    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", candidate):
        return None
    return candidate


def _resolve_handler_node(handler_index: dict[str, Any], candidate: str | None) -> Any | None:
    normalized = _normalize_handler_candidate(candidate)
    if not normalized:
        return None

    direct = handler_index.get(normalized)
    if direct is not None:
        return direct

    if normalized.startswith("this."):
        direct = handler_index.get(normalized[5:])
        if direct is not None:
            return direct

    leaf = normalized.rsplit(".", 1)[-1]
    return handler_index.get(leaf)


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


def _split_top_level_args(text: str) -> list[str]:
    args: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: str | None = None
    escaped = False

    for ch in text:
        if quote:
            buf.append(ch)
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == quote:
                quote = None
            continue

        if ch in {'\"', "'", "`"}:
            quote = ch
            buf.append(ch)
            continue

        if ch in "([{":
            depth += 1
            buf.append(ch)
            continue

        if ch in ")]}":
            depth = max(0, depth - 1)
            buf.append(ch)
            continue

        if ch == "," and depth == 0:
            args.append("".join(buf).strip())
            buf = []
            continue

        buf.append(ch)

    tail = "".join(buf).strip()
    if tail:
        args.append(tail)
    return args


def _extract_if_condition(if_text: str) -> str:
    start = if_text.find("(")
    if start < 0:
        return ""

    depth = 0
    cond_start = -1
    for idx in range(start, len(if_text)):
        ch = if_text[idx]
        if ch == "(":
            if depth == 0:
                cond_start = idx + 1
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and cond_start >= 0:
                return if_text[cond_start:idx]
    return ""


def _extract_methods_from_condition(condition: str) -> list[str]:
    methods: list[str] = []
    for hit in _IF_CONDITION_METHOD_RE.finditer(condition):
        method = (hit.group("left") or hit.group("right") or "").upper()
        if method in _HTTP_METHOD_SET:
            methods.append(method)

    deduped: list[str] = []
    seen: set[str] = set()
    for method in methods:
        if method in seen:
            continue
        seen.add(method)
        deduped.append(method)
    return deduped


def _extract_path_from_condition(condition: str) -> str | None:
    hit = _IF_CONDITION_PATH_RE.search(condition)
    if not hit:
        return None
    raw = hit.group("left") or hit.group("right") or ""
    if not raw:
        return None
    return normalize_path(raw)


def _extract_first_handler_call(body: str) -> str | None:
    for hit in _HANDLER_CALL_RE.finditer(body):
        name = hit.group("handler") or ""
        if name.rsplit(".", 1)[-1] in {"if", "switch", "for", "while", "return"}:
            continue
        normalized = _normalize_handler_candidate(name)
        if normalized:
            return normalized
    return None


class NodejsTypescriptAdapter(FrameAdapter):
    """Node.js / TS 路由适配器。"""

    NAME = "nodejs_typescript"
    LANGUAGES = sorted(_TS_EXTENSIONS)
    TREE_SITTER_LANGUAGES = ["typescript", "javascript"]
    AST_PARADIGMS = [
        AST_PARADIGM_DECORATOR_METADATA,
        AST_PARADIGM_CALL_REGISTRATION,
        AST_PARADIGM_IMPERATIVE_DISPATCH,
    ]
    SUPPORTED_FRAMEWORKS = [
        "nestjs",
        "express",
        "fastify",
        "koa-router",
        "hono",
        "elysia",
        "restify",
        "node-native-http",
    ]

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
(function_declaration) @func_decl
(variable_declarator) @var_decl
(if_statement) @if_stmt
"""

    def _build_handler_index(
        self,
        source_bytes: bytes,
        captures: list[tuple[Any, str]],
    ) -> dict[str, Any]:
        handlers: dict[str, Any] = {}

        def _bind_handler(name: str, node: Any):
            if name and name not in handlers:
                handlers[name] = node

        for node, cap_name in captures:
            if cap_name == "func_decl":
                name_node = node.child_by_field_name("name")
                if name_node is None:
                    continue
                name = source_bytes[name_node.start_byte : name_node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                _bind_handler(name, node)
                continue

            if cap_name == "method":
                name_node = node.child_by_field_name("name")
                if name_node is None:
                    continue
                name = source_bytes[name_node.start_byte : name_node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                _bind_handler(name, node)

                class_node = _find_ancestor(node, {"class_declaration"})
                if class_node is not None:
                    class_name_node = class_node.child_by_field_name("name")
                    if class_name_node is not None:
                        class_name = source_bytes[
                            class_name_node.start_byte : class_name_node.end_byte
                        ].decode("utf-8", errors="replace")
                        _bind_handler(f"{class_name}.{name}", node)
                continue

            if cap_name == "var_decl":
                name_node = node.child_by_field_name("name")
                value_node = node.child_by_field_name("value")
                if name_node is None or value_node is None:
                    continue
                if value_node.type not in {
                    "arrow_function",
                    "function",
                    "function_expression",
                }:
                    continue
                name = source_bytes[name_node.start_byte : name_node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                _bind_handler(name, value_node)
        return handlers

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

    def _parse_call_routes(
        self,
        call_text: str,
        call_node: Any,
        handler_index: dict[str, Any],
    ) -> list[tuple[str, str, Any]]:
        routes: list[tuple[str, str, Any]] = []
        for hit in _CALL_ROUTE_RE.finditer(call_text):
            method = hit.group("verb").upper()
            path = normalize_path(hit.group("path"))

            handler_node = None
            open_paren = call_text.find("(")
            close_paren = call_text.rfind(")")
            if open_paren >= 0 and close_paren > open_paren:
                args_text = call_text[open_paren + 1 : close_paren]
                args = _split_top_level_args(args_text)
                if len(args) >= 2:
                    handler_node = _resolve_handler_node(handler_index, args[1].strip())

            snippet_node = call_node
            if handler_node is not None:
                snippet_node = handler_node
            elif call_node.parent is not None and call_node.parent.type in {
                "expression_statement",
                "lexical_declaration",
                "variable_declaration",
                "statement_block",
            }:
                snippet_node = call_node.parent
            routes.append((method, path, snippet_node))
        return routes

    def _parse_imperative_if_routes(
        self,
        if_text: str,
        if_node: Any,
        handler_index: dict[str, Any],
    ) -> list[tuple[str, str, Any]]:
        condition = _extract_if_condition(if_text)
        methods = _extract_methods_from_condition(condition)
        path = _extract_path_from_condition(condition)
        if not methods or not path:
            return []

        body = if_text[if_text.find(")") + 1 :] if ")" in if_text else if_text
        handler_name = _extract_first_handler_call(body)
        handler_node = _resolve_handler_node(handler_index, handler_name)
        snippet_node = handler_node or if_node

        return [(method, path, snippet_node) for method in methods]

    def _extract_routes_from_tree(
        self,
        source_file: Path,
        source_bytes: bytes,
        root_node: Any,
        captures: list[tuple[Any, str]],
    ) -> list[RouteSnippet]:
        _ = root_node

        snippets: list[RouteSnippet] = []
        handler_index = self._build_handler_index(source_bytes, captures)

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
                for method, path, snippet_node in self._parse_call_routes(
                    call_text,
                    node,
                    handler_index,
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

            elif cap_name == "if_stmt":
                if_text = source_bytes[node.start_byte : node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                for method, path, snippet_node in self._parse_imperative_if_routes(
                    if_text,
                    node,
                    handler_index,
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
