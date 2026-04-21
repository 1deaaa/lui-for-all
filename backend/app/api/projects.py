"""
项目 API 路由
处理项目导入、发现、能力图谱、删除等能力
"""

import asyncio
import os
import socket
import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PROJECT_ROOT
from app.db import async_session, get_session
from app.discovery.route_extractor import RouteExtractor
from app.models.audit import Approval, HttpExecution, ModelCall, PolicyVerdictRecord
from app.models.project import CapabilityRecord, Project, RouteMapRecord
from app.models.session import Message, Session
from app.models.task import TaskEvent, TaskRun
from app.repositories.audit_repository import AuditRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.task_repository import TaskRepository

router = APIRouter()


# ── Slug 生成工具 ──

_RESERVED_SLUGS = {"api", "docs", "redoc", "openapi.json", "health", "mcp", "assets", "login"}


def generate_slug(name: str) -> str:
    """从项目名生成 URL slug"""
    import re
    slug = name.lower().strip()
    slug = re.sub(r'[\s\-]+', '-', slug)
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    slug = slug.strip('-')[:48]
    return slug or 'project'


class ProjectImportRequest(BaseModel):
    """项目导入请求"""

    name: str
    base_url: str
    openapi_url: str | None = None
    description: str | None = None
    slug: str | None = Field(default=None, description="URL 友好标识，如 my-app，不填则自动从 name 生成")
    username: str | None = Field(default=None, description="需要目标系统登录时填写的账号")
    password: str | None = Field(default=None, description="需要目标系统登录时填写的密码")
    login_route_id: str | None = Field(default=None, description="登录接口 route_id，如 POST:/api/auth/login")
    login_field_username: str | None = Field(default="username", description="登录接口的用户名字段名")
    login_field_password: str | None = Field(default="password", description="登录接口的密码字段名")
    source_path: str = Field(
        ...,
        description="目标项目本地源码目录的绝对路径",
    )


class FetchRoutesRequest(BaseModel):
    """从 OpenAPI 地址拉取路由列表请求"""
    base_url: str
    openapi_url: str | None = None
    source_path: str | None = None


class VerifyLoginRequest(BaseModel):
    """验证登录接口请求"""
    base_url: str
    login_route_id: str
    username: str
    password: str
    body_field_username: str = Field(default="username", description="登录接口的用户名字段名")
    body_field_password: str = Field(default="password", description="登录接口的密码字段名")


class VerifySourcePathRequest(BaseModel):
    """源码路径验证请求"""

    source_path: str = Field(
        ...,
        description="目标项目本地源码目录的绝对路径",
    )


class TestConnectionRequest(BaseModel):
    """连通性测试请求"""

    base_url: str
    openapi_url: str | None = None
    source_path: str | None = None


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


class ProjectImportPreset(BaseModel):
    """项目导入预置项（用于前端一键填充）"""

    id: str
    name: str
    description: str
    base_url: str
    openapi_url: str
    source_path: str
    login_route_id: str
    username: str
    password: str
    body_field_username: str = "username"
    body_field_password: str = "password"
    available: bool = True


def _resolve_source_path(candidates: list[Path]) -> tuple[str, bool]:
    """从候选路径中选择第一个存在且为目录的路径。"""
    seen: set[str] = set()
    normalized: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            normalized.append(candidate)

    for candidate in normalized:
        if candidate.exists() and candidate.is_dir():
            return str(candidate), True

    return str(normalized[0]), False


