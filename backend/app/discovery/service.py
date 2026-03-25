"""
发现服务
协调 OpenAPI 摄取和能力图谱生成
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.capability_builder import build_capability_graph
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
    ) -> tuple[RouteMap, CapabilityGraph]:
        """执行项目发现"""
        # 1. 摄取 OpenAPI
        route_map = await ingest_openapi(base_url, openapi_path)
        route_map.project_id = project_id

        # 2. 构建能力图谱 (现为异步 AI 过程)
        capability_graph = await build_capability_graph(route_map)

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
) -> tuple[RouteMap, CapabilityGraph]:
    """便捷函数：执行项目发现"""
    service = DiscoveryService(db)
    return await service.discover_project(project_id, base_url, openapi_path)
