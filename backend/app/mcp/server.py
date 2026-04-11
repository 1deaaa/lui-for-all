"""
MCP 连接桥 - FastMCP Server
通过标准 MCP 协议（Streamable HTTP / Streamable-HTTP 传输）
将自然语言服务统一暴露给外部 AI Agent（如 OpenClaw、Claude Desktop 等）。

内部前端的聊天走 /api/sessions SSE 路由；
外部 Agent 走 /mcp 端点，协议和业务逻辑完全复用同一套 LangGraph 图。

暴露的 MCP Tools：
  - list_projects              列出所有已导入项目
  - get_project_capabilities   查看项目能力清单（业务语义 + 安全属性）
  - chat                       发送自然语言消息，由内部 AI 执行并返回结果
  - get_task_run_result        查询任务执行结果与产物
  - get_session_history        获取会话对话历史

鉴权：
  通过环境变量 LUI_MCP_API_TOKEN 配置静态 Bearer Token。
  未配置则完全开放（开发模式）。
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import Field

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# FastMCP 服务实例
# ─────────────────────────────────────────

mcp = FastMCP(
    name="LUI-for-All",
    instructions=(
        "你正在连接到 LUI-for-All —— 一个自然语言接口层，让你通过对话与已导入的业务系统交互。\n\n"
        "推荐工作流：\n"
        "1. 调用 list_projects 获取可用的 project_id（通常只需调用一次）\n"
        "   - 若返回空列表，提示用户先导入项目，不要重复调用\n"
        "2. 调用 get_project_capabilities 查看项目能做什么\n"
        "   - 默认返回轻量列表（capability_id、名称、摘要），帮助快速浏览\n"
        "   - 需要详细信息时，传入 capability_ids 批量查询（领域、安全等级、意图示例等）\n"
        "   - 可按 domain / safety_level / keyword 过滤\n"
        "3. 调用 chat 发送自然语言指令\n"
        "   - 内部 AI 会自动理解意图、选择接口、执行调用并汇总结果\n"
        "   - 你无法直接调用底层路由，chat 是唯一的执行通道\n"
        "4. 多轮对话：将 chat 返回的 session_id 传入下次调用以保持上下文\n"
        "5. get_task_run_result 可查询历史任务详情，get_session_history 可回看对话记录\n\n"
        "安全提示：\n"
        "- safety_level=hard_write 或 critical 的操作在 MCP 模式下可能被跳过，需通过内置聊天界面审批\n"
        "- 若 chat 返回错误，请检查错误信息中的排查建议并转达给用户"
    ),
)


def _resolve_response_language(locale: str | None) -> tuple[str, str]:
    """将 locale 标准化为内部 locale 与提示词语言名。"""
    normalized = (locale or "").strip().lower().replace("_", "-")

    if normalized.startswith("en"):
        return "en-US", "English"
    if normalized.startswith("ja"):
        return "ja-JP", "日本語"
    return "zh-CN", "简体中文"


def _build_parameter_hints_from_route(route: dict[str, Any]) -> dict[str, Any]:
    """从 route_map 路由记录提取参数提示（含 request_body_fields）。"""
    hints: dict[str, Any] = {}
    all_params = (route.get("parameters") or []) + (route.get("request_body_fields") or [])

    for param in all_params:
        if not isinstance(param, dict):
            continue
        name = param.get("name")
        if not name:
            continue

        location = str(param.get("location") or "query")
        key = name if name not in hints else f"{name}@{location}"
        hints[key] = {
            "name": name,
            "location": location,
            "type": param.get("type_hint", "str"),
            "required": bool(param.get("required", False)),
            "description": param.get("description"),
            "default": param.get("default"),
            "example": param.get("example"),
        }

    return hints


def _merge_parameter_hints(
    capability_hints: dict[str, Any] | None,
    backed_by_routes: list[dict[str, Any]] | None,
    route_hints_by_route_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """将 capability 已有 hints 与 route_map hints 合并，优先保留已有字段并补齐缺失项。"""
    merged = dict(capability_hints or {})
    if not backed_by_routes:
        return merged

    def _hint_identity(hint_key: str, hint_val: Any) -> str:
        if isinstance(hint_val, dict):
            name = str(hint_val.get("name") or str(hint_key).split("@", 1)[0])
            location = str(hint_val.get("location") or "")
        else:
            name = str(hint_key).split("@", 1)[0]
            location = ""
        return f"{name}@{location}" if location else name

    existing_identities: set[str] = {
        _hint_identity(str(key), value)
        for key, value in merged.items()
    }

    for route in backed_by_routes:
        if not isinstance(route, dict):
            continue
        route_id = route.get("route_id")
        if not route_id:
            continue

        route_hints = route_hints_by_route_id.get(str(route_id), {})
        for hint_key, hint_val in route_hints.items():
            identity = _hint_identity(str(hint_key), hint_val)
            if identity in existing_identities:
                continue
            merged[hint_key] = hint_val
            existing_identities.add(identity)

    return merged


def _build_route_hints_by_route_id(routes: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """为 route_id 建立参数提示索引。"""
    route_hints_by_route_id: dict[str, dict[str, Any]] = {}
    if not routes:
        return route_hints_by_route_id

    for route in routes:
        if not isinstance(route, dict):
            continue
        route_id = route.get("route_id")
        if not route_id:
            continue
        route_hints_by_route_id[str(route_id)] = _build_parameter_hints_from_route(route)
    return route_hints_by_route_id


# ─────────────────────────────────────────
# Tool: list_projects
# ─────────────────────────────────────────

@mcp.tool(
    name="list_projects",
    description=(
        "列出所有已导入的项目，返回项目 ID、名称、描述和能力数量。"
        "在调用 chat 前通常只需调用一次此工具获取有效的 project_id。"
        "若返回空列表，应提示用户先导入项目，不要重复调用本工具。"
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
async def list_projects() -> list[dict]:
    """列出所有已导入项目"""
    from app.db import async_session
    from app.repositories.project_repository import ProjectRepository

    async with async_session() as db:
        repo = ProjectRepository(db)
        projects = await repo.list_all()
        result = []
        for p in projects:
            caps = await repo.list_capabilities(p.id)
            result.append(
                {
                    "project_id": p.id,
                    "name": p.name,
                    "description": p.description or "",
                    "base_url": p.base_url,
                    "discovery_status": p.discovery_status,
                    "capability_count": len(caps),
                }
            )
        # Prefer actionable projects first so generic MCP clients don't keep retrying empty-capability entries.
        result.sort(key=lambda item: int(item.get("capability_count") or 0), reverse=True)
        logger.info("[mcp.list_projects] returned %d projects", len(result))
        return result


@mcp.tool(
    name="get_project_capabilities",
    description=(
        "获取指定项目的能力清单。默认返回轻量列表（ID、名称、摘要），"
        "传入 capability_ids 可批量查询指定能力的详细信息（领域、安全等级、意图示例等）。"
        "可按 domain / safety_level / keyword 过滤。"
        "底层路由参数细节由内部 AI 自行处理，本工具不返回。"
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
async def get_project_capabilities(
    project_id: Annotated[str, Field(description="目标项目 ID")],
    capability_ids: Annotated[
        list[str] | None,
        Field(description="可选，批量查询指定能力的详细信息，传入 capability_id 列表"),
    ] = None,
    domain: Annotated[
        str | None,
        Field(
            description="可选，按业务领域过滤：auth/customer/finance/inventory/content/analytics/operations/system/unknown",
        ),
    ] = None,
    safety_level: Annotated[
        str | None,
        Field(
            description="可选，按安全等级过滤：readonly_safe/readonly_sensitive/soft_write/hard_write/critical",
        ),
    ] = None,
    keyword: Annotated[
        str | None,
        Field(description="可选，按能力名称或功能摘要模糊匹配"),
    ] = None,
    limit: Annotated[int, Field(description="最多返回条数", ge=1, le=500)] = 200,
) -> dict[str, Any]:
    """返回项目能力目录，便于外部 AI 了解项目可调用范围。"""
    from app.db import async_session
    from app.repositories.project_repository import ProjectRepository

    async with async_session() as db:
        repo = ProjectRepository(db)
        project = await repo.get_by_id(project_id)
        if not project:
            raise ValueError(f"项目不存在：{project_id}")

        caps = await repo.list_capabilities(project_id)

        # 批量查询模式：传入 capability_ids 时返回详细信息
        if capability_ids:
            id_set = {str(cid) for cid in capability_ids}
            items: list[dict[str, Any]] = []
            for c in caps:
                if c.capability_id not in id_set:
                    continue
                items.append({
                    "capability_id": c.capability_id,
                    "name": c.name,
                    "summary": c.summary,
                    "domain": c.domain,
                    "safety_level": c.safety_level,
                    "permission_level": c.permission_level,
                    "user_intent_examples": c.user_intent_examples,
                    "data_sensitivity": c.data_sensitivity,
                    "ai_usage_guidelines": c.ai_usage_guidelines,
                })
            return {
                "project_id": project.id,
                "project_name": project.name,
                "count": len(items),
                "capabilities": items,
            }

        # 默认轻量模式：只返回 ID、名称、摘要
        domain_lc = (domain or "").strip().lower()
        safety_lc = (safety_level or "").strip().lower()
        keyword_lc = (keyword or "").strip().lower()

        filtered: list[dict[str, Any]] = []
        for c in caps:
            if domain_lc and (c.domain or "").lower() != domain_lc:
                continue
            if safety_lc and (c.safety_level or "").lower() != safety_lc:
                continue
            if keyword_lc:
                haystack = f"{c.name} {c.summary or ''} {c.capability_id}".lower()
                if keyword_lc not in haystack:
                    continue

            filtered.append({
                "capability_id": c.capability_id,
                "name": c.name,
                "summary": c.summary,
            })

            if len(filtered) >= limit:
                break

        return {
            "project_id": project.id,
            "project_name": project.name,
            "count": len(filtered),
            "capabilities": filtered,
        }


@mcp.tool(
    name="get_task_run_result",
    description=(
        "按 task_run_id 查询任务执行结果与状态。"
        "返回任务状态、AI 汇总文本、执行产物等。"
        "task_run_id 由 chat 工具返回。"
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
async def get_task_run_result(
    task_run_id: Annotated[str, Field(description="任务 ID（由 chat 工具返回）")],
    include_artifacts: Annotated[
        bool,
        Field(description="是否返回 execution_artifacts"),
    ] = True,
    artifact_limit: Annotated[int, Field(description="产物返回上限", ge=1, le=500)] = 100,
) -> dict[str, Any]:
    """查询任务执行详情，便于外部系统做二次编排或审计。"""
    from app.db import async_session
    from app.repositories.task_repository import TaskRepository

    async with async_session() as db:
        task = await TaskRepository(db).get_by_id(task_run_id)
        if not task:
            raise ValueError(f"任务不存在：{task_run_id}")

        result: dict[str, Any] = {
            "task_run_id": task.id,
            "session_id": task.session_id,
            "project_id": task.project_id,
            "status": task.status,
            "user_message": task.user_message,
            "summary_text": task.summary_text,
            "error": task.error,
            "trace_id": task.trace_id,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "ui_blocks_count": len(task.ui_blocks or []),
        }

        if include_artifacts:
            result["execution_artifacts"] = (task.execution_artifacts or [])[:artifact_limit]
        return result


# ─────────────────────────────────────────
# Tool: get_session_history
# ─────────────────────────────────────────

@mcp.tool(
    name="get_session_history",
    description=(
        "获取指定会话的对话历史，用于回看之前的交互记录。"
        "session_id 由 chat 工具返回。"
    ),
    annotations={"readOnlyHint": True},
)
async def get_session_history(
    session_id: Annotated[str, Field(description="会话 ID（由 chat 工具返回）")],
    limit: Annotated[
        int, Field(description="最多返回的消息条数", ge=1, le=100)
    ] = 20,
) -> list[dict]:
    """获取会话对话历史"""
    from app.db import async_session
    from app.repositories.session_repository import SessionRepository

    async with async_session() as db:
        repo = SessionRepository(db)
        messages = await repo.list_messages(session_id, limit=limit)
        return [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]


# ─────────────────────────────────────────
# Tool: chat（核心工具）
# ─────────────────────────────────────────

@mcp.tool(
    name="chat",
    description=(
        "向指定项目发送自然语言消息，由项目内的管理 AI 执行：\n"
        "1. 理解你的意图\n"
        "2. 从能力图谱中选择合适的接口\n"
        "3. 执行一个或多个 HTTP 调用（多轮 ReAct 循环）\n"
        "4. 汇总结果并以自然语言回复\n\n"
        "这是唯一的执行通道，你无法直接调用底层路由。\n"
        "支持多轮对话：传入相同的 session_id 可保持上下文，不传则自动创建新会话。"
    ),
)
async def chat(
    ctx: Context,
    project_id: Annotated[
        str, Field(description="目标项目 ID（从 list_projects 获取）")
    ],
    message: Annotated[
        str, Field(description="自然语言消息，描述你想做的事情")
    ],
    session_id: Annotated[
        str | None,
        Field(description="可选，已有会话 ID，用于保持多轮对话上下文"),
    ] = None,
    locale: Annotated[
        str | None,
        Field(description="可选，响应语言（zh-CN/en-US/ja-JP）"),
    ] = None,
) -> dict:
    """向项目发送自然语言消息，执行 LangGraph Agentic Loop，返回 AI 汇总结果"""
    from app.db import async_session as db_session
    from app.models.session import Message, Session
    from app.models.task import TaskRun
    from app.orchestrator.graph import graph_app
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.session_repository import SessionRepository
    from app.repositories.task_repository import TaskRepository
    from app.config import settings

    # ── 前置检查：LLM 可用性 ──
    try:
        from app.llm.agent_matchbox import matchbox
        mgr = matchbox(required=False)
        if not mgr:
            raise RuntimeError(
                "内部 AI 不可用：LLM 管理器未初始化。"
                "排查建议：1) 前往 LUI-for-All 前台「模型设置」页面，配置至少一个 LLM 平台和模型；"
                "2) 确认 API Base URL 和 API Key 正确；3) 使用「测试连接」功能验证连通性后重试。"
            )
        details = mgr.get_user_selection_detail(-1, "main")
        current = details.get("current", {})
        if not current.get("platform_id") or current.get("platform_id") == -1:
            raise RuntimeError(
                "内部 AI 不可用：尚未选择主模型。"
                "排查建议：前往 LUI-for-All 前台「模型设置」页面，选择一个已配置的模型作为主模型后重试。"
            )
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"内部 AI 不可用：LLM 配置检查失败（{type(e).__name__}: {e}）。"
            "排查建议：前往 LUI-for-All 前台「模型设置」页面，检查模型配置是否完整。"
        ) from e

    if settings.safety_default_action != "allow":
        raise RuntimeError(
            "MCP 调用拒绝：当前系统安全性尚未就绪。MCP 取代了人类视觉审计环节，"
            "您必须前往前台「系统设置」中，主动将「默认动作」切换为「全部允许」以确认开放此全自动通道。"
            "警告：只有在您确信接入的 AI Agent 是安全、受控的情况下才可以执行此操作！"
        )

    response_locale, response_language = _resolve_response_language(locale)

    await ctx.report_progress(0, 100)
    short_msg = message[:60] + ("..." if len(message) > 60 else "")
    await ctx.info(f"📨 收到任务：{short_msg}")

    # ── 1. 验证项目、创建或复用会话 ──
    thread_id: str
    async with db_session() as db:
        project_repo = ProjectRepository(db)
        session_repo = SessionRepository(db)
        task_repo = TaskRepository(db)

        project = await project_repo.get_by_id(project_id)
        if not project:
            raise ValueError(
                f"项目不存在：{project_id}。请先调用 list_projects 获取有效的 project_id。"
            )

        # ── 前置检查：项目发现状态 ──
        if project.discovery_status != "completed":
            status_hint = {
                "pending": "项目尚未开始建图，请在前台触发项目发现流程。",
                "in_progress": "项目正在建图中，请稍后重试。",
                "failed": f"项目建图失败{f'（{project.discovery_error}）' if project.discovery_error else ''}，请在前台重新触发发现流程。",
            }.get(project.discovery_status, f"项目状态异常（{project.discovery_status}），请联系管理员。")
            raise RuntimeError(
                f"项目「{project.name}」尚未完成能力建图（当前状态：{project.discovery_status}），无法执行任务。"
                f"{status_hint}"
            )

        if session_id:
            session = await session_repo.get_by_id(session_id)
            if not session or session.project_id != project_id:
                raise ValueError(
                    f"会话 {session_id} 不存在或不属于项目 {project_id}。"
                )
            thread_id = session.thread_id or f"thread_{session_id}"
        else:
            session_id = str(uuid.uuid4())
            thread_id = f"thread_{session_id}"
            session = Session(
                id=session_id,
                project_id=project_id,
                status="active",
                thread_id=thread_id,
            )
            await session_repo.add_session(session)

        # 保存用户消息
        user_message_id = str(uuid.uuid4())
        user_msg = Message(
            id=user_message_id,
            session_id=session_id,
            role="user",
            content=message,
        )
        await session_repo.add_message(user_msg)
        if not session.title:
            await session_repo.update_title(session_id, message[:20])

        # 创建任务记录
        task_run_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        task_run = TaskRun(
            id=task_run_id,
            session_id=session_id,
            project_id=project_id,
            user_message=message,
            status="running",
            trace_id=trace_id,
            thread_id=thread_id,
        )
        await task_repo.add_task_run(task_run)

        # 加载历史消息（排除刚添加的用户消息）
        all_msgs = await session_repo.list_messages(session_id, limit=50)
        chat_history = [
            {"role": m.role, "content": m.content}
            for m in all_msgs
            if m.id != user_message_id and m.role in ("user", "assistant")
        ]

        # 加载项目能力图谱
        caps = await project_repo.list_capabilities(project_id)
        route_map = await project_repo.get_latest_route_map(project_id)
        route_hints_by_route_id = _build_route_hints_by_route_id(
            route_map.routes if route_map else None,
        )
        available_capabilities: list[dict] = [
            {
                "capability_id": c.capability_id,
                "name": c.name,
                "summary": c.summary,
                "description": c.description,
                "domain": c.domain,
                "safety_level": c.safety_level,
                "backed_by_routes": c.backed_by_routes,
                "user_intent_examples": c.user_intent_examples,
                "permission_level": c.permission_level,
                "data_sensitivity": c.data_sensitivity,
                "best_modalities": c.best_modalities,
                "ai_usage_guidelines": c.ai_usage_guidelines,
                "parameter_hints": _merge_parameter_hints(
                    c.parameter_hints,
                    c.backed_by_routes,
                    route_hints_by_route_id,
                ),
            }
            for c in caps
        ]

        # 保存项目字段（避免会话关闭后懒加载异常）
        proj_base_url = project.base_url
        proj_username = project.username
        proj_password = project.password
        proj_login_route_id = project.login_route_id
        proj_login_field_username = project.login_field_username or "username"
        proj_login_field_password = project.login_field_password or "password"
        proj_description = project.description
        proj_name = project.name

        await db.commit()

    await ctx.report_progress(10, 100)
    await ctx.info(f"📋 项目「{proj_name}」已加载，共 {len(available_capabilities)} 个能力，开始执行…")

    # ── 2. 构建 LangGraph 初始状态 ──
    initial_state: dict[str, Any] = {
        "session_id": session_id,
        "project_id": project_id,
        "trace_id": trace_id,
        "response_locale": response_locale,
        "response_language": response_language,
        "project_base_url": proj_base_url,
        "project_username": proj_username,
        "project_password": proj_password,
        "project_login_route_id": proj_login_route_id,
        "project_login_field_username": proj_login_field_username,
        "project_login_field_password": proj_login_field_password,
        "project_description": proj_description,
        "chat_history": chat_history,
        "user_message": message,
        "available_capabilities": available_capabilities,
        "route_hints_by_route_id": route_hints_by_route_id,
        "agentic_history": [],
        "agentic_done": False,
        "agentic_iterations": 0,
        "pending_writes": [],
        "execution_artifacts": [],
        "final_answer_draft": None,
        "summary_text": None,
        "ui_blocks": [],
        "error": None,
        "current_node": None,
        "request_complexity": None,
    }
    config = {"configurable": {"thread_id": thread_id}}

    # ── 3. 执行图，监听流式事件，上报进度 ──
    node_progress_map = {
        "agent_entry": 15,
        "agentic_loop": 60,
        "summarize": 85,
        "emit_blocks": 95,
    }
    final_state: dict[str, Any] = dict(initial_state)
    tool_calls_log: list[dict] = []
    skipped_writes: list[dict] = []
    graph_interrupted = False

    try:
        async for stream_type, payload in graph_app.astream(
            initial_state,
            config,
            stream_mode=["custom", "updates"],
        ):
            if stream_type == "custom":
                if not isinstance(payload, dict):
                    continue
                ev = payload.get("event", "")

                if ev == "task_progress":
                    pct = int(payload.get("progress", 0) * 100)
                    msg_txt = payload.get("message", "")
                    await ctx.report_progress(max(pct, 10), 100)
                    if msg_txt:
                        await ctx.info(msg_txt)

                elif ev == "agentic_iteration":
                    iteration = payload.get("iteration", 0)
                    think = payload.get("think") or ""
                    log_msg = f"🔄 第 {iteration} 轮推理"
                    if think:
                        log_msg += f"：{think[:80]}"
                    await ctx.info(log_msg)

                elif ev == "tool_started":
                    route = payload.get("route_id", "")
                    title = payload.get("title", "")
                    await ctx.info(f"→ 调用接口：{route}  {title}")

                elif ev == "tool_completed":
                    route = payload.get("route_id", "")
                    sc = payload.get("status_code")
                    await ctx.info(f"← 完成：{route}（HTTP {sc}）")
                    tool_calls_log.append({"route_id": route, "status_code": sc})

                elif ev == "write_approval_required":
                    # MCP 模式下无法交互审批，跳过并记录
                    graph_interrupted = True
                    items = payload.get("items", [])
                    for item in items:
                        rid = item.get("route_id", "")
                        reason = item.get("reasoning", "")
                        skipped_writes.append({"route_id": rid, "reasoning": reason})
                        await ctx.warning(f"⚠️ 写入操作需人工审批（MCP 模式已跳过）：{rid}  {reason}")

            elif stream_type == "updates":
                if not isinstance(payload, dict):
                    continue
                for node_name, node_update in payload.items():
                    if isinstance(node_update, dict):
                        for k, v in node_update.items():
                            if k in ("execution_artifacts", "ui_blocks"):
                                cur = final_state.get(k) or []
                                cur.extend(v)
                                final_state[k] = cur
                            else:
                                final_state[k] = v
                    pct = node_progress_map.get(node_name, 0)
                    if pct:
                        await ctx.report_progress(pct, 100)

    except Exception as exc:
        logger.error(f"[mcp.chat] LangGraph 执行异常: {exc}", exc_info=True)
        raise RuntimeError(f"任务执行失败：{exc}") from exc

    # ── 4. 若图因 interrupt 暂停，自动以拒绝方式恢复（MCP 安全策略）──
    if graph_interrupted:
        await ctx.info("⚙️ 写入操作审批跳过，以拒绝模式恢复图执行…")
        try:
            from langgraph.types import Command

            async for stream_type, payload in graph_app.astream(
                Command(resume={"approved_ids": []}),
                config,
                stream_mode=["custom", "updates"],
            ):
                if stream_type == "updates":
                    if not isinstance(payload, dict):
                        continue
                    for node_name, node_update in payload.items():
                        if isinstance(node_update, dict):
                            for k, v in node_update.items():
                                if k in ("execution_artifacts", "ui_blocks"):
                                    cur = final_state.get(k) or []
                                    cur.extend(v)
                                    final_state[k] = cur
                                else:
                                    final_state[k] = v
                elif stream_type == "custom":
                    if not isinstance(payload, dict):
                        continue
                    ev = payload.get("event", "")
                    if ev == "task_progress":
                        pct = int(payload.get("progress", 0) * 100)
                        await ctx.report_progress(max(pct, 60), 100)
        except Exception as exc:
            logger.warning(f"[mcp.chat] 审批拒绝恢复失败: {exc}")

    await ctx.report_progress(97, 100)

    # ── 5. 持久化结果 ──
    summary = final_state.get("summary_text") or ""
    error = final_state.get("error")

    async with db_session() as db:
        task_repo = TaskRepository(db)
        session_repo = SessionRepository(db)

        task_run = await task_repo.get_by_id(task_run_id)
        if task_run:
            artifacts = final_state.get("execution_artifacts") or []
            task_run.execution_artifacts = [
                artifact.model_dump() if hasattr(artifact, "model_dump") else artifact
                for artifact in artifacts
            ]
            task_run.ui_blocks = final_state.get("ui_blocks") or []
            task_run.normalized_intent = final_state.get("normalized_intent")
            task_run.summary_text = summary
            task_run.status = "failed" if error else "completed"
            if error:
                task_run.error = error
            else:
                task_run.completed_at = datetime.now(UTC).replace(tzinfo=None)

        if summary and not error:
            assistant_msg = Message(
                id=str(uuid.uuid4()),
                session_id=session_id,
                role="assistant",
                content=summary,
                task_run_id=task_run_id,
            )
            await session_repo.add_message(assistant_msg)

        await db.commit()

    await ctx.report_progress(100, 100)
    await ctx.info("✅ 任务完成")

    if error:
        raise RuntimeError(f"任务执行遇到错误：{error}")

    # ── 6. 返回结果 ──
    result: dict[str, Any] = {
        "session_id": session_id,
        "task_run_id": task_run_id,
        "summary": summary,
        "tool_calls": tool_calls_log,
        "ui_blocks": final_state.get("ui_blocks", []),
    }
    if skipped_writes:
        result["skipped_writes"] = skipped_writes
        result["note"] = (
            "部分写入操作需要人工审批，在 MCP 模式下已被安全跳过。"
            "如需执行写入，请通过内置聊天界面完成审批流程。"
        )
    return result