def _verify_source_path(source_path: str) -> dict:
    """
    验证源码路径的可达性，返回结构化诊断信息。

    涵盖：路径存在性、是否为目录、可读性、框架检测、
    Docker 环境感知及卷挂载提示。
    """
    from app.discovery.adapters import get_adapter, list_adapters

    in_container = _is_running_in_container()
    path = Path(source_path)

    result: dict = {
        "source_path": source_path,
        "accessible": False,
        "is_directory": False,
        "readable": False,
        "framework_detected": None,
        "adapter_name": None,
        "available_adapters": [a["name"] for a in list_adapters()],
        "file_count": 0,
        "sample_files": [],
        "running_in_container": in_container,
        "hint": None,
    }

    # 路径不存在
    if not path.exists():
        if in_container:
            result["hint"] = (
                f"路径 {source_path} 在当前容器内不可达。"
                "若目标项目源码位于宿主机或其他容器，"
                "请在 docker-compose.yml 中通过 volumes 将源码目录挂载到本容器，"
                "例如：- /path/on/host/my-project:/app/projects/my-project，"
                "然后 source_path 填写容器内挂载路径 /app/projects/my-project。"
            )
        else:
            result["hint"] = f"路径 {source_path} 不存在，请检查路径是否正确。"
        return result

    # 不是目录
    if not path.is_dir():
        result["hint"] = f"路径 {source_path} 不是目录，请提供项目根目录路径。"
        return result

    result["is_directory"] = True

    # 可读性检测
    try:
        entries = list(path.iterdir())
        result["readable"] = True
        result["accessible"] = True
        result["file_count"] = len(entries)
        result["sample_files"] = sorted(
            [e.name for e in entries if not e.name.startswith(".")]
        )[:20]
    except PermissionError:
        result["hint"] = (
            f"路径 {source_path} 存在但无读取权限。"
            "请检查目录权限或容器运行用户的访问控制。"
        )
        return result
    except OSError as e:
        result["hint"] = f"读取目录 {source_path} 时出错：{e}"
        return result

    # 框架检测
    adapter = get_adapter(source_path)
    if adapter:
        result["framework_detected"] = adapter.NAME
        result["adapter_name"] = adapter.NAME
    else:
        result["hint"] = (
            "未检测到匹配的框架适配器，源码精准提取将不可用，"
            "建图时将使用规则推断模式。如需精准提取，"
            "请确认项目使用了已支持的框架。"
        )

    return result


def _is_running_in_container() -> bool:
    return Path("/.dockerenv").exists() or os.environ.get("CONTAINER") == "1"


def _resolve_sample_base_url(service_name: str, port: int) -> str:
    """根据运行环境生成示例服务地址。"""
    env_key = f"LUI_{service_name.replace('-', '_').upper()}_BASE_URL"
    override = os.environ.get(env_key)
    if override:
        return override.rstrip("/")

    if _is_running_in_container():
        try:
            socket.getaddrinfo(service_name, port)
            return f"http://{service_name}:{port}"
        except OSError:
            pass

    return f"http://localhost:{port}"


def _extract_routes_from_source(source_path: str) -> list[dict[str, str]]:
    extractor = RouteExtractor(source_path)
    snippets = extractor.extract_all_routes()

    routes: list[dict[str, str]] = []
    seen: set[str] = set()
    for snippet in snippets:
        route_id = f"{snippet.method}:{snippet.path}"
        if route_id in seen:
            continue
        seen.add(route_id)
        routes.append(
            {
                "route_id": route_id,
                "method": snippet.method,
                "path": snippet.path,
                "summary": f"AST:{snippet.adapter_name} {snippet.file_path}:{snippet.start_line}",
            }
        )

    routes.sort(key=lambda item: (item["path"], item["method"]))
    return routes


def _build_openapi_probe_urls(base_url: str, openapi_url: str | None) -> list[str]:
    """构建 OpenAPI 探测候选地址（兼容反向代理与子路径部署）。"""
    base = base_url.rstrip("/")
    parsed_base = urlparse(base)

    candidates: list[str] = []

    if openapi_url:
        if openapi_url.startswith("http"):
            candidates.append(openapi_url)
        else:
            suffix = openapi_url if openapi_url.startswith("/") else f"/{openapi_url}"
            candidates.append(f"{base}{suffix}")
    else:
        candidates.append(f"{base}/openapi.json")

    if parsed_base.scheme and parsed_base.netloc:
        origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
        base_path = parsed_base.path.rstrip("/")

        candidates.extend(
            [
                f"{origin}/openapi.json",
                f"{origin}/api/openapi.json",
                f"{origin}/v1/openapi.json",
            ]
        )

        if base_path:
            candidates.append(f"{origin}{base_path}/openapi.json")

    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(key)

    return deduped


def _is_valid_openapi_spec(spec: object) -> bool:
    """判断 payload 是否为 OpenAPI 文档。"""
    if not isinstance(spec, dict):
        return False

    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return False

    return "openapi" in spec or "swagger" in spec or bool(paths)


