"""
框架适配器协议层（Tree-sitter 版）
================================

本模块定义了：
1. RouteSnippet：统一路由源码片段结构
2. FrameAdapter：框架适配器抽象基类
3. path_matches / iter_source_files：共享工具

核心目标：
- 适配器只负责“如何把 AST captures 还原为路由片段”
- 基类统一负责“遍历文件 -> AST 解析 -> Query 执行 -> 批量路由匹配”
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
import importlib
from pathlib import Path
from typing import Any, Iterator

from app.discovery.adapters.paradigms import normalize_ast_paradigms

try:
    _ts_module = importlib.import_module("tree_sitter_languages")
    get_language = getattr(_ts_module, "get_language")
    get_parser = getattr(_ts_module, "get_parser")
except Exception as exc:  # pragma: no cover - 依赖缺失时走降级路径
    get_language = None
    get_parser = None
    _TREE_SITTER_IMPORT_ERROR = str(exc)
else:
    _TREE_SITTER_IMPORT_ERROR = None


_LANGUAGE_CACHE: dict[str, Any] = {}
_PARSER_CACHE: dict[str, Any] = {}


def normalize_path(path: str) -> str:
    """标准化路由路径，统一以 / 开头。"""
    value = (path or "").strip()
    if not value:
        return "/"
    value = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", value)
    if not value.startswith("/"):
        value = f"/{value}"
    return value


def join_paths(prefix: str, path: str) -> str:
    """拼接路由前缀和子路径。"""
    left = normalize_path(prefix)
    right = normalize_path(path)
    if left == "/":
        return right
    if right == "/":
        return left
    return normalize_path(f"{left.rstrip('/')}/{right.lstrip('/')}")


@dataclass
class RouteSnippet:
    """从源码中提取出的路由函数片段（语言/框架无关）。"""

    route_id: str
    file_path: str
    start_line: int
    end_line: int
    code: str
    adapter_name: str = "unknown"
    method: str = "GET"
    path: str = "/"

    def __post_init__(self):
        self.method = (self.method or "GET").upper()
        self.path = normalize_path(self.path)
        if not self.route_id:
            self.route_id = f"{self.method}:{self.path}"

    def __repr__(self) -> str:
        return (
            f"<RouteSnippet {self.route_id} @ "
            f"{self.file_path}:{self.start_line}-{self.end_line} "
            f"[{self.adapter_name}] ({len(self.code)} chars)>"
        )

    def to_context_block(self, seq_idx: int = 1, total: int = 1) -> str:
        """格式化为注入 LLM 上下文的代码块（下游格式保持不变）。"""
        return (
            f"####### [{seq_idx}/{total}] {self.route_id} ##############\n"
            f"# 源码位置: {self.file_path} 第 {self.start_line}-{self.end_line} 行\n"
            f"{self.code}\n"
        )


def normalize_param_to_regex(path: str) -> str:
    """
    将路径参数转换为正则通配符 [^/]+，兼容以下参数风格：
    - OpenAPI: {id}
    - Express: :id
    """
    path = re.sub(r":(\w+)", r"{\1}", path)
    esc = re.escape(path)
    return re.sub(r"\\\{[^}]+\\\}", r"[^/]+", esc)


def path_matches(code_path: str, openapi_path: str) -> bool:
    """
    模糊路径匹配：判断代码声明路径是否对应 OpenAPI 路径。

    兼容两类场景：
    1. 完全一致（参数风格可不同）
    2. 代码声明缺少前缀（例如 router/controller prefix）
    """
    code_path = normalize_path(code_path)
    openapi_path = normalize_path(openapi_path)

    code_re = normalize_param_to_regex(code_path)
    target_re = normalize_param_to_regex(openapi_path)

    if re.fullmatch(target_re, code_path) or re.fullmatch(code_re, openapi_path):
        return True

    code_segs = code_path.strip("/").split("/")
    target_segs = openapi_path.strip("/").split("/")
    n_code = len(code_segs)
    n_target = len(target_segs)

    if n_code > 0 and n_code <= n_target:
        suffix_target_segs = target_segs[n_target - n_code :]
        suffix_target = "/" + "/".join(suffix_target_segs)
        suffix_target_re = normalize_param_to_regex(suffix_target)

        has_static_match = False
        for idx, code_seg in enumerate(code_segs):
            code_is_param = code_seg.startswith("{") or code_seg.startswith(":")
            target_seg = suffix_target_segs[idx]
            target_is_param = target_seg.startswith("{")
            if not code_is_param and not target_is_param:
                if code_seg.lower() == target_seg.lower():
                    has_static_match = True
                else:
                    has_static_match = False
                    break

        if has_static_match and re.fullmatch(suffix_target_re, code_path):
            return True

    return False


def iter_source_files(
    source_path: Path,
    extensions: set[str],
    exclude_dirs: set[str] | None = None,
) -> Iterator[Path]:
    """通用源码文件遍历工具，自动跳过常见噪音目录。"""
    if exclude_dirs is None:
        exclude_dirs = {
            "__pycache__",
            ".git",
            "venv",
            ".venv",
            "node_modules",
            "dist",
            "build",
            ".next",
            "out",
            "test",
            "tests",
            "spec",
            "__tests__",
            "alembic",
            "migrations",
            ".backup_migrations",
            ".pytest_cache",
            ".mypy_cache",
        }

    import os

    for root, dirs, files in os.walk(source_path):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for filename in sorted(files):
            fp = root_path / filename
            if fp.suffix.lower() in extensions:
                yield fp


class FrameAdapter(ABC):
    """
    框架适配器抽象基类（Tree-sitter 协议）。

    子类必须实现：
    - can_handle(source_path)
    - get_tree_sitter_query()
    - _extract_routes_from_tree(...)
    """

    NAME: str = "base"
    LANGUAGES: list[str] = []
    TREE_SITTER_LANGUAGES: list[str] = []
    AST_PARADIGMS: list[str] = []
    SUPPORTED_FRAMEWORKS: list[str] = []

    EXCLUDE_DIRS = {
        "__pycache__",
        ".git",
        "venv",
        ".venv",
        "node_modules",
        "dist",
        "build",
        ".next",
        "out",
        "test",
        "tests",
        "spec",
        "__tests__",
        "alembic",
        "migrations",
        ".backup_migrations",
        ".pytest_cache",
        ".mypy_cache",
    }

    def __init__(self, source_path: str):
        self.source_path = Path(source_path)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        """Structured adapter metadata for diagnostics and docs."""
        return {
            "name": cls.NAME,
            "languages": list(cls.LANGUAGES),
            "tree_sitter_languages": list(cls.TREE_SITTER_LANGUAGES),
            "ast_paradigms": normalize_ast_paradigms(cls.AST_PARADIGMS),
            "supported_frameworks": list(cls.SUPPORTED_FRAMEWORKS),
            "class": cls.__name__,
        }

    @classmethod
    @abstractmethod
    def can_handle(cls, source_path: Path) -> bool:
        """探针：判断目标目录是否属于该适配器支持的框架/语言。"""
        ...

    @abstractmethod
    def get_tree_sitter_query(self) -> str:
        """返回该适配器的 Tree-sitter S 表达式 Query。"""
        ...

    @abstractmethod
    def _extract_routes_from_tree(
        self,
        source_file: Path,
        source_bytes: bytes,
        root_node: Any,
        captures: list[tuple[Any, str]],
    ) -> list[RouteSnippet]:
        """将 Query captures 转换为 RouteSnippet 集合。"""
        ...

    def _fallback_extract_all_routes(self) -> list[RouteSnippet]:
        """Tree-sitter 不可用时的降级提取（子类可选覆写）。"""
        return []

    def _iter_source_files(self) -> Iterator[Path]:
        return iter_source_files(
            self.source_path,
            {ext.lower() for ext in self.LANGUAGES},
            self.EXCLUDE_DIRS,
        )

    def _resolve_tree_sitter_language_name(self) -> str | None:
        if not self.TREE_SITTER_LANGUAGES:
            return None
        if get_language is None or get_parser is None:
            return None

        self._ts_last_error = None

        for candidate in self.TREE_SITTER_LANGUAGES:
            if candidate in _LANGUAGE_CACHE and candidate in _PARSER_CACHE:
                return candidate
            try:
                _LANGUAGE_CACHE[candidate] = get_language(candidate)
                _PARSER_CACHE[candidate] = get_parser(candidate)
                return candidate
            except Exception as exc:
                self._ts_last_error = exc
                continue
        return None

    def _get_tree_sitter_components(self) -> tuple[Any, Any] | None:
        lang_name = self._resolve_tree_sitter_language_name()
        if not lang_name:
            detail = _TREE_SITTER_IMPORT_ERROR or str(getattr(self, "_ts_last_error", "") or "")
            if detail:
                print(
                    f"[FrameAdapter:{self.NAME}] ⚠️ Tree-sitter 依赖不可用: "
                    f"{detail}"
                )
            return None
        return _LANGUAGE_CACHE[lang_name], _PARSER_CACHE[lang_name]

    def _make_snippet(
        self,
        method: str,
        path: str,
        source_file: Path,
        source_bytes: bytes,
        node: Any,
        route_id: str | None = None,
    ) -> RouteSnippet:
        method_upper = method.upper()
        norm_path = normalize_path(path)
        rid = route_id or f"{method_upper}:{norm_path}"

        code = source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8", errors="replace"
        )

        try:
            rel_path = str(source_file.relative_to(self.source_path))
        except ValueError:
            rel_path = str(source_file)

        return RouteSnippet(
            route_id=rid,
            file_path=rel_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            code=code,
            adapter_name=self.NAME,
            method=method_upper,
            path=norm_path,
        )

    def _dedupe_snippets(self, snippets: list[RouteSnippet]) -> list[RouteSnippet]:
        seen: set[tuple[str, str, int, int]] = set()
        result: list[RouteSnippet] = []
        for snippet in snippets:
            key = (
                snippet.route_id,
                snippet.file_path,
                snippet.start_line,
                snippet.end_line,
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(snippet)
        return result

    def extract_all_routes(self) -> list[RouteSnippet]:
        """提取当前源码目录中可识别的全部路由。"""
        ts_components = self._get_tree_sitter_components()
        if ts_components is None:
            return self._fallback_extract_all_routes()

        language, parser = ts_components
        query_text = self.get_tree_sitter_query().strip()
        if not query_text:
            return self._fallback_extract_all_routes()

        try:
            query = language.query(query_text)
        except Exception as exc:
            print(f"[FrameAdapter:{self.NAME}] ⚠️ Query 编译失败: {exc}")
            return self._fallback_extract_all_routes()

        snippets: list[RouteSnippet] = []

        for source_file in self._iter_source_files():
            try:
                source_bytes = source_file.read_bytes()
            except Exception:
                continue

            try:
                tree = parser.parse(source_bytes)
            except Exception as exc:
                print(f"[FrameAdapter:{self.NAME}] ⚠️ AST 解析失败 {source_file}: {exc}")
                continue

            try:
                captures = query.captures(tree.root_node)
            except Exception as exc:
                print(f"[FrameAdapter:{self.NAME}] ⚠️ Query 执行失败 {source_file}: {exc}")
                captures = []

            try:
                file_snippets = self._extract_routes_from_tree(
                    source_file,
                    source_bytes,
                    tree.root_node,
                    captures,
                )
            except Exception as exc:
                print(f"[FrameAdapter:{self.NAME}] ⚠️ 路由提取失败 {source_file}: {exc}")
                file_snippets = []

            snippets.extend(file_snippets)

        return self._dedupe_snippets(snippets)

    def discover_routes(self) -> list[RouteSnippet]:
        """语义发现层统一入口：返回项目中可解析的全部路由。"""
        return self.extract_all_routes()

    def extract_route(self, method: str, path: str) -> RouteSnippet | None:
        """提取单条路由（默认复用 extract_batch）。"""
        route_id = f"{method.upper()}:{normalize_path(path)}"
        return self.extract_batch([(method, path)]).get(route_id)

    def extract_batch(
        self, routes: list[tuple[str, str]]
    ) -> dict[str, RouteSnippet | None]:
        """
        批量提取多条路由。

        重构后逻辑：
        1. 一次性遍历目录并提取全部 RouteSnippet
        2. 按 method/path 对每条目标路由做最佳匹配
        """
        discovered = self.extract_all_routes()

        by_exact: dict[str, list[RouteSnippet]] = {}
        for snippet in discovered:
            by_exact.setdefault(snippet.route_id, []).append(snippet)

        result: dict[str, RouteSnippet | None] = {}

        for method, path in routes:
            norm_method = method.upper()
            norm_path = normalize_path(path)
            route_id = f"{norm_method}:{norm_path}"

            exact_candidates = by_exact.get(route_id, [])
            if exact_candidates:
                result[route_id] = max(exact_candidates, key=lambda s: len(s.code))
                continue

            fuzzy_candidates = [
                snippet
                for snippet in discovered
                if snippet.method == norm_method and path_matches(snippet.path, norm_path)
            ]
            if fuzzy_candidates:
                result[route_id] = max(fuzzy_candidates, key=lambda s: len(s.code))
            else:
                result[route_id] = None

        return result

    def __repr__(self) -> str:
        return f"<FrameAdapter:{self.NAME} @ {self.source_path}>"
