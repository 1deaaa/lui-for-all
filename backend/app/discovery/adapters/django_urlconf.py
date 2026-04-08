"""
Django URLConf 适配器（Tree-sitter 版）
=====================================

覆盖 Django 路由集中配置风格：
- path(...)
- re_path(...)
- include(...)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.discovery.adapters.base import FrameAdapter, RouteSnippet, join_paths, normalize_path
from app.discovery.adapters.paradigms import (
    AST_PARADIGM_DECORATOR_METADATA,
    AST_PARADIGM_ROUTE_TABLE,
)


_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
_METHOD_NAMES = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

_PATH_CALL_RE = re.compile(r"^\s*(path|re_path|url)\s*\(", re.DOTALL)
_INCLUDE_RE = re.compile(r"^\s*include\s*\((.*)\)\s*$", re.DOTALL)

_REQUIRE_HTTP_METHODS_RE = re.compile(
    r"@\s*require_http_methods\s*\(\s*\[([^\]]+)\]\s*\)",
    re.IGNORECASE,
)
_API_VIEW_RE = re.compile(r"@\s*api_view\s*\(\s*\[([^\]]+)\]\s*\)", re.IGNORECASE)

_REQUIRE_SINGLE_METHOD_MAP = {
    "require_GET": ["GET"],
    "require_POST": ["POST"],
    "require_PUT": ["PUT"],
    "require_PATCH": ["PATCH"],
    "require_DELETE": ["DELETE"],
    "require_safe": ["GET", "HEAD"],
}


@dataclass
class _ViewDef:
    name: str
    module: str
    file_path: Path
    node: Any
    methods: list[str]


@dataclass
class _ImportMaps:
    module_aliases: dict[str, str]
    object_aliases: dict[str, str]


def _strip_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] in {'"', "'"} and text[-1] == text[0]:
        return text[1:-1]
    if len(text) >= 3 and text[0] in {'r', 'R'} and text[1] in {'"', "'"} and text[-1] == text[1]:
        return text[2:-1]
    return text


def _extract_string_literal(expr: str) -> str | None:
    expr = expr.strip()
    if not expr:
        return None

    if expr[0] in {'"', "'"} and expr[-1] == expr[0]:
        return expr[1:-1]

    if len(expr) >= 3 and expr[0] in {'r', 'R'} and expr[1] in {'"', "'"} and expr[-1] == expr[1]:
        return expr[2:-1]

    return None


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

        if ch in {'"', "'"}:
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


def _extract_call_arguments(call_text: str) -> list[str]:
    start = call_text.find("(")
    end = call_text.rfind(")")
    if start < 0 or end <= start:
        return []
    return _split_top_level_args(call_text[start + 1 : end])


def _convert_django_route(raw_route: str, is_regex: bool) -> str:
    route = raw_route.strip()
    if is_regex:
        route = route.lstrip("^").rstrip("$")
        route = re.sub(r"\(\?P<([A-Za-z_]\w*)>[^)]+\)", r"{\1}", route)
        route = re.sub(r"\([^)]*\)", "{param}", route)
        route = route.replace("\\/", "/")
    else:
        route = re.sub(r"<(?:(?:[A-Za-z_][A-Za-z0-9_]*):)?([A-Za-z_][A-Za-z0-9_]*)>", r"{\1}", route)

    return normalize_path(route)


def _extract_methods_from_decorator_text(decorator_lines: list[str]) -> list[str]:
    if not decorator_lines:
        return ["GET"]

    joined = "\n".join(decorator_lines)

    methods: list[str] = []

    mm = _REQUIRE_HTTP_METHODS_RE.search(joined)
    if mm:
        methods.extend(token.upper() for token in re.findall(r"[A-Za-z]+", mm.group(1)))

    am = _API_VIEW_RE.search(joined)
    if am:
        methods.extend(token.upper() for token in re.findall(r"[A-Za-z]+", am.group(1)))

    for dec_name, dec_methods in _REQUIRE_SINGLE_METHOD_MAP.items():
        if re.search(rf"@\s*{re.escape(dec_name)}\b", joined):
            methods.extend(dec_methods)

    normalized = [m for m in methods if m in _HTTP_METHODS]
    if normalized:
        deduped = sorted(set(normalized), key=lambda x: _METHOD_NAMES.index(x))
        return deduped

    return ["GET"]


def _resolve_relative_module(current_module: str, imported_module: str) -> str:
    if not imported_module.startswith("."):
        return imported_module

    package_parts = current_module.split(".")[:-1]
    dots = len(imported_module) - len(imported_module.lstrip("."))
    rest = imported_module[dots:]

    keep = max(0, len(package_parts) - (dots - 1))
    base = package_parts[:keep]

    if rest:
        return ".".join(base + rest.split("."))
    return ".".join(base)


def _module_name_from_path(root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(root)
    no_ext = rel.with_suffix("")
    parts = list(no_ext.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _collect_import_maps(source_text: str, current_module: str) -> _ImportMaps:
    module_aliases: dict[str, str] = {}
    object_aliases: dict[str, str] = {}

    for line in source_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        m_from = re.match(r"from\s+([\.\w]+)\s+import\s+(.+)", stripped)
        if m_from:
            src_mod = _resolve_relative_module(current_module, m_from.group(1).strip())
            imported = m_from.group(2).strip()
            for item in _split_top_level_args(imported):
                part = item.strip()
                if not part or part == "*":
                    continue
                m_alias = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s+as\s+([A-Za-z_][A-Za-z0-9_]*)", part)
                if m_alias:
                    name = m_alias.group(1)
                    alias = m_alias.group(2)
                else:
                    name = part
                    alias = part

                fq = f"{src_mod}.{name}" if src_mod else name
                object_aliases[alias] = fq
                module_aliases.setdefault(alias, fq)
            continue

        m_import = re.match(r"import\s+([\.\w]+)(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*))?", stripped)
        if m_import:
            mod = _resolve_relative_module(current_module, m_import.group(1).strip())
            alias = m_import.group(2) or mod.split(".")[-1]
            module_aliases[alias] = mod

    return _ImportMaps(module_aliases=module_aliases, object_aliases=object_aliases)


class DjangoUrlconfAdapter(FrameAdapter):
    """Django urls.py 集中路由适配器。"""

    NAME = "django_urlconf"
    LANGUAGES = [".py"]
    TREE_SITTER_LANGUAGES = ["python"]
    AST_PARADIGMS = [AST_PARADIGM_ROUTE_TABLE, AST_PARADIGM_DECORATOR_METADATA]
    SUPPORTED_FRAMEWORKS = ["django", "django-rest-framework"]

    @classmethod
    def can_handle(cls, source_path: Path) -> bool:
        manage_py = source_path / "manage.py"
        if manage_py.exists():
            try:
                text = manage_py.read_text(encoding="utf-8", errors="ignore")
                if "DJANGO_SETTINGS_MODULE" in text or "django.core.management" in text:
                    return True
            except Exception:
                pass

        for dep_file in ("requirements.txt", "pyproject.toml", "Pipfile", "setup.py"):
            fp = source_path / dep_file
            if not fp.exists():
                continue
            try:
                content = fp.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue
            if "django" in content:
                return True

        for urls_file in source_path.rglob("urls.py"):
            try:
                content = urls_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if "urlpatterns" in content and ("path(" in content or "re_path(" in content):
                return True

        return False

    def get_tree_sitter_query(self) -> str:
        return """