def _extract_routes_from_openapi_spec(spec: dict) -> list[dict[str, str]]:
    """将 OpenAPI paths 转为标准路由列表。"""
    if not isinstance(spec, dict):
        return []

    paths = spec.get("paths", {})
    if not isinstance(paths, dict):
        return []

    routes: list[dict[str, str]] = []
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
                if not isinstance(op, dict):
                    op = {}
                summary = op.get("summary") or op.get("operationId") or ""
                routes.append(
                    {
                        "route_id": f"{method.upper()}:{path}",
                        "method": method.upper(),
                        "path": path,
                        "summary": summary,
                    }
                )
    return routes


async def _resolve_import_routes_openapi_first(
    base_url: str,
    openapi_url: str | None,
    source_path: str | None,
    timeout: float = 10.0,
) -> dict[str, object]:
    """导入链路统一路由发现：优先 OpenAPI，失败时按需回退 AST。"""
    import httpx

    probe_urls = _build_openapi_probe_urls(base_url, openapi_url)
    probe_issues: list[str] = []
    auth_blocked_status: int | None = None

    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            for test_url in probe_urls:
                try:
                    response = await client.get(test_url)
                except httpx.TimeoutException:
                    probe_issues.append(f"{test_url} 超时")
                    continue
                except Exception as request_error:
                    probe_issues.append(f"{test_url} 连接失败({type(request_error).__name__})")
                    continue

                status = response.status_code
                if status in (401, 403):
                    auth_blocked_status = status
                    probe_issues.append(f"{test_url} 需要授权 (HTTP {status})")
                    continue
                if status >= 400:
                    probe_issues.append(f"{test_url} 返回 HTTP {status}")
                    continue

                content_type = (response.headers.get("content-type", "") or "").lower()
                if "application/json" not in content_type:
                    probe_issues.append(f"{test_url} 返回非 JSON ({content_type or 'unknown'})")
                    continue

                try:
                    spec = response.json()
                except Exception as parse_error:
                    probe_issues.append(f"{test_url} JSON 解析失败 ({type(parse_error).__name__})")
                    continue

                if not _is_valid_openapi_spec(spec):
                    payload_type = type(spec).__name__
                    if isinstance(spec, dict):
                        payload_hint = f"keys={list(spec.keys())[:3]}"
                    elif isinstance(spec, list):
                        payload_hint = f"list_len={len(spec)}"
                    else:
                        payload_hint = ""
                    probe_issues.append(
                        f"{test_url} JSON 不是 OpenAPI 文档 ({payload_type} {payload_hint})"
                    )
                    continue

                return {
                    "status": "success",
                    "message": f"连接与 OpenAPI 探索可用 ({test_url})",
                    "routes": _extract_routes_from_openapi_spec(spec),
                    "source": "openapi",
                }
    except Exception as fatal_error:
        probe_issues.append(f"探测流程异常({type(fatal_error).__name__})")

    brief_issue = "；".join(probe_issues[:3]) if probe_issues else "未找到可用 OpenAPI 地址"
    if len(probe_issues) > 3:
        brief_issue += f"；另有 {len(probe_issues) - 3} 条探测失败"

    if source_path:
        ast_routes = _extract_routes_from_source(source_path)
        return {
            "status": "warning",
            "message": f"OpenAPI 不可用（{brief_issue}），已切换 AST 语义发现。",
            "routes": ast_routes,
            "source": "ast",
        }

    if auth_blocked_status in (401, 403):
        return {
            "status": "warning",
            "message": f"接口存在授权拦截 (HTTP {auth_blocked_status})。",
            "routes": [],
            "source": "openapi",
        }

    return {
        "status": "warning",
        "message": f"OpenAPI 不可用：{brief_issue}",
        "routes": [],
        "source": "openapi",
    }


