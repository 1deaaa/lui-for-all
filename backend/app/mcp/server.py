"""
MCP 连接桥 - FastMCP Server
通过标准 MCP 协议（Streamable HTTP / Streamable-HTTP 传输）
将自然语言服务统一暴露给外部 AI Agent（如 OpenClaw、Claude Desktop 等）。

内部前端的聊天走 /api/sessions SSE 路由；
外部 Agent 走 /mcp 端点，协议和业务逻辑完全复用同一套 LangGraph 图。

暴露的 MCP Tools：
  - list_projects        列出所有已导入项目
  - chat                 发送自然语言消息，流式执行 LangGraph 并返回结果
  - get_session_history  获取会话对话历史

鉴权：
  通过环境变量 LUI_MCP_API_TOKEN 配置静态 Bearer Token。
  未配置则完全开放（开发模式）。
"""

import logging
import uuid
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
        "你正在连接到 LUI-for-All 自然语言接口层。\n"
        "这个服务让你能够通过自然语言与已导入的业务系统进行交互。\n\n"
        "推荐工作流：\n"
        "1. 先调用 list_projects 确认可用的 project_id\n"
        "2. 调用 chat 发送自然语言指令；系统会自动理解意图、选择接口、执行并汇总返回\n"
        "3. 若需多轮对话，将上一步返回的 session_id 传入下次 chat 调用\n"
        "4. 调用 get_session_history 可回看历史记录\n\n"
        "注意：写入类操作（create/update/delete）需要在目标系统配置了相应权限后才能执行。"
    ),
)


# ─────────────────────────────────────────
# Tool: list_projects
# ─────────────────────────────────────────

@mcp.tool(
    name="list_projects",
    description=(
        "列出所有已导入到 LUI-for-All 的项目，包含项目 ID、名称、描述和能力数量。"
        "在调用 chat 工具前，应先调用此工具获取有效的 project_id。"
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
                    "capability_count": len(caps),
                }
            )
        return result


# ─────────────────────────────────────────
# Tool: get_session_history
# ─────────────────────────────────────────

@mcp.tool(
    name="get_session_history",
    description="获取指定会话的完整对话历史，用于了解之前的交互记录。",
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
        "向指定项目发送自然语言消息。系统将自动：\n"
        "1. 理解你的意图\n"
        "2. 从项目能力图谱中选择合适的 API 接口\n"
        "3. 执行一个或多个 HTTP 调用（多轮 ReAct 循环）\n"
        "4. 汇总结果并以自然语言回复\n\n"
        "支持多轮对话：传入相同的 session_id 可保持上下文。\n"
        "不传 session_id 时自动创建新会话，返回的 session_id 可用于后续轮次。"
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
) -> dict:
    """向项目发送自然语言消息，执行 LangGraph Agentic Loop，返回 AI 汇总结果"""
    from app.db import async_session as db_session
    from app.models.session import Message, Session
    from app.models.task import TaskRun
    from app.orchestrator.graph import graph_app
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.session_repository import SessionRepository
    from app.repositories.task_repository import TaskRepository

    await ctx.report_progress(0, 100)
    short_msg = message[:60] + ("..." if len(message) > 60 else "")
    await ctx.log("info", f"📨 收到任务：{short_msg}")

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
            if m.id != user_message_id
        ]

        # 加载项目能力图谱
        caps = await project_repo.list_capabilities(project_id)
        available_capabilities: list[dict] = [
            {
                "capability_id": c.capability_id,
                "name": c.name,
                "description": c.description,
                "domain": c.domain,
                "safety_level": c.safety_level,
                "backed_by_routes": c.backed_by_routes,
                "user_intent_examples": c.user_intent_examples,
                "permission_level": c.permission_level,
                "data_sensitivity": c.data_sensitivity,
                "best_modalities": c.best_modalities,
                "requires_confirmation": c.requires_confirmation,
                "parameter_hints": c.parameter_hints,
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
    await ctx.log(
        "info",
        f"📋 项目「{proj_name}」已加载，共 {len(available_capabilities)} 个能力，开始执行…",
    )

    # ── 2. 构建 LangGraph 初始状态 ──
    initial_state: dict[str, Any] = {
        "session_id": session_id,
        "project_id": project_id,
        "trace_id": trace_id,
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
        "agentic_history": [],
        "agentic_done": False,
        "agentic_iterations": 0,
        "pending_writes": [],
        "execution_artifacts": [],
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
                ev = payload.get("event", "")

                if ev == "task_progress":
                    pct = int(payload.get("progress", 0) * 100)
                    msg_txt = payload.get("message", "")
                    await ctx.report_progress(max(pct, 10), 100)
                    if msg_txt:
                        await ctx.log("info", msg_txt)

                elif ev == "agentic_iteration":
                    iteration = payload.get("iteration", 0)
                    think = payload.get("think") or ""
                    log_msg = f"🔄 第 {iteration} 轮推理"
                    if think:
                        log_msg += f"：{think[:80]}"
                    await ctx.log("info", log_msg)

                elif ev == "tool_started":
                    route = payload.get("route_id", "")
                    title = payload.get("title", "")
                    await ctx.log("info", f"→ 调用接口：{route}  {title}")

                elif ev == "tool_completed":
                    route = payload.get("route_id", "")
                    sc = payload.get("status_code")
                    await ctx.log("info", f"← 完成：{route}（HTTP {sc}）")
                    tool_calls_log.append({"route_id": route, "status_code": sc})

                elif ev == "write_approval_required":
                    # MCP 模式下无法交互审批，跳过并记录
                    graph_interrupted = True
                    items = payload.get("items", [])
                    for item in items:
                        rid = item.get("route_id", "")
                        reason = item.get("reasoning", "")
                        skipped_writes.append({"route_id": rid, "reasoning": reason})
                        await ctx.log(
                            "warning",
                            f"⚠️ 写入操作需人工审批（MCP 模式已跳过）：{rid}  {reason}",
                        )

            elif stream_type == "updates":
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
        await ctx.log("info", "⚙️ 写入操作审批跳过，以拒绝模式恢复图执行…")
        try:
            from langgraph.types import Command

            async for stream_type, payload in graph_app.astream(
                Command(resume={"approved_ids": []}),
                config,
                stream_mode=["custom", "updates"],
            ):
                if stream_type == "updates":
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
            task_run.summary_text = summary
            task_run.status = "failed" if error else "completed"
            if error:
                task_run.error = error

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
    await ctx.log("info", "✅ 任务完成")

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