(function_definition) @function
(class_definition) @class
(call) @call
"""

    def _extract_routes_from_tree(
        self,
        source_file: Path,
        source_bytes: bytes,
        root_node: Any,
        captures: list[tuple[Any, str]],
    ) -> list[RouteSnippet]:
        # Django 适配器走项目级解析，此处保留抽象方法实现。
        _ = source_file, source_bytes, root_node, captures
        return []

    def extract_all_routes(self) -> list[RouteSnippet]:
        ts_components = self._get_tree_sitter_components()
        if ts_components is None:
            return self._fallback_extract_all_routes()

        language, parser = ts_components

        try:
            def_query = language.query("""
(function_definition) @function
(class_definition) @class
""")
            call_query = language.query("(call) @call")
        except Exception as exc:
            print(f"[FrameAdapter:{self.NAME}] ⚠️ Query 编译失败: {exc}")
            return self._fallback_extract_all_routes()

        py_files = list(self._iter_source_files())
        module_to_file: dict[str, Path] = {}
        file_to_module: dict[Path, str] = {}

        for file_path in py_files:
            try:
                mod = _module_name_from_path(self.source_path, file_path)
            except Exception:
                continue
            module_to_file[mod] = file_path
            file_to_module[file_path] = mod

        view_defs_by_fq: dict[str, _ViewDef] = {}
        view_defs_by_name: dict[str, list[_ViewDef]] = {}

        parsed_cache: dict[Path, tuple[bytes, Any]] = {}

        for file_path in py_files:
            try:
                source_bytes = file_path.read_bytes()
                tree = parser.parse(source_bytes)
            except Exception:
                continue

            parsed_cache[file_path] = (source_bytes, tree)
            module = file_to_module.get(file_path, "")
            lines = source_bytes.decode("utf-8", errors="replace").splitlines()

            for node, cap_name in def_query.captures(tree.root_node):
                if cap_name not in {"function", "class"}:
                    continue

                name_node = node.child_by_field_name("name")
                if name_node is None:
                    continue
                name = source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")

                methods = ["GET"]
                if cap_name == "function":
                    start_line = node.start_point[0]
                    decorator_lines: list[str] = []
                    cursor = start_line - 1
                    while cursor >= 0:
                        ln = lines[cursor].strip()
                        if ln.startswith("@"):
                            decorator_lines.insert(0, ln)
                            cursor -= 1
                            continue
                        if not ln or ln.startswith("#"):
                            cursor -= 1
                            continue
                        break
                    methods = _extract_methods_from_decorator_text(decorator_lines)
                else:
                    class_text = source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
                    found = [m.upper() for m in re.findall(r"^\s*def\s+(get|post|put|patch|delete|head|options)\s*\(", class_text, re.IGNORECASE | re.MULTILINE)]
                    methods = sorted(set(found), key=lambda x: _METHOD_NAMES.index(x)) if found else ["GET"]

                view_def = _ViewDef(
                    name=name,
                    module=module,
                    file_path=file_path,
                    node=node,
                    methods=methods,
                )

                fq = f"{module}.{name}" if module else name
                view_defs_by_fq[fq] = view_def
                view_defs_by_name.setdefault(name, []).append(view_def)

        snippets: list[RouteSnippet] = []
        visited_include: set[tuple[Path, str]] = set()

        def resolve_view(
            view_expr: str,
            import_maps: _ImportMaps,
            current_module: str,
        ) -> tuple[_ViewDef | None, list[str] | None]:
            expr = view_expr.strip()
            explicit_methods: list[str] | None = None

            # DRF ViewSet: SomeViewSet.as_view({'get': 'list', ...})
            as_view_match = re.match(r"(.+?)\.as_view\((.*)\)$", expr)
            if as_view_match:
                expr = as_view_match.group(1).strip()
                inside = as_view_match.group(2).strip()
                if inside.startswith("{"):
                    keys = [k.upper() for k in re.findall(r"['\"]([A-Za-z]+)['\"]\s*:", inside)]
                    keys = [k for k in keys if k in _HTTP_METHODS]
                    if keys:
                        explicit_methods = sorted(set(keys), key=lambda x: _METHOD_NAMES.index(x))

            token = expr
            if "." in token:
                first, rest = token.split(".", 1)
                if first in import_maps.module_aliases:
                    mod = import_maps.module_aliases[first]
                    fq = f"{mod}.{rest}"
                    if fq in view_defs_by_fq:
                        return view_defs_by_fq[fq], explicit_methods

                fq_direct = token
                if fq_direct in view_defs_by_fq:
                    return view_defs_by_fq[fq_direct], explicit_methods

            if token in import_maps.object_aliases:
                fq = import_maps.object_aliases[token]
                if fq in view_defs_by_fq:
                    return view_defs_by_fq[fq], explicit_methods

            # 同包 views 回退
            pkg = current_module.rsplit(".", 1)[0] if "." in current_module else ""
            if pkg:
                candidate = f"{pkg}.views.{token}"
                if candidate in view_defs_by_fq:
                    return view_defs_by_fq[candidate], explicit_methods

            defs = view_defs_by_name.get(token, [])
            if len(defs) == 1:
                return defs[0], explicit_methods

            return None, explicit_methods

        def extract_include_module(view_expr: str) -> str | None:
            mm = _INCLUDE_RE.match(view_expr.strip())
            if not mm:
                return None
            args_text = mm.group(1)
            args = _split_top_level_args(args_text)
            if not args:
                return None

            first = args[0].strip()
            # include(("app.urls", "ns"), namespace="...")
            if first.startswith("(") and first.endswith(")"):
                inner = _split_top_level_args(first[1:-1])
                if inner:
                    first = inner[0].strip()

            module_str = _extract_string_literal(first)
            return module_str

        def walk_urlconf(urls_file: Path, prefix: str = "/"):
            key = (urls_file, normalize_path(prefix))
            if key in visited_include:
                return
            visited_include.add(key)

            if urls_file not in parsed_cache:
                try:
                    source_bytes = urls_file.read_bytes()
                    tree = parser.parse(source_bytes)
                    parsed_cache[urls_file] = (source_bytes, tree)
                except Exception:
                    return

            source_bytes, tree = parsed_cache[urls_file]
            current_module = file_to_module.get(urls_file, _module_name_from_path(self.source_path, urls_file))
            source_text = source_bytes.decode("utf-8", errors="replace")
            import_maps = _collect_import_maps(source_text, current_module)

            for call_node, cap_name in call_query.captures(tree.root_node):
                if cap_name != "call":
                    continue

                fn_node = call_node.child_by_field_name("function")
                if fn_node is None:
                    continue
                fn_text = source_bytes[fn_node.start_byte : fn_node.end_byte].decode("utf-8", errors="replace")
                if fn_text not in {"path", "re_path", "url"}:
                    continue

                call_text = source_bytes[call_node.start_byte : call_node.end_byte].decode("utf-8", errors="replace")
                if not _PATH_CALL_RE.match(call_text):
                    continue

                args = _extract_call_arguments(call_text)
                if len(args) < 2:
                    continue

                route_raw_literal = args[0].strip()
                route_raw = _extract_string_literal(route_raw_literal)
                if route_raw is None:
                    continue

                route_part = _convert_django_route(route_raw, is_regex=(fn_text in {"re_path", "url"}))
                full_path = join_paths(prefix, route_part)

                view_expr = args[1].strip()
                include_module = extract_include_module(view_expr)
                if include_module:
                    include_module_resolved = _resolve_relative_module(current_module, include_module)
                    include_file = module_to_file.get(include_module_resolved)
                    if include_file is None:
                        # 兼容 include("app.urls") -> module path 直接命中不到时尝试补 .urls
                        maybe = f"{include_module_resolved}.urls"
                        include_file = module_to_file.get(maybe)
                    if include_file is not None:
                        walk_urlconf(include_file, full_path)
                    continue

                view_def, explicit_methods = resolve_view(view_expr, import_maps, current_module)
                if view_def is None:
                    continue

                methods = explicit_methods or view_def.methods or ["GET"]
                methods = [m for m in methods if m in _HTTP_METHODS] or ["GET"]

                vd_source_bytes, _ = parsed_cache.get(view_def.file_path, (None, None))
                if vd_source_bytes is None:
                    try:
                        vd_source_bytes = view_def.file_path.read_bytes()
                    except Exception:
                        continue

                for method in methods:
                    snippets.append(
                        self._make_snippet(
                            method=method,
                            path=full_path,
                            source_file=view_def.file_path,
                            source_bytes=vd_source_bytes,
                            node=view_def.node,
                        )
                    )

        for file_path in py_files:
            if file_path.name == "urls.py":
                walk_urlconf(file_path, "/")

        return self._dedupe_snippets(snippets)
