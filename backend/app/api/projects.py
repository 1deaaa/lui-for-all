"""
项目 API 路由
处理项目导入、发现、能力图谱等
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.project import CapabilityRecord, Project, RouteMapRecord
from app.schemas.capability import Capability, CapabilityGraph
from app.schemas.route_map import HttpMethod, RouteInfo, RouteMap

router = APIRouter()


# ==================== Pydantic 请求模型 ====================


class ProjectImportRequest(BaseModel):
    """项目导入请求"""

    name: str
    base_url: str
    openapi_url: str | None = None
    description: str | None = None
    username: str | None = Field(default=None, description="需要目标系统登录时填写的账号")
    password: str | None = Field(default=None, description="需要目标系统登录时填写的密码")

class TestConnectionRequest(BaseModel):
    """连通性测试请求"""
    base_url: str
    openapi_url: str | None = None


class ProjectImportResponse(BaseModel):
    """项目导入响应"""

    project_id: str
    name: str
    status: str


class DiscoveryStatusResponse(BaseModel):
    """发现状态响应"""

    project_id: str
    name: str | None = None
    base_url: str | None = None
    status: str
    route_count: int | None = None
    capability_count: int | None = None
    error: str | None = None


# ==================== API 端点 ====================


@router.post("/import", response_model=ProjectImportResponse)
async def import_project(
    request: ProjectImportRequest,
    db: AsyncSession = Depends(get_session),
):
    """导入新项目"""
    project_id = str(uuid.uuid4())

    project = Project(
        id=project_id,
        name=request.name,
        base_url=request.base_url,
        openapi_url=request.openapi_url,
        description=request.description,
        username=request.username,
        password=request.password,
        discovery_status="pending",
    )

    db.add(project)
    await db.commit()

    return ProjectImportResponse(
        project_id=project_id,
        name=request.name,
        status="pending",
    )


@router.post("/test-connection")
async def test_connection(request: TestConnectionRequest):
    """测试指定基地址或 OpenApiURL 的连通性"""
    import httpx
    
    test_url = request.base_url.rstrip("/")
    if request.openapi_url:
        if request.openapi_url.startswith("http"):
            test_url = request.openapi_url
        else:
            test_url = f"{test_url}{request.openapi_url if request.openapi_url.startswith('/') else '/' + request.openapi_url}"
    else:
        test_url = f"{test_url}/openapi.json"
        
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            response = await client.get(test_url)
            # 在某些情况下，只要不报连接超时且有响应，即可视为连通。
            response.raise_for_status()
            
            # 若确保能拿到 JSON，可以试着验证
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                return {"status": "warning", "message": f"连接成功，但地址返回的不是一个 JSON ({content_type})"}
                
            return {"status": "success", "message": "连接与 OpenAPI 探索可用"}
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail=f"目标服务连接超时 ({test_url})。请查证地址是否可达或服务是否启动。")
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status in (401, 403):
            # 这点很关键，说明端口是对的，只是拦截了。这可以算连通。
            return {"status": "warning", "message": f"接口存在跨域拦截或强制授权阻断 (状态码: {status})。确认这是否符合预期。"}
        raise HTTPException(status_code=status, detail=f"访问目标时遭到了错误状态码: HTTP {status} ({test_url})")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"连接失败或服务未启动: {str(e)}")


@router.post("/{project_id}/discover")
async def trigger_discovery(
    project_id: str,
    db: AsyncSession = Depends(get_session),
):
    """触发项目发现"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 更新状态为进行中
    project.discovery_status = "in_progress"
    await db.commit()

    try:
        # 执行实际的发现逻辑
        from app.discovery.service import run_discovery

        openapi_path = "/openapi.json"
        if project.openapi_url:
            # 从完整 URL 提取路径
            from urllib.parse import urlparse
            parsed = urlparse(project.openapi_url)
            openapi_path = parsed.path

        route_map, capability_graph = await run_discovery(
            db, project_id, project.base_url, openapi_path
        )

        return {
            "project_id": project_id,
            "status": "completed",
            "route_count": len(route_map.routes),
            "capability_count": len(capability_graph.capabilities),
            "message": "发现任务完成",
        }
    except Exception as e:
        # 更新状态为失败
        project.discovery_status = "failed"
        project.discovery_error = str(e)
        await db.commit()

        raise HTTPException(status_code=500, detail=f"发现失败: {str(e)}")


@router.get("/{project_id}/status", response_model=DiscoveryStatusResponse)
async def get_discovery_status(
    project_id: str,
    db: AsyncSession = Depends(get_session),
):
    """获取发现状态"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 获取路由和能力数量
    route_result = await db.execute(
        select(RouteMapRecord).where(RouteMapRecord.project_id == project_id)
    )
    route_map = route_result.scalar_one_or_none()

    capability_result = await db.execute(
        select(CapabilityRecord).where(CapabilityRecord.project_id == project_id)
    )
    capabilities = capability_result.scalars().all()

    return DiscoveryStatusResponse(
        project_id=project_id,
        name=project.name,
        base_url=project.base_url,
        status=project.discovery_status,
        route_count=len(route_map.routes) if route_map else 0,
        capability_count=len(capabilities),
        error=project.discovery_error,
    )


@router.get("/{project_id}/route-map")
async def get_route_map(
    project_id: str,
    db: AsyncSession = Depends(get_session),
):
    """获取路由地图"""
    result = await db.execute(
        select(RouteMapRecord)
        .where(RouteMapRecord.project_id == project_id)
        .order_by(RouteMapRecord.created_at.desc())
    )
    route_map = result.scalar_one_or_none()

    if not route_map:
        raise HTTPException(status_code=404, detail="路由地图不存在")

    return {
        "project_id": project_id,
        "version": route_map.version,
        "routes": route_map.routes,
        "schemas": route_map.schemas,
        "route_count": route_map.route_count,
        "source": route_map.source,
        "created_at": route_map.created_at.isoformat(),
    }


@router.get("/{project_id}/capabilities")
async def get_capabilities(
    project_id: str,
    db: AsyncSession = Depends(get_session),
):
    """获取能力图谱"""
    result = await db.execute(
        select(CapabilityRecord).where(CapabilityRecord.project_id == project_id)
    )
    capabilities = result.scalars().all()

    if not capabilities:
        raise HTTPException(status_code=404, detail="能力图谱不存在")

    return {
        "project_id": project_id,
        "capabilities": [
            {
                "capability_id": c.capability_id,
                "name": c.name,
                "description": c.description,
                "domain": c.domain,
                "backed_by_routes": c.backed_by_routes,
                "user_intent_examples": c.user_intent_examples,
                "permission_level": c.permission_level,
                "safety_level": c.safety_level,
                "data_sensitivity": c.data_sensitivity,
                "requires_confirmation": c.requires_confirmation,
                "best_modalities": c.best_modalities,
                "parameter_hints": c.parameter_hints,
                "ai_usage_guidelines": c.ai_usage_guidelines,
                "source_code_analysis": c.source_code_analysis,
            }
            for c in capabilities
        ],
        "total": len(capabilities),
    }


@router.get("/")
async def list_projects(
    db: AsyncSession = Depends(get_session),
):
    """列出所有项目"""
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()

    return {
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "base_url": p.base_url,
                "discovery_status": p.discovery_status,
                "discovery_error": p.discovery_error,
                "model_version": p.model_version,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
            for p in projects
        ],
        "total": len(projects),
    }
