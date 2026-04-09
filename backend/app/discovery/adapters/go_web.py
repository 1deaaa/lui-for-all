"""
Go Web 适配器（Tree-sitter 版）
=============================

覆盖：Gin / Echo / Fiber / Chi 常见链式路由注册风格。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.discovery.adapters.base import FrameAdapter, RouteSnippet, join_paths, normalize_path
from app.discovery.adapters.paradigms import (
    AST_PARADIGM_CALL_REGISTRATION,
    AST_PARADIGM_IMPERATIVE_DISPATCH,
)


_ROUTE_CALL_RE = re.compile(
    r"(?P<obj>[A-Za-z_]\w*)\s*\.\s*(?P<verb>GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|Get|Post|Put|Delete|Patch|Head|Options)\s*\(\s*\"(?P<path>[^\"]+)\"",
)
_HANDLE_FUNC_RE = re.compile(
    r"(?P<obj>[A-Za-z_]\w*|http)\s*\.\s*HandleFunc\s*\(\s*\"(?P<pattern>[^\"]+)\"\s*,\s*(?P<handler>[A-Za-z_]\w*)",
)
_GROUP_PREFIX_RE = re.compile(
    r"(?P<name>[A-Za-z_]\w*)\s*:?=\s*[A-Za-z_]\w*\s*\.\s*Group\s*\(\s*\"(?P<prefix>[^\"]+)\"",
)

_GO_METHOD_LITERAL_RE = re.compile(
    r"(?:r|req)\.Method\s*==\s*\"(?P<left>[A-Za-z]+)\"|\"(?P<right>[A-Za-z]+)\"\s*==\s*(?:r|req)\.Method"
)
_GO_METHOD_CONST_RE = re.compile(r"http\.Method(?P<name>Get|Post|Put|Delete|Patch|Head|Options)")
_GO_PATH_COMPARE_RE = re.compile(
    r"(?:r|req)\.URL\.Path\s*==\s*\"(?P<left>/[^\"]*)\"|\"(?P<right>/[^\"]*)\"\s*==\s*(?:r|req)\.URL\.Path"
)
_GO_HANDLER_CALL_RE = re.compile(
    r"(?:return\s+)?(?P<handler>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\("
)
_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


def _normalize_handler_name(raw: str | None) -> str | None:
    if not raw:
        return None
    name = re.sub(r"\s+", "", raw.strip())
    name = name.replace("?.", ".")
    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", name):
        return None
    return name.rsplit(".", 1)[-1]


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


def _extract_http_methods(text: str) -> list[str]:
    methods: list[str] = []

    for hit in _GO_METHOD_CONST_RE.finditer(text):
        method = (hit.group("name") or "").upper()
        if method in _HTTP_METHODS:
            methods.append(method)

    for hit in _GO_METHOD_LITERAL_RE.finditer(text):
        method = (hit.group("left") or hit.group("right") or "").upper()
        if method in _HTTP_METHODS:
            methods.append(method)

    deduped: list[str] = []
    seen: set[str] = set()
    for method in methods:
        if method in seen:
            continue
        seen.add(method)
        deduped.append(method)
    return deduped


def _extract_http_path(text: str) -> str | None:
    hit = _GO_PATH_COMPARE_RE.search(text)
    if not hit:
        return None
    raw = hit.group("left") or hit.group("right") or ""
    if not raw:
        return None
    return normalize_path(raw)


def _split_method_and_path_pattern(raw: str) -> tuple[str | None, str]:
    text = (raw or "").strip()
    if not text:
        return None, "/"

    parts = text.split(None, 1)
    if len(parts) == 2 and parts[0].upper() in _HTTP_METHODS:
        return parts[0].upper(), normalize_path(parts[1])

    return None, normalize_path(text)


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

        if ch in {'"', "'", "`"}:
            quote = ch
            buf.append(ch)
            continue

        if ch in "([{" :
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


def _extract_first_handler_call(body: str) -> str | None:
    for hit in _GO_HANDLER_CALL_RE.finditer(body):
        name = _normalize_handler_name(hit.group("handler"))
        if not name:
            continue
        if name in {"if", "switch", "for", "func", "return"}:
            continue
        return name
    return None


def _find_matching_go_brace(text: str, open_brace_index: int) -> int:
    depth = 0
    for idx in range(open_brace_index, len(text)):
        ch = text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def _extract_go_function_snippet(
    source_text: str,
    source_file: Path,
    method: str,
    path: str,
    function_name: str,
) -> RouteSnippet | None:
    pattern = re.compile(
        rf"(?m)^\s*func(?:\s*\([^)]*\))?\s+{re.escape(function_name)}\s*\("
    )
    match = pattern.search(source_text)
    if not match:
        return None

    open_brace_index = source_text.find("{", match.end())
    if open_brace_index < 0:
        return None

    close_brace_index = _find_matching_go_brace(source_text, open_brace_index)
    if close_brace_index < 0:
        return None

    start_offset = match.start()
    end_offset = close_brace_index + 1
    code = source_text[start_offset:end_offset]
    start_line = source_text.count("\n", 0, start_offset) + 1
    end_line = source_text.count("\n", 0, end_offset) + 1

    return RouteSnippet(
        route_id=f"{method.upper()}:{normalize_path(path)}",
        file_path=source_file.name,
        start_line=start_line,
        end_line=end_line,
        code=code,
        adapter_name="go_web",
        method=method,
        path=path,
    )


class GoWebAdapter(FrameAdapter):
    """Go Web 框架路由适配器。"""

    NAME = "go_web"
    LANGUAGES = [".go"]
    TREE_SITTER_LANGUAGES = ["go"]
    AST_PARADIGMS = [AST_PARADIGM_CALL_REGISTRATION, AST_PARADIGM_IMPERATIVE_DISPATCH]
    SUPPORTED_FRAMEWORKS = ["gin", "echo", "fiber", "chi", "net-http"]

    @classmethod
    def can_handle(cls, source_path: Path) -> bool:
        go_mod = source_path / "go.mod"
        if go_mod.exists():
            try:
                content = go_mod.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                content = ""
            if any(
                fw in content
                for fw in (
                    "github.com/gin-gonic/gin",
                    "github.com/labstack/echo",
                    "github.com/gofiber/fiber",
                    "github.com/go-chi/chi",
                )
            ):
                return True

        scanned = 0
        for go_file in source_path.rglob("*.go"):
            if scanned >= 40:
                break
            scanned += 1
            try:
                text = go_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if (
                ".GET(" in text
                or ".Post(" in text
                or ".Group(" in text
                or ".HandleFunc(" in text
                or "r.Method" in text
            ):
                return True

        return False

    def get_tree_sitter_query(self) -> str:
        return """