def _build_sample_import_presets() -> list[ProjectImportPreset]:
    """构建示例项目导入预置，自动探测当前运行环境下可用路径。"""
    repo_sample_root = PROJECT_ROOT / "backend_for_test"
    fastapi_base_url = _resolve_sample_base_url("sample-fastapi", 8010)
    node_base_url = _resolve_sample_base_url("sample-node", 8020)

    fastapi_source_path, fastapi_available = _resolve_source_path(
        [
            repo_sample_root / "fastapi_sample",
            Path("/app/backend_for_test/fastapi_sample"),
        ]
    )
    node_source_path, node_available = _resolve_source_path(
        [
            repo_sample_root / "node_sample",
            Path("/app/backend_for_test/node_sample"),
        ]
    )

    return [
        ProjectImportPreset(
            id="sample-fastapi",
            name="FastAPI 示例",
            description="自动填充本机 FastAPI 示例地址与源码目录。",
            base_url=fastapi_base_url,
            openapi_url=f"{fastapi_base_url}/openapi.json",
            source_path=fastapi_source_path,
            login_route_id="POST:/api/auth/login",
            username="111",
            password="111111",
            body_field_username="username",
            body_field_password="password",
            available=fastapi_available,
        ),
        ProjectImportPreset(
            id="sample-node",
            name="Node 示例",
            description="自动填充本机 Node 示例地址与源码目录。",
            base_url=node_base_url,
            openapi_url=f"{node_base_url}/openapi.json",
            source_path=node_source_path,
            login_route_id="POST:/api/auth/login",
            username="111",
            password="111111",
            body_field_username="username",
            body_field_password="password",
            available=node_available,
        ),
    ]


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


@router.get("/import-presets")
async def get_import_presets():
    """返回用于前端快速导入示例项目的预置项。"""
    presets = _build_sample_import_presets()
    return {"presets": [preset.model_dump() for preset in presets]}


@router.post("/verify-source-path")
async def verify_source_path(request: VerifySourcePathRequest):
    """验证源码路径的可达性，返回结构化诊断信息（含 Docker 环境感知）"""
    result = _verify_source_path(request.source_path)
    return result


