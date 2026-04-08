"""
语义路由摄取器（无 OpenAPI 兜底）
=================================

当目标系统未暴露 OpenAPI 时，使用 Tree-sitter 适配器直接从源码提取路由，
并生成 RouteMap，供后续能力建图流水线复用。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.discovery.route_extractor import RouteExtractor, RouteSnippet
from app.schemas.route_map import HttpMethod, RouteInfo, RouteMap


_ACTION_MAP = {
    "GET": "查询",
    "POST": "创建",
    "PUT": "更新",
    "PATCH": "修改",
    "DELETE": "删除",
    "HEAD": "读取",
    "OPTIONS": "探测",
}


def _summary_from_method_path(method: str, path: str) -> str:
    action = _ACTION_MAP.get(method.upper(), "操作")
    tail = path.strip("/").split("/")[-1] if path and path != "/" else "根路由"
    return f"{action}{tail}"


@dataclass
class SemanticIngestResult:
    """AST 语义摄取结果：路由地图 + 可复用源码片段。"""

    route_map: RouteMap
    route_snippets_by_route_id: dict[str, RouteSnippet]


class SemanticRouteIngestor:
    """基于 AST 的路由摄取器。"""

    def __init__(self, source_path: str, base_url: str = ""):
        self.source_path = source_path
        self.base_url = (base_url or "").rstrip("/")

    async def ingest(self) -> RouteMap:
        result = await self.ingest_with_snippets()
        return result.route_map

    async def ingest_with_snippets(self) -> SemanticIngestResult:
        extractor = RouteExtractor(self.source_path)
        snippets = extractor.extract_all_routes()

        if not snippets:
            raise ValueError(
                "未能从源码中提取任何路由，请检查 source_path 是否正确或补充适配器。"
            )

        routes: list[RouteInfo] = []
        seen_route_ids: set[str] = set()
        snippet_index: dict[str, RouteSnippet] = {}

        for snippet in snippets:
            method = snippet.method.upper()
            try:
                http_method = HttpMethod(method)
            except ValueError:
                continue

            route_id = f"{method}:{snippet.path}"

            best_snippet = snippet_index.get(route_id)
            if best_snippet is None or len(snippet.code) > len(best_snippet.code):
                snippet_index[route_id] = snippet

            if route_id in seen_route_ids:
                continue
            seen_route_ids.add(route_id)

            routes.append(
                RouteInfo(
                    route_id=route_id,
                    path=snippet.path,
                    method=http_method,
                    operation_id=None,
                    summary=_summary_from_method_path(method, snippet.path),
                    description=(
                        f"由 {snippet.adapter_name} 从源码 {snippet.file_path}:"
                        f"{snippet.start_line}-{snippet.end_line} 提取"
                    ),
                    tags=["ast"],
                    parameters=[],
                    request_body_ref=None,
                    request_body_fields=[],
                    responses=[],
                    response_is_streaming=False,
                    deprecated=False,
                    security=[],
                )
            )

        version = f"ast-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        route_map = RouteMap(
            project_id=str(uuid.uuid4()),
            version=version,
            base_url=self.base_url,
            routes=routes,
            schemas={},
            discovered_at=datetime.now(UTC).isoformat(),
            source="ast",
        )
        return SemanticIngestResult(
            route_map=route_map,
            route_snippets_by_route_id=snippet_index,
        )


async def ingest_semantic_routes(source_path: str, base_url: str = "") -> RouteMap:
    """便捷函数：执行 AST 语义路由摄取。"""
    ingestor = SemanticRouteIngestor(source_path=source_path, base_url=base_url)
    return await ingestor.ingest()


async def ingest_semantic_routes_with_snippets(
    source_path: str,
    base_url: str = "",
) -> SemanticIngestResult:
    """便捷函数：执行 AST 语义路由摄取并返回可复用片段缓存。"""
    ingestor = SemanticRouteIngestor(source_path=source_path, base_url=base_url)
    return await ingestor.ingest_with_snippets()