(call_expression) @call
(function_declaration) @function
(if_statement) @if_stmt
"""

    def _extract_routes_from_tree(
        self,
        source_file: Path,
        source_bytes: bytes,
        root_node: Any,
        captures: list[tuple[Any, str]],
    ):
        _ = root_node

        file_text = source_bytes.decode("utf-8", errors="replace")
        group_prefixes = {
            hit.group("name"): normalize_path(hit.group("prefix"))
            for hit in _GROUP_PREFIX_RE.finditer(file_text)
        }

        snippets = []
        function_nodes: dict[str, Any] = {}

        for node, cap_name in captures:
            if cap_name not in {"function", "func_decl"}:
                continue
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            fn_name = source_bytes[name_node.start_byte : name_node.end_byte].decode(
                "utf-8", errors="replace"
            )
            function_nodes[fn_name] = node

        for node, cap_name in captures:
            if cap_name != "call":
                continue

            call_text = source_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            )
            call_args_text = ""
            open_paren = call_text.find("(")
            close_paren = call_text.rfind(")")
            if open_paren >= 0 and close_paren > open_paren:
                call_args_text = call_text[open_paren + 1 : close_paren]
            call_args = _split_top_level_args(call_args_text) if call_args_text else []

            for hit in _ROUTE_CALL_RE.finditer(call_text):
                method = hit.group("verb").upper()
                obj_name = hit.group("obj")
                path = normalize_path(hit.group("path"))
                if obj_name in group_prefixes:
                    path = join_paths(group_prefixes[obj_name], path)

                handler_name = None
                if len(call_args) >= 2:
                    candidate = call_args[1].strip()
                    handler_name = _normalize_handler_name(candidate)

                if handler_name:
                    source_snippet = _extract_go_function_snippet(
                        file_text,
                        source_file,
                        method=method,
                        path=path,
                        function_name=handler_name,
                    )
                    if source_snippet is not None:
                        snippets.append(source_snippet)
                        continue

                node_for_snippet = node.parent if node.parent is not None else node
                snippets.append(
                    self._make_snippet(
                        method=method,
                        path=path,
                        source_file=source_file,
                        source_bytes=source_bytes,
                        node=node_for_snippet,
                    )
                )

            for hit in _HANDLE_FUNC_RE.finditer(call_text):
                pattern = hit.group("pattern")
                handler_name = hit.group("handler")
                method_from_pattern, path = _split_method_and_path_pattern(pattern)
                methods = [method_from_pattern] if method_from_pattern else ["GET"]

                source_snippet = _extract_go_function_snippet(
                    file_text,
                    source_file,
                    method=methods[0],
                    path=path,
                    function_name=handler_name,
                )
                if source_snippet is not None:
                    for method in methods:
                        if method == methods[0]:
                            snippets.append(source_snippet)
                        else:
                            snippets.append(
                                RouteSnippet(
                                    route_id=f"{method.upper()}:{normalize_path(path)}",
                                    file_path=source_snippet.file_path,
                                    start_line=source_snippet.start_line,
                                    end_line=source_snippet.end_line,
                                    code=source_snippet.code,
                                    adapter_name=source_snippet.adapter_name,
                                    method=method,
                                    path=path,
                                )
                            )
                    continue

                node_for_snippet = (
                    function_nodes.get(handler_name)
                    or node.parent
                    or node
                )
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

        for node, cap_name in captures:
            if cap_name != "if_stmt":
                continue

            if_text = source_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            )
            condition_text = _extract_if_condition(if_text)
            methods = _extract_http_methods(condition_text)
            path = _extract_http_path(condition_text)
            if not methods or not path:
                continue

            body_text = if_text[if_text.find(")") + 1 :] if ")" in if_text else if_text
            handler_name = _extract_first_handler_call(body_text)
            node_for_snippet = function_nodes.get(handler_name) or node

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
