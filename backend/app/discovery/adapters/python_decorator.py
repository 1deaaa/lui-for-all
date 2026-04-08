"""
Python 装饰器风格适配器（Tree-sitter 版）
========================================

覆盖：FastAPI / Flask / Sanic / Starlette / Litestar 等装饰器路由风格。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.discovery.adapters.base import FrameAdapter, RouteSnippet, join_paths, normalize_path
from app.discovery.adapters.paradigms import AST_PARADIGM_DECORATOR_METADATA


_KNOWN_FRAMEWORKS = frozenset(
    {
        "fastapi",
        "flask",
        "sanic",
        "starlette",
        "litestar",
        "aiohttp",
        "bottle",
        "quart",
    }
)

_DECORATOR_PROBE_RE = re.compile(
    r"@\w[\w.]*\.(get|post|put|delete|patch|options|head|route|api_route)\s*\(",
    re.IGNORECASE,
)

_METHOD_DECORATOR_RE = re.compile(
    r"@(?:(?P<target>[\w.]+)\.)?(?P<verb>get|post|put|delete|patch|options|head)\s*\((?P<args>.*?)\)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_ROUTE_DECORATOR_RE = re.compile(
    r"@(?:(?P<target>[\w.]+)\.)?(?:route|api_route)\s*\((?P<args>.*?)\)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_METHODS_ARG_RE = re.compile(r"methods\s*=\s*\[([^\]]+)\]", re.IGNORECASE)
_STRING_RE = re.compile(r"['\"]([^'\"]*)['\"]")
_PATH_KW_RE = re.compile(
    r"(?:path|url|rule)\s*=\s*(['\"][^'\"]*['\"])",
    re.IGNORECASE,
)
_ROUTER_PREFIX_RE = re.compile(
    r"(?P<name>[A-Za-z_]\w*)\s*=\s*(?:APIRouter|Blueprint)\((?P<args>.*?)\)",
    re.DOTALL,
)
_PREFIX_IN_ARGS_RE = re.compile(
    r"(?:prefix|url_prefix)\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}


def _unquote(value: str) -> str:
    data = value.strip()
    if len(data) >= 2 and data[0] in {'"', "'"} and data[-1] == data[0]:
        return data[1:-1]
    return data


def _extract_path_from_args(args: str) -> str:
    kw = _PATH_KW_RE.search(args)
    if kw:
        return normalize_path(_unquote(kw.group(1)))
    m = _STRING_RE.search(args)
    if m:
        return normalize_path(m.group(1))
    return "/"


def _extract_methods_from_args(args: str) -> list[str]:
    match = _METHODS_ARG_RE.search(args)
    if not match:
        return ["GET"]

    raw = match.group(1)
    names = [token.upper() for token in re.findall(r"[A-Za-z]+", raw)]
    methods = [name for name in names if name in _HTTP_METHODS]
    return methods or ["GET"]


def _extract_router_prefixes(source_text: str) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for hit in _ROUTER_PREFIX_RE.finditer(source_text):
        name = hit.group("name")
        args = hit.group("args")
        pref = _PREFIX_IN_ARGS_RE.search(args)
        if pref:
            prefixes[name] = normalize_path(pref.group(1))
    return prefixes


class PythonDecoratorAdapter(FrameAdapter):
    """Python 装饰器路由适配器。"""

    NAME = "python_decorator"
    LANGUAGES = [".py"]
    TREE_SITTER_LANGUAGES = ["python"]
    AST_PARADIGMS = [AST_PARADIGM_DECORATOR_METADATA]
    SUPPORTED_FRAMEWORKS = [
        "fastapi",
        "flask",
        "sanic",
        "starlette",
        "litestar",
        "aiohttp",
        "bottle",
        "quart",
    ]

    @classmethod
    def can_handle(cls, source_path: Path) -> bool:
        for dep_name in (
            "requirements.txt",
            "requirements-base.txt",
            "pyproject.toml",
            "Pipfile",
            "setup.py",
        ):
            dep_path = source_path / dep_name
            if not dep_path.exists():
                continue
            try:
                content = dep_path.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue
            if any(fw in content for fw in _KNOWN_FRAMEWORKS):
                return True

        scanned = 0
        for py_file in source_path.rglob("*.py"):
            if scanned >= 30:
                break
            scanned += 1
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if _DECORATOR_PROBE_RE.search(content):
                return True

        return False

    def get_tree_sitter_query(self) -> str:
        return """
