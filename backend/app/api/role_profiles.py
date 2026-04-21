"""
角色画像 API 路由
处理角色画像的 CRUD、权限探测触发、可达性修正
"""

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.project import RoleProfile, RouteAccessibility
from app.repositories.project_repository import ProjectRepository

router = APIRouter()


# ── 请求/响应模型 ──

class CreateRoleProfileRequest(BaseModel):
    """创建角色画像请求"""
    name: str = Field(description="角色名，如 普通用户、管理员")
    description: str | None = None
    probe_username: str = Field(description="探测时使用的目标系统用户名")
    probe_password: str = Field(description="探测时使用的目标系统密码")


class UpdateAccessibilityRequest(BaseModel):
    """手动修正可达性请求"""
    accessible: bool = Field(description="是否可达")


class SetDefaultRoleRequest(BaseModel):
    """设置默认角色画像请求"""
    role_profile_id: str | None = Field(description="角色画像 ID，null 表示取消默认")


# ── 端点 ──

@router.get("/{project_id}/role-profiles")
async def list_role_profiles(
    project_id: str,
    db: AsyncSession = Depends(get_session),
):
    """列出项目的所有角色画像"""
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    profiles = await repo.list_role_profiles(project_id)
    default_id = project.default_role_profile_id
    return {
        "profiles": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "probe_username": p.probe_username,
                "probe_status": p.probe_status,
                "probe_error": p.probe_error,
                "route_count": p.route_count,
                "accessible_count": p.accessible_count,
                "is_default": p.id == default_id if default_id else False,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
            for p in profiles
        ],
        "total": len(profiles),
    }


@router.post("/{project_id}/role-profiles")
async def create_role_profile(
    project_id: str,
    request: CreateRoleProfileRequest,
    db: AsyncSession = Depends(get_session),
):
    """创建角色画像并触发权限探测"""
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if not project.login_route_id:
        raise HTTPException(status_code=400, detail="项目未配置登录接口，无法创建角色画像")

    profile_id = str(uuid.uuid4())
    profile = RoleProfile(
        id=profile_id,
        project_id=project_id,
        name=request.name,
        description=request.description,
        probe_username=request.probe_username,
        probe_password=request.probe_password,
        probe_status="pending",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await repo.add_role_profile(profile)
    await db.commit()

    # 异步触发探测
    asyncio.create_task(_run_probe_async(profile_id))

    return {
        "id": profile_id,
        "name": request.name,
        "probe_status": "pending",
        "message": "角色画像已创建，权限探测已异步启动",
    }


@router.get("/{project_id}/role-profiles/{profile_id}")
async def get_role_profile(
    project_id: str,
    profile_id: str,
    db: AsyncSession = Depends(get_session),
):
    """查看角色画像详情（含可达路由列表）"""
    repo = ProjectRepository(db)
    profile = await repo.get_role_profile(profile_id)
    if not profile or profile.project_id != project_id:
        raise HTTPException(status_code=404, detail="角色画像不存在")

    accessibility = await repo.list_route_accessibility(project_id, profile_id)

    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "probe_username": profile.probe_username,
        "probe_status": profile.probe_status,
        "probe_error": profile.probe_error,
        "route_count": profile.route_count,
        "accessible_count": profile.accessible_count,
        "accessibility": [
            {
                "id": a.id,
                "route_id": a.route_id,
                "accessible": a.accessible,
                "probe_status_code": a.probe_status_code,
                "probe_method": a.probe_method,
                "manually_overridden": a.manually_overridden,
                "updated_at": a.updated_at.isoformat(),
            }
            for a in accessibility
        ],
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


@router.post("/{project_id}/role-profiles/{profile_id}/reprobe")
async def reprobe_role_profile(
    project_id: str,
    profile_id: str,
    db: AsyncSession = Depends(get_session),
):
    """重新触发权限探测"""
    repo = ProjectRepository(db)
    profile = await repo.get_role_profile(profile_id)
    if not profile or profile.project_id != project_id:
        raise HTTPException(status_code=404, detail="角色画像不存在")

    if profile.probe_status == "probing":
        raise HTTPException(status_code=409, detail="探测正在进行中，请稍后")

    # 重置状态
    profile.probe_status = "pending"
    profile.probe_error = None
    await db.commit()

    # 异步触发探测
    asyncio.create_task(_run_probe_async(profile_id))

    return {"id": profile_id, "probe_status": "pending", "message": "权限探测已重新启动"}


@router.patch("/{project_id}/role-profiles/{profile_id}/accessibility/{route_id:path}")
async def update_accessibility(
    project_id: str,
    profile_id: str,
    route_id: str,
    request: UpdateAccessibilityRequest,
    db: AsyncSession = Depends(get_session),
):
    """手动修正单条路由的可达性"""
    repo = ProjectRepository(db)
    record = await repo.get_route_accessibility(project_id, profile_id, route_id)

    if not record:
        # 不存在则创建
        record = RouteAccessibility(
            id=str(uuid.uuid4()),
            project_id=project_id,
            role_profile_id=profile_id,
            route_id=route_id,
            accessible=request.accessible,
            probe_status_code=None,
            probe_method=None,
            manually_overridden=True,
            updated_at=datetime.now(UTC),
        )
        db.add(record)
    else:
        record.accessible = request.accessible
        record.manually_overridden = True
        record.updated_at = datetime.now(UTC)

    # 更新画像统计
    profile = await repo.get_role_profile(profile_id)
    if profile:
        all_records = await repo.list_route_accessibility(project_id, profile_id)
        profile.accessible_count = sum(1 for r in all_records if r.accessible)
        profile.route_count = len(all_records)

    await db.commit()
    return {"route_id": route_id, "accessible": request.accessible, "manually_overridden": True}


@router.delete("/{project_id}/role-profiles/{profile_id}")
async def delete_role_profile(
    project_id: str,
    profile_id: str,
    db: AsyncSession = Depends(get_session),
):
    """删除角色画像及关联的可达性数据"""
    repo = ProjectRepository(db)
    profile = await repo.get_role_profile(profile_id)
    if not profile or profile.project_id != project_id:
        raise HTTPException(status_code=404, detail="角色画像不存在")

    # 如果是默认画像，先清除默认引用
    project = await repo.get_by_id(project_id)
    if project and project.default_role_profile_id == profile_id:
        project.default_role_profile_id = None

    # 删除可达性记录
    accessibility = await repo.list_route_accessibility(project_id, profile_id)
    for a in accessibility:
        await db.delete(a)

    await db.delete(profile)
    await db.commit()
    return {"id": profile_id, "message": "角色画像已删除"}


@router.put("/{project_id}/default-role")
async def set_default_role(
    project_id: str,
    request: SetDefaultRoleRequest,
    db: AsyncSession = Depends(get_session),
):
    """设置项目的默认用户角色画像"""
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if request.role_profile_id:
        profile = await repo.get_role_profile(request.role_profile_id)
        if not profile or profile.project_id != project_id:
            raise HTTPException(status_code=404, detail="角色画像不存在")
        if profile.probe_status != "completed":
            raise HTTPException(status_code=400, detail="只能将已完成探测的角色画像设为默认")

    project.default_role_profile_id = request.role_profile_id
    await db.commit()
    return {"project_id": project_id, "default_role_profile_id": request.role_profile_id}


# ── 内部辅助 ──

async def _run_probe_async(profile_id: str):
    """在独立数据库会话中异步执行探测"""
    from app.db import async_session
    from app.services.probe_service import run_probe

    async with async_session() as db:
        try:
            await run_probe(db, profile_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[probe] 异步探测失败: {e}")
