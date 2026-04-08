"""
Java Spring Boot 适配器（Tree-sitter 版）
=======================================

覆盖：Spring MVC / Spring Boot 注解路由风格。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.discovery.adapters.base import FrameAdapter, join_paths, normalize_path


_HTTP_MAPPING_RE = re.compile(
    r"@(?P<verb>Get|Post|Put|Delete|Patch|Request|RequestMapping)Mapping\s*\((?P<args>.*?)\)",
    re.IGNORECASE | re.DOTALL,
)

_DIRECT_MAPPING_RE = re.compile(
    r"@(?P<verb>Get|Post|Put|Delete|Patch)Mapping\s*\((?P<args>.*?)\)",
    re.IGNORECASE | re.DOTALL,
)

_REQUEST_MAPPING_RE = re.compile(
    r"@RequestMapping\s*\((?P<args>.*?)\)",
    re.IGNORECASE | re.DOTALL,
)

_REQUEST_METHOD_RE = re.compile(r"RequestMethod\.([A-Za-z]+)")
_STRING_RE = re.compile(r"['\"]([^'\"]+)['\"]")


class JavaSpringAdapter(FrameAdapter):
    """Spring Boot 注解路由适配器。"""

    NAME = "java_spring"
    LANGUAGES = [".java"]
    TREE_SITTER_LANGUAGES = ["java"]

    @classmethod
    def can_handle(cls, source_path: Path) -> bool:
        for build_file in ("pom.xml", "build.gradle", "build.gradle.kts"):
            p = source_path / build_file
            if not p.exists():
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue
            if "spring-boot" in content or "spring-web" in content:
                return True

        scanned = 0
        for java_file in source_path.rglob("*.java"):
            if scanned >= 40:
                break
            scanned += 1
            try:
                text = java_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if "@RestController" in text or "@RequestMapping" in text or "@GetMapping" in text:
                return True

        return False

    def get_tree_sitter_query(self) -> str:
        return """
(method_declaration) @method
(class_declaration) @class
"""

    def _extract_path_from_args(self, args: str) -> str:
        kw = re.search(r"(?:path|value)\s*=\s*(['\"][^'\"]+['\"])", args)
        if kw:
            token = kw.group(1).strip()
            return normalize_path(token[1:-1])

        first = _STRING_RE.search(args)
        if first:
            return normalize_path(first.group(1))

        return "/"

    def _extract_class_prefix(self, source_bytes: bytes, class_node: Any) -> str:
        text = source_bytes[class_node.start_byte : class_node.end_byte].decode(
            "utf-8", errors="replace"
        )
        rm = _REQUEST_MAPPING_RE.search(text)
        if not rm:
            return "/"
        return self._extract_path_from_args(rm.group("args") or "")

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

        class_prefix_cache: dict[tuple[int, int], str] = {}
        for class_node in class_nodes:
            key = (class_node.start_byte, class_node.end_byte)
            class_prefix_cache[key] = self._extract_class_prefix(source_bytes, class_node)

        snippets = []

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

            # 1) @GetMapping / @PostMapping...
            for hit in _DIRECT_MAPPING_RE.finditer(method_text):
                method = hit.group("verb").upper()
                args = hit.group("args") or ""
                sub_path = self._extract_path_from_args(args)
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

            # 2) @RequestMapping(method=..., path=...)
            for hit in _REQUEST_MAPPING_RE.finditer(method_text):
                args = hit.group("args") or ""
                methods = [m.upper() for m in _REQUEST_METHOD_RE.findall(args)]
                methods = [m for m in methods if m in {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}]
                if not methods:
                    methods = ["GET"]

                sub_path = self._extract_path_from_args(args)
                full_path = join_paths(prefix, sub_path)

                for method in methods:
                    snippets.append(
                        self._make_snippet(
                            method=method,
                            path=full_path,
                            source_file=source_file,
                            source_bytes=source_bytes,
                            node=method_node,
                        )
                    )

        return snippets