(
  (decorated_definition
    (decorator) @decorator
    definition: (function_definition) @handler) @decorated
)
"""

    def _parse_decorator_routes(
        self,
        decorator_text: str,
        router_prefixes: dict[str, str],
    ) -> list[tuple[str, str]]:
        text = decorator_text.strip()

        m = _METHOD_DECORATOR_RE.match(text)
        if m:
            target = (m.group("target") or "").split(".")[0]
            method = (m.group("verb") or "GET").upper()
            path = _extract_path_from_args(m.group("args") or "")
            if target in router_prefixes:
                path = join_paths(router_prefixes[target], path)
            return [(method, path)]

        r = _ROUTE_DECORATOR_RE.match(text)
        if r:
            target = (r.group("target") or "").split(".")[0]
            args = r.group("args") or ""
            path = _extract_path_from_args(args)
            methods = _extract_methods_from_args(args)
            if target in router_prefixes:
                path = join_paths(router_prefixes[target], path)
            return [(method, path) for method in methods]

        return []

    def _extract_routes_from_tree(
        self,
        source_file: Path,
        source_bytes: bytes,
        root_node: Any,
        captures: list[tuple[Any, str]],
    ) -> list[RouteSnippet]:
        _ = root_node

        source_text = source_bytes.decode("utf-8", errors="replace")
        router_prefixes = _extract_router_prefixes(source_text)

        groups: dict[tuple[int, int], dict[str, Any]] = {}

        for node, cap_name in captures:
            group_node = None
            if cap_name == "decorated":
                group_node = node
            elif node.parent is not None and node.parent.type == "decorated_definition":
                group_node = node.parent

            if group_node is None:
                continue

            key = (group_node.start_byte, group_node.end_byte)
            bucket = groups.setdefault(
                key,
                {
                    "snippet_node": group_node,
                    "decorators": [],
                },
            )

            if cap_name == "decorator":
                bucket["decorators"].append(node)

        snippets: list[RouteSnippet] = []

        for bucket in groups.values():
            snippet_node = bucket["snippet_node"]
            decorators = bucket["decorators"]

            for dec_node in decorators:
                dec_text = source_bytes[dec_node.start_byte : dec_node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                for method, path in self._parse_decorator_routes(dec_text, router_prefixes):
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
        """依赖缺失时回退到正则扫描，保证功能可用。"""
        snippets: list[RouteSnippet] = []

        for py_file in self._iter_source_files():
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = content.splitlines()
            prefixes = _extract_router_prefixes(content)

            idx = 0
            while idx < len(lines):
                line = lines[idx]
                if not line.strip().startswith("@"):
                    idx += 1
                    continue

                dec_text = line.strip()
                routes = self._parse_decorator_routes(dec_text, prefixes)
                if not routes:
                    idx += 1
                    continue

                def_idx = None
                for j in range(idx, min(idx + 20, len(lines))):
                    if re.match(r"\s*(async\s+)?def\s+\w+", lines[j]):
                        def_idx = j
                        break

                if def_idx is None:
                    idx += 1
                    continue

                base_indent = len(lines[def_idx]) - len(lines[def_idx].lstrip())
                start = idx
                while start > 0 and lines[start - 1].strip().startswith("@"):
                    start -= 1

                end = def_idx
                k = def_idx + 1
                while k < len(lines):
                    stripped = lines[k].strip()
                    if not stripped or stripped.startswith("#"):
                        k += 1
                        continue
                    curr_indent = len(lines[k]) - len(lines[k].lstrip())
                    if curr_indent <= base_indent:
                        break
                    end = k
                    k += 1

                code = "\n".join(lines[start : end + 1])
                try:
                    rel_path = str(py_file.relative_to(self.source_path))
                except ValueError:
                    rel_path = str(py_file)

                for method, path in routes:
                    snippets.append(
                        RouteSnippet(
                            route_id=f"{method}:{normalize_path(path)}",
                            file_path=rel_path,
                            start_line=start + 1,
                            end_line=end + 1,
                            code=code,
                            adapter_name=self.NAME,
                            method=method,
                            path=path,
                        )
                    )

                idx = end + 1

        return snippets