@router.post("/import", response_model=ProjectImportResponse)
async def import_project(
    request: ProjectImportRequest,
    db: AsyncSession = Depends(get_session),
):
    """导入新项目"""
    verification = _verify_source_path(request.source_path)
    if not verification["accessible"]:
        hint = verification.get("hint", "")
        if verification["running_in_container"]:
            detail = (
                f"源码路径不可达: {request.source_path}。"
                f"{hint}"
            ) if hint else (
                f"源码路径不可达: {request.source_path}。"
                "若目标项目源码位于宿主机或其他容器，"
                "请通过 volumes 将源码目录挂载到本容器。"
            )
        else:
            detail = (
                f"源码路径不可达: {request.source_path}。{hint}"
            ) if hint else f"指定的本地源码路径不存在: {request.source_path}"
        raise HTTPException(status_code=400, detail=detail)
    if not verification["is_directory"]:
        raise HTTPException(
            status_code=400,
            detail=f"源码路径必须是一个目录: {request.source_path}",
        )

    project_id = str(uuid.uuid4())

    # 生成 slug
    slug = request.slug or generate_slug(request.name)
    if slug in _RESERVED_SLUGS:
        slug = f"{slug}-project"
    # 确保 slug 唯一
    existing = await ProjectRepository(db).get_by_slug(slug)
    if existing:
        slug = f"{slug}-{project_id[:8]}"

    project = Project(
        id=project_id,
        name=request.name,
        slug=slug,
        base_url=request.base_url,
        openapi_url=request.openapi_url,
        description=request.description,
        username=request.username,
        password=request.password,
        login_route_id=request.login_route_id,
        login_field_username=request.login_field_username or "username",
        login_field_password=request.login_field_password or "password",
        source_path=request.source_path,
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


@router.get("/resolve-slug/{slug}")
async def resolve_project_slug(
    slug: str,
    db: AsyncSession = Depends(get_session),
):
    """将 URL slug 解析为项目信息，供前端用户登录页初始化使用"""
    project = await ProjectRepository(db).get_by_slug(slug)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.user_login_enabled:
        raise HTTPException(status_code=403, detail="该项目未开放用户登录")
    return {
        "project_id": project.id,
        "name": project.name,
        "slug": project.slug,
    }

@router.post("/fetch-routes")
async def fetch_routes(request: FetchRoutesRequest):
    """从 OpenAPI 地址拉取路由列表，供前端选择登录接口"""
    try:
        result = await _resolve_import_routes_openapi_first(
            base_url=request.base_url,
            openapi_url=request.openapi_url,
            source_path=request.source_path,
            timeout=10.0,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无法获取路由列表: {e}")

    payload = {
        "routes": result.get("routes", []),
        "source": result.get("source", "openapi"),
    }
    if result.get("source") == "ast":
        payload["warning"] = result.get("message", "OpenAPI 不可用，已切换 AST 语义发现")
    return payload


@router.post("/verify-login")
async def verify_login(request: VerifyLoginRequest):
    """用提供的凭据调用登录接口，验证是否能拿到 token"""
    import httpx
    from app.services.auth_session_service import AuthSessionService

    method_str, _, path = request.login_route_id.partition(":")
    if not path:
        raise HTTPException(status_code=400, detail="login_route_id 格式应为 METHOD:/path")

    base = request.base_url.rstrip("/")
    url = f"{base}{path if path.startswith('/') else '/' + path}"
    body = {
        request.body_field_username: request.username,
        request.body_field_password: request.password,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.request(
                method=method_str.upper(),
                url=url,
                json=body,
                headers={"Content-Type": "application/json"},
            )
            status_code = resp.status_code
            try:
                body_json = resp.json()
            except Exception:
                body_json = {}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"请求失败: {e}")

    auth = AuthSessionService()
    auth.capture_token(body_json)

    if auth.token:
        return {"success": True, "status_code": status_code, "message": "登录成功，token 已捕获"}
    else:
        return {"success": False, "status_code": status_code, "message": f"登录接口返回 HTTP {status_code}，未能从响应中捕获 token"}


@router.post("/test-connection")
async def test_connection(request: TestConnectionRequest):
    """测试指定基地址或 OpenApiURL 的连通性，同时检测 source_path 可达性"""
    # 源码路径可达性检测
    source_path_info = None
    if request.source_path:
        source_path_info = _verify_source_path(request.source_path)

    try:
        result = await _resolve_import_routes_openapi_first(
            base_url=request.base_url,
            openapi_url=request.openapi_url,
            source_path=request.source_path,
            timeout=10.0,
        )
        response = {
            "status": result.get("status", "success"),
            "message": result.get("message", "连接与 OpenAPI 探索可用"),
            "routes": result.get("routes", []),
            "source": result.get("source", "openapi"),
        }
        if source_path_info is not None:
            response["source_path_info"] = source_path_info
        return response
    except HTTPException:
        raise
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
                "slug": p.slug,
                "description": p.description,
                "base_url": p.base_url,
                "discovery_status": p.discovery_status,
                "discovery_progress": int((p.metadata_ or {}).get("discovery_progress", 0)),
                "discovery_message": (p.metadata_ or {}).get("discovery_message"),
                "discovery_error": p.discovery_error,
                "model_version": p.model_version,
                "user_login_enabled": p.user_login_enabled,
                "default_role_profile_id": p.default_role_profile_id,
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
    slug: str | None = None
    base_url: str | None = None
    user_login_enabled: bool | None = None
    default_role_profile_id: str | None = None


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
    if request.slug is not None:
        if request.slug in _RESERVED_SLUGS:
            raise HTTPException(status_code=400, detail=f"slug 不能使用保留名称: {', '.join(sorted(_RESERVED_SLUGS))}")
        existing = await ProjectRepository(db).get_by_slug(request.slug)
        if existing and existing.id != project_id:
            raise HTTPException(status_code=409, detail="slug 已被其他项目使用")
        project.slug = request.slug
    if request.user_login_enabled is not None:
        project.user_login_enabled = request.user_login_enabled
    if request.base_url is not None:
        project.base_url = request.base_url.rstrip("/")
    if request.default_role_profile_id is not None:
        project.default_role_profile_id = request.default_role_profile_id

    await db.commit()
    return {"project_id": project_id, "status": "updated"}


class CapabilityUpdateRequest(BaseModel):
    """能力信息修改请求"""
    permission_level: str | None = None


@router.patch("/{project_id}/capabilities/{capability_id}")
async def update_capability(
    project_id: str,
    capability_id: str,
    request: CapabilityUpdateRequest,
    db: AsyncSession = Depends(get_session),
):
    """修改能力的权限级别等信息"""
    result = await db.execute(
        select(CapabilityRecord)
        .where(
            CapabilityRecord.project_id == project_id,
            CapabilityRecord.capability_id == capability_id
        )
        .order_by(CapabilityRecord.created_at.desc())
        .limit(1)
    )
    capability = result.scalar_one_or_none()
    
    if not capability:
        raise HTTPException(status_code=404, detail="能力不存在")

    if request.permission_level is not None:
        capability.permission_level = request.permission_level

    await db.commit()
    return {"capability_id": capability_id, "status": "updated"}


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
