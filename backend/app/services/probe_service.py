"""
权限探测服务
用指定用户凭据登录目标系统后，逐条探测路由可达性
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import RoleProfile, RouteAccessibility
from app.repositories.project_repository import ProjectRepository
from app.services.auth_session_service import AuthSessionService

logger = logging.getLogger(__name__)

# 探测间隔（秒），防止触发目标系统限流
_PROBE_INTERVAL = 0.2
# 探测超时（秒）
_PROBE_TIMEOUT = 10.0

# 可达状态码：认证通过，仅请求参数/资源不对
_ACCESSIBLE_CODES = {200, 201, 206, 400, 404, 405, 409, 422}
# 不可达状态码：无权访问
_DENIED_CODES = {401, 403}
# 5xx 重试次数
_5XX_RETRY = 1


def _classify_accessibility(status_code: int | None) -> bool | None:
    """根据 HTTP 状态码判定可达性

    Returns:
        True = 可达, False = 不可达, None = 不确定
    """
    if status_code is None:
        return None
    if status_code in _ACCESSIBLE_CODES:
        return True
    if status_code in _DENIED_CODES:
        return False
    if 500 <= status_code < 600:
        return None  # 服务端异常，不确定
    # 其他状态码默认视为可达（如 301 重定向等）
    return True


def _build_probe_path(path: str) -> str:
    """将路径参数占位符替换为探测用的虚拟值

    如 /api/items/{id} → /api/items/0
    """
    import re
    return re.sub(r'\{[^}]+\}', '0', path)


async def _login_for_probe(
    project_repo: ProjectRepository,
    project_id: str,
    username: str,
    password: str,
) -> AuthSessionService | None:
    """用探测凭据登录目标系统，返回认证会话服务"""
    project = await project_repo.get_by_id(project_id)
    if not project or not project.login_route_id:
        return None

    auth_svc = AuthSessionService()
    method_str, _, path = project.login_route_id.partition(":")
    if not path:
        return None

    url = f"{project.base_url.rstrip('/')}/{path.lstrip('/')}"
    body = {
        project.login_field_username or "username": username,
        project.login_field_password or "password": password,
    }

    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            resp = await client.request(
                method=method_str.upper() or "POST",
                url=url,
                json=body,
            )
            if resp.status_code >= 400:
                logger.warning(f"[probe] 登录失败: {resp.status_code}")
                return None

            # 捕获 token
            auth_svc.capture_token(resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {})
            auth_svc.capture_from_cookies(dict(resp.cookies))

            if not auth_svc.token:
                logger.warning("[probe] 登录成功但未捕获到 token")
                return None

            return auth_svc
    except Exception as e:
        logger.error(f"[probe] 登录异常: {e}")
        return None


async def run_probe(
    db: AsyncSession,
    profile_id: str,
) -> None:
    """执行权限探测，逐条探测路由可达性

    此函数为后台任务，由 API 端点触发后异步执行。
    """
    project_repo = ProjectRepository(db)
    profile = await project_repo.get_role_profile(profile_id)
    if not profile:
        logger.error(f"[probe] 角色画像不存在: {profile_id}")
        return

    # 更新状态为 probing
    profile.probe_status = "probing"
    profile.probe_error = None
    await db.commit()

    try:
        # 1. 登录目标系统
        auth_svc = await _login_for_probe(
            project_repo, profile.project_id,
            profile.probe_username, profile.probe_password,
        )
        if not auth_svc:
            profile.probe_status = "failed"
            profile.probe_error = "登录目标系统失败，请检查凭据和登录接口配置"
            await db.commit()
            return

        # 2. 获取路由地图
        route_map = await project_repo.get_latest_route_map(profile.project_id)
        if not route_map or not route_map.routes:
            profile.probe_status = "failed"
            profile.probe_error = "项目无可用路由地图，请先完成项目发现"
            await db.commit()
            return

        routes = route_map.routes

        # 3. 清除旧的可达性记录
        await project_repo.delete_route_accessibility_by_profile(profile_id)

        # 4. 逐条探测
        accessible_count = 0
        project = await project_repo.get_by_id(profile.project_id)
        base_url = project.base_url.rstrip("/") if project else ""

        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            for route_info in routes:
                method = route_info.get("method", "GET")
                path = route_info.get("path", "/")
                route_id = route_info.get("route_id", f"{method}:{path}")

                probe_path = _build_probe_path(path)
                url = f"{base_url}/{probe_path.lstrip('/')}"
                headers = auth_svc.build_headers()

                # 根据方法构建探测请求
                probe_method = method.upper()
                try:
                    if probe_method in ("POST", "PUT", "PATCH"):
                        resp = await client.request(
                            probe_method, url,
                            json={}, headers=headers,
                        )
                    elif probe_method == "DELETE":
                        resp = await client.request(
                            probe_method, url,
                            headers=headers,
                        )
                    else:  # GET, HEAD, OPTIONS
                        resp = await client.request(
                            probe_method, url,
                            headers=headers,
                        )

                    status_code = resp.status_code
                except Exception:
                    status_code = None

                accessible = _classify_accessibility(status_code)

                # 5xx 重试：可能是探测参数导致的假阴性，重试一次确认
                if accessible is None and status_code is not None and 500 <= status_code < 600:
                    await asyncio.sleep(_PROBE_INTERVAL * 2)
                    try:
                        if probe_method in ("POST", "PUT", "PATCH"):
                            retry_resp = await client.request(probe_method, url, json={}, headers=headers)
                        elif probe_method == "DELETE":
                            retry_resp = await client.request(probe_method, url, headers=headers)
                        else:
                            retry_resp = await client.request(probe_method, url, headers=headers)
                        retry_status = retry_resp.status_code
                        retry_class = _classify_accessibility(retry_status)
                        if retry_class is not None:
                            accessible = retry_class
                            status_code = retry_status
                    except Exception:
                        pass

                # 不确定的标记为不可达（安全优先），但保留 probe_status_code 供管理员手动修正
                is_accessible = accessible is True
                if is_accessible:
                    accessible_count += 1

                # 写入可达性记录
                record = RouteAccessibility(
                    id=str(uuid.uuid4()),
                    project_id=profile.project_id,
                    role_profile_id=profile_id,
                    route_id=route_id,
                    accessible=is_accessible,
                    probe_status_code=status_code,
                    probe_method=probe_method,
                    manually_overridden=False,
                    updated_at=datetime.now(UTC),
                )
                db.add(record)

                # 探测间隔
                await asyncio.sleep(_PROBE_INTERVAL)

        # 5. 更新画像统计
        profile.route_count = len(routes)
        profile.accessible_count = accessible_count
        profile.probe_status = "completed"
        await db.commit()

        logger.info(
            f"[probe] 探测完成: profile={profile_id}, "
            f"routes={len(routes)}, accessible={accessible_count}"
        )

    except Exception as e:
        logger.error(f"[probe] 探测异常: {e}")
        profile.probe_status = "failed"
        profile.probe_error = str(e)
        await db.commit()
