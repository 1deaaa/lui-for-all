"""
Go Web 适配器（Tree-sitter 版）
=============================

覆盖：Gin / Echo / Fiber / Chi 常见链式路由注册风格。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.discovery.adapters.base import FrameAdapter, join_paths, normalize_path


_ROUTE_CALL_RE = re.compile(
    r"(?P<obj>[A-Za-z_]\w*)\s*\.\s*(?P<verb>GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|Get|Post|Put|Delete|Patch|Head|Options)\s*\(\s*\"(?P<path>[^\"]+)\"",
)
_GROUP_PREFIX_RE = re.compile(
    r"(?P<name>[A-Za-z_]\w*)\s*:?=\s*[A-Za-z_]\w*\s*\.\s*Group\s*\(\s*\"(?P<prefix>[^\"]+)\"",
)


class GoWebAdapter(FrameAdapter):
    """Go Web 框架路由适配器。"""

    NAME = "go_web"
    LANGUAGES = [".go"]
    TREE_SITTER_LANGUAGES = ["go"]

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
            if ".GET(" in text or ".Post(" in text or ".Group(" in text:
                return True

        return False

    def get_tree_sitter_query(self) -> str:
        return """
(call_expression) @call
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

        for node, cap_name in captures:
            if cap_name != "call":
                continue

            call_text = source_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            )

            for hit in _ROUTE_CALL_RE.finditer(call_text):
                method = hit.group("verb").upper()
                obj_name = hit.group("obj")
                path = normalize_path(hit.group("path"))
                if obj_name in group_prefixes:
                    path = join_paths(group_prefixes[obj_name], path)

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

        return snippets
