"""
发现服务
协调 OpenAPI 摄取和能力图谱生成
"""

import uuid
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.capability_builder import build_capability_graph
from app.discovery.enrichers.project_context import generate_project_context
from app.discovery.openapi_ingestor import ingest_openapi
from app.models.project import CapabilityRecord, Project, RouteMapRecord
from app.schemas.capability import CapabilityGraph
from app.schemas.route_map import RouteMap


class DiscoveryService:
    """项目发现服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def discover_project(
        self,
        project_id: str,
        base_url: str,
        openapi_path: str = "/openapi.json",
        progress_callback: Callable[[int, str], Awaitable[None]] | None = None,
        source_path: str | None = None,
    ) -> tuple[RouteMap, CapabilityGraph]:
        """执行项目发现。source_path 可选，提供则启用路由函数精准提取"""
        async def report(percent: int, message: str):
            if progress_callback:
                await progress_callback(percent, message)

        await report(5, "正在拉取 OpenAPI 文档")

        # 1. 摄取 OpenAPI
        route_map = await ingest_openapi(base_url, openapi_path)
        route_map.project_id = project_id

        await report(20, f"OpenAPI 解析完成，共发现 {len(route_map.routes)} 条路由")

        await report(25, f"开始推断项目的全局业务上下文边界")
        global_context = await generate_project_context(route_map, source_path, self.db)
        await report(30, f"全局推断结果：{global_context[:30]}...")

        # 2. 构建能力图谱 (AI 过程)
        capability_graph = await build_capability_graph(
            route_map,
            progress_callback=report,
            source_path=source_path,
            global_context=global_context,
        )

        await report(90, "能力图谱已生成，正在写入数据库")

        # 3. 保存路由地图
        route_map_record = RouteMapRecord(
            id=str(uuid.uuid4()),
            project_id=project_id,
            version=route_map.version,
            routes=[r.model_dump() for r in route_map.routes],
            schemas=route_map.schemas,
            route_count=len(route_map.routes),
            source=route_map.source,
        )
        self.db.add(route_map_record)

        # 4. 保存能力图谱
        for cap in capability_graph.capabilities:
            cap_record = CapabilityRecord(
                id=str(uuid.uuid4()),
                project_id=project_id,
                graph_version=capability_graph.version,
                capability_id=cap.capability_id,
                name=cap.name,
                description=cap.description,
                summary=cap.summary,  # 新增超短摘要
                domain=cap.domain.value,
                backed_by_routes=[r.model_dump() for r in cap.backed_by_routes],
                user_intent_examples=cap.user_intent_examples,
                permission_level=cap.required_permission_level.value,
                safety_level=cap.safety_level.value,
                data_sensitivity=cap.data_sensitivity,
                requires_confirmation=cap.requires_confirmation,
                best_modalities=[m.value for m in cap.best_modalities],
                parameter_hints=cap.parameter_hints,
                ai_usage_guidelines=cap.ai_usage_guidelines,
                source_code_analysis=cap.source_code_analysis,
            )
            self.db.add(cap_record)

        # 5. 更新项目状态
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.discovery_status = "completed"
            project.route_map_version = route_map.version
            project.capability_graph_version = capability_graph.version

        await self.db.commit()

        # 建模阶段总结
        print(f"\n{'='*50}")
        print(f"🚀 项目建模完成: {project.name if project else project_id}")
        print(f"   - OpenAPI 接口总数: {len(route_map.routes)}")
        ai_cap_count = sum(1 for cap in capability_graph.capabilities if cap.source_code_analysis is not None)
        print(f"   - AI 精准识别接口: {ai_cap_count}")
        print(f"   - 规则降级接口: {len(route_map.routes) - ai_cap_count}")
        print(f"{'='*50}\n")

        await report(100, "项目建图完成")

        return route_map, capability_graph

    async def get_route_map(self, project_id: str) -> RouteMap | None:
        """获取项目的路由地图"""
        result = await self.db.execute(
            select(RouteMapRecord)
            .where(RouteMapRecord.project_id == project_id)
            .order_by(RouteMapRecord.created_at.desc())
        )
        record = result.scalar_one_or_none()

        if not record:
            return None

        # 重建 RouteMap
        from app.schemas.route_map import HttpMethod, RouteInfo

        routes = []
        for r in record.routes:
            route = RouteInfo(
                route_id=r["route_id"],
                path=r["path"],
                method=HttpMethod(r["method"]),
                operation_id=r.get("operation_id"),
                summary=r.get("summary"),
                description=r.get("description"),
                tags=r.get("tags", []),
                parameters=[],
                request_body_ref=r.get("request_body_ref"),
                responses=[],
                deprecated=r.get("deprecated", False),
                security=r.get("security", []),
            )
            routes.append(route)

        return RouteMap(
            project_id=project_id,
            version=record.version,
            base_url="",
            routes=routes,
            schemas=record.schemas,
            discovered_at=record.created_at.isoformat(),
            source=record.source,
        )

    async def get_capabilities(self, project_id: str) -> list[CapabilityRecord]:
        """获取项目的能力列表"""
        result = await self.db.execute(
            select(CapabilityRecord).where(CapabilityRecord.project_id == project_id)
        )
        return list(result.scalars().all())


async def run_discovery(
    db: AsyncSession,
    project_id: str,
    base_url: str,
    openapi_path: str = "/openapi.json",
    progress_callback: Callable[[int, str], Awaitable[None]] | None = None,
    source_path: str | None = None,
) -> tuple[RouteMap, CapabilityGraph]:
    """便捷函数：执行项目发现"""
    service = DiscoveryService(db)
    return await service.discover_project(
        project_id,
        base_url,
        openapi_path,
        progress_callback=progress_callback,
        source_path=source_path,
    )
