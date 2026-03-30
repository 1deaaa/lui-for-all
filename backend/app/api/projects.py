"""
项目 API 路由
处理项目导入、发现、能力图谱、删除等能力
"""

import asyncio
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session, get_session
from app.models.audit import Approval, HttpExecution, ModelCall, PolicyVerdictRecord
from app.models.project import CapabilityRecord, Project, RouteMapRecord
from app.models.session import Message, Session
from app.models.task import TaskEvent, TaskRun
from app.repositories.audit_repository import AuditRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.task_repository import TaskRepository

router = APIRouter()


class ProjectImportRequest(BaseModel):
    """项目导入请求"""

    name: str
    base_url: str
    openapi_url: str | None = None
    description: str | None = None
    username: str | None = Field(default=None, description="需要目标系统登录时填写的账号")
    password: str | None = Field(default=None, description="需要目标系统登录时填写的密码")
    source_path: str = Field(
        ...,
        description="目标项目本地源码目录的绝对路径",
    )


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
    progress: int = 0
    progress_message: str | None = None
    route_count: int | None = None
    capability_count: int | None = None
    error: str | None = None


def _extract_progress(project: Project) -> tuple[int, str | None]:
    metadata = project.metadata_ or {}
    return int(metadata.get("discovery_progress", 0)), metadata.get("discovery_message")


async def _update_project_progress(project_id: str, progress: int, message: str):
    async with async_session() as db:
        project = await ProjectRepository(db).get_by_id(project_id)
        if not project:
            return

        metadata = dict(project.metadata_ or {})
        metadata["discovery_progress"] = progress
        metadata["discovery_message"] = message
        project.metadata_ = metadata
        await db.commit()


async def _run_discovery_job(project_id: str):
    async with async_session() as db:
        project_repository = ProjectRepository(db)
        project = await project_repository.get_by_id(project_id)
        if not project:
            return

        try:
            from app.discovery.service import run_discovery

            openapi_path = "/openapi.json"
            if project.openapi_url:
                from urllib.parse import urlparse

                parsed = urlparse(project.openapi_url)
                openapi_path = parsed.path or "/openapi.json"

            await run_discovery(
                db,
                project_id,
                project.base_url,
                openapi_path,
                progress_callback=lambda percent, message: _update_project_progress(
                    project_id,
                    percent,
                    message,
                ),
                source_path=project.source_path,  # 传入本地源码路径
            )
        except Exception as e:
            project = await project_repository.get_by_id(project_id)
            if not project:
                return

            metadata = dict(project.metadata_ or {})
            metadata["discovery_progress"] = 0
            metadata["discovery_message"] = "项目建图失败"
            project.metadata_ = metadata
            project.discovery_status = "failed"
            project.discovery_error = str(e)
            await db.commit()


@router.post("/import", response_model=ProjectImportResponse)
async def import_project(
    request: ProjectImportRequest,
    db: AsyncSession = Depends(get_session),
):
    """导入新项目"""
    if not os.path.exists(request.source_path):
        raise HTTPException(
            status_code=400,
            detail=f"指定的本地源码路径不存在: {request.source_path}",
        )
    if not os.path.isdir(request.source_path):
        raise HTTPException(
            status_code=400,
            detail=f"源码路径必须是一个目录: {request.source_path}",
        )

    project_id = str(uuid.uuid4())

    project = Project(
        id=project_id,
        name=request.name,
        base_url=request.base_url,
        openapi_url=request.openapi_url,
        description=request.description,
        username=request.username,
        password=request.password,
        source_path=request.source_path,  # 存储本地源码路径
        discovery_status="pending",
        metadata_={
            "discovery_progress": 0,
            "discovery_message": "等待开始项目建图",
        },
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
            suffix = request.openapi_url if request.openapi_url.startswith("/") else f"/{request.openapi_url}"
            test_url = f"{test_url}{suffix}"
    else:
        test_url = f"{test_url}/openapi.json"

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            response = await client.get(test_url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                return {"status": "warning", "message": f"连接成功，但地址返回的不是一个 JSON ({content_type})"}

            return {"status": "success", "message": "连接与 OpenAPI 探索可用"}
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail=f"目标服务连接超时 ({test_url})。请查证地址是否可达或服务是否启动。")
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status in (401, 403):
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
    project = await ProjectRepository(db).get_by_id(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if project.discovery_status == "in_progress":
        progress, message = _extract_progress(project)
        return {
            "project_id": project_id,
            "status": "in_progress",
            "progress": progress,
            "message": message or "项目建图已在进行中",
        }

    metadata = dict(project.metadata_ or {})
    metadata["discovery_progress"] = 0
    metadata["discovery_message"] = "项目发现任务已启动"
    project.metadata_ = metadata
    project.discovery_status = "in_progress"
    project.discovery_error = None
    await db.commit()

    asyncio.create_task(_run_discovery_job(project_id))

    return {
        "project_id": project_id,
        "status": "in_progress",
        "progress": 0,
        "message": "项目发现任务已启动",
    }


@router.get("/{project_id}/status", response_model=DiscoveryStatusResponse)
async def get_discovery_status(
    project_id: str,
    db: AsyncSession = Depends(get_session),
):
    """获取发现状态"""
    project_repository = ProjectRepository(db)
    project = await project_repository.get_by_id(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    route_map = await project_repository.get_latest_route_map(project_id)
    capabilities = await project_repository.list_capabilities(project_id)
    progress, progress_message = _extract_progress(project)

    return DiscoveryStatusResponse(
        project_id=project_id,
        name=project.name,
        base_url=project.base_url,
        status=project.discovery_status,
        progress=progress,
        progress_message=progress_message,
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
    route_map = await ProjectRepository(db).get_latest_route_map(project_id)

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
    capabilities = await ProjectRepository(db).list_capabilities(project_id)

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
    projects = await ProjectRepository(db).list_all()

    return {
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "base_url": p.base_url,
                "discovery_status": p.discovery_status,
                "discovery_progress": int((p.metadata_ or {}).get("discovery_progress", 0)),
                "discovery_message": (p.metadata_ or {}).get("discovery_message"),
                "discovery_error": p.discovery_error,
                "model_version": p.model_version,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
            for p in projects
        ],
        "total": len(projects),
    }


class ProjectUpdateRequest(BaseModel):
    """项目信息修改请求"""
    name: str | None = None
    description: str | None = None


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    db: AsyncSession = Depends(get_session),
):
    """修改项目名称或描述（前端手动纠正 AI 生成内容）"""
    project = await ProjectRepository(db).get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if request.name is not None:
        project.name = request.name
    if request.description is not None:
        project.description = request.description

    await db.commit()
    return {"project_id": project_id, "status": "updated"}


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_session),
):
    """删除项目及其相关记录"""
    project_repository = ProjectRepository(db)
    session_repository = SessionRepository(db)
    task_repository = TaskRepository(db)
    audit_repository = AuditRepository(db)
    project = await project_repository.get_by_id(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    task_ids = await task_repository.task_ids_by_project(project_id)
    await session_repository.delete_by_project(project_id)
    await audit_repository.delete_by_task_ids(task_ids)
    await task_repository.delete_by_project(project_id)
    await project_repository.delete_graph_data(project_id)
    await project_repository.delete_by_id(project_id)
    await db.commit()

    return {"project_id": project_id, "status": "deleted"}
