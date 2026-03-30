"""
SSE 事件流 Schema
定义 AG-UI 风格的 Server-Sent Events 事件规范
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """SSE 事件类型"""

    # 会话生命周期
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"

    # 任务流程
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # LangGraph 节点事件
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"

    # 意图解析
    INTENT_PARSED = "intent_parsed"

    # 能力选择
    CAPABILITIES_SELECTED = "capabilities_selected"

    # 任务计划
    TASK_PLAN_DRAFTED = "task_plan_drafted"

    # 策略检查
    POLICY_CHECKED = "policy_checked"
    POLICY_BLOCKED = "policy_blocked"

    # 参数请求
    PARAMS_REQUESTED = "params_requested"

    # 审批
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"

    # 执行
    EXECUTION_STARTED = "execution_started"
    EXECUTION_PROGRESS = "execution_progress"
    EXECUTION_COMPLETED = "execution_completed"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"

    # 结果
    SUMMARY_READY = "summary_ready"

    # UI Block
    UI_BLOCK_EMITTED = "ui_block_emitted"

    # Token 流式输出
    TOKEN_EMITTED = "token_emitted"
    THOUGHT_EMITTED = "thought_emitted"

    # Agentic Loop 专用
    WRITE_APPROVAL_REQUIRED = "write_approval_required"  # 写入操作待人工批准
    AGENTIC_ITERATION = "agentic_iteration"              # 每轮循环开始通知

    # 错误
    ERROR = "error"


class SSEEvent(BaseModel):
    """SSE 事件基类"""

    event: EventType = Field(description="事件类型")
    data: dict[str, Any] = Field(default_factory=dict, description="事件数据")
    id: str | None = Field(default=None, description="事件 ID")
    retry: int | None = Field(default=None, description="重试间隔 (毫秒)")


class SessionStartedEvent(BaseModel):
    """会话开始事件"""

    event: EventType = Field(default=EventType.SESSION_STARTED, frozen=True)
    session_id: str = Field(description="会话 ID")
    project_id: str = Field(description="项目 ID")
    trace_id: str = Field(description="追踪 ID")


class TaskStartedEvent(BaseModel):
    """任务开始事件"""

    event: EventType = Field(default=EventType.TASK_STARTED, frozen=True)
    session_id: str = Field(description="会话 ID")
    task_run_id: str = Field(description="任务运行 ID")
    user_message: str = Field(description="用户消息")


class TaskCompletedEvent(BaseModel):
    """任务完成事件"""

    event: EventType = Field(default=EventType.TASK_COMPLETED, frozen=True)
    session_id: str = Field(description="会话 ID")
    task_run_id: str = Field(description="任务运行 ID")
    summary: str | None = Field(default=None, description="任务摘要")


class NodeCompletedEvent(BaseModel):
    """节点完成事件"""

    event: EventType = Field(default=EventType.NODE_COMPLETED, frozen=True)
    session_id: str = Field(description="会话 ID")
    task_run_id: str = Field(description="任务运行 ID")
    node_name: str = Field(description="节点名称")
    progress: float = Field(default=0.0, description="进度")


class TaskProgressEvent(BaseModel):
    """任务进度事件"""

    event: EventType = Field(default=EventType.TASK_PROGRESS, frozen=True)
    session_id: str = Field(description="会话 ID")
    task_run_id: str = Field(description="任务运行 ID")
    node_name: str = Field(description="当前节点名称")
    progress: float = Field(ge=0.0, le=1.0, description="进度 (0-1)")
    message: str | None = Field(default=None, description="进度消息")


class ToolStartedEvent(BaseModel):
    """工具开始事件"""

    event: EventType = Field(default=EventType.TOOL_STARTED, frozen=True)
    session_id: str = Field(description="会话 ID")
    task_run_id: str = Field(description="任务运行 ID")
    tool_name: str = Field(description="工具名称")
    title: str = Field(description="事件标题")
    detail: str | None = Field(default=None, description="详细信息")
    step_id: str | None = Field(default=None, description="步骤 ID")
    route_id: str | None = Field(default=None, description="路由 ID")


class ToolCompletedEvent(BaseModel):
    """工具完成事件"""

    event: EventType = Field(default=EventType.TOOL_COMPLETED, frozen=True)
    session_id: str = Field(description="会话 ID")
    task_run_id: str = Field(description="任务运行 ID")
    tool_name: str = Field(description="工具名称")
    title: str = Field(description="事件标题")
    detail: str | None = Field(default=None, description="详细信息")
    step_id: str | None = Field(default=None, description="步骤 ID")
    route_id: str | None = Field(default=None, description="路由 ID")
    status_code: int | None = Field(default=None, description="HTTP 状态码")


class UIBlockEmittedEvent(BaseModel):
    """UI Block 输出事件"""

    event: EventType = Field(default=EventType.UI_BLOCK_EMITTED, frozen=True)
    session_id: str = Field(description="会话 ID")
    task_run_id: str = Field(description="任务运行 ID")
    block_index: int = Field(description="Block 序号")
    block_type: str = Field(description="Block 类型")
    block_data: dict[str, Any] = Field(description="Block 数据")


class TokenEmittedEvent(BaseModel):
    """Token 发射事件 (用于流式对话)"""

    event: EventType = Field(default=EventType.TOKEN_EMITTED, frozen=True)
    session_id: str = Field(description="会话 ID")
    task_run_id: str = Field(description="任务运行 ID")
    token: str = Field(description="Token 内容")


class ThoughtEmittedEvent(BaseModel):
    """思考过程发射事件"""

    event: EventType = Field(default=EventType.THOUGHT_EMITTED, frozen=True)
    session_id: str = Field(description="会话 ID")
    task_run_id: str = Field(description="任务运行 ID")
    token: str = Field(description="思考 Token 内容")


class ApprovalRequiredEvent(BaseModel):
    """审批请求事件"""

    event: EventType = Field(default=EventType.APPROVAL_REQUIRED, frozen=True)
    session_id: str = Field(description="会话 ID")
    task_run_id: str = Field(description="任务运行 ID")
    approval_id: str = Field(description="审批 ID")
    title: str = Field(description="审批标题")
    description: str = Field(description="审批描述")
    risk_level: str = Field(description="风险等级")
    timeout_seconds: int = Field(default=300, description="超时时间")


class ErrorEvent(BaseModel):
    """错误事件"""

    event: EventType = Field(default=EventType.ERROR, frozen=True)
    session_id: str | None = Field(default=None, description="会话 ID")
    task_run_id: str | None = Field(default=None, description="任务运行 ID")
    error_code: str = Field(description="错误代码")
    error_message: str = Field(description="错误消息")
    details: dict[str, Any] | None = Field(default=None, description="详细信息")


def format_sse_event(event: BaseModel) -> str:
    """格式化为 SSE 文本格式"""
    event_dict = event.model_dump(mode="json")
    event_type = event_dict.pop("event", "message")
    lines = [f"event: {event_type}"]

    if "id" in event_dict and event_dict["id"]:
        lines.append(f"id: {event_dict['id']}")

    import json

    lines.append(f"data: {json.dumps(event_dict, ensure_ascii=False)}")
    lines.append("")  # 空行结束
    lines.append("")  # 额外空行
    return "\n".join(lines)


class WriteApprovalRequiredEvent(BaseModel):
    """写入操作待人工审批事件"""

    event: EventType = Field(default=EventType.WRITE_APPROVAL_REQUIRED, frozen=True)
    session_id: str = Field(description="会话 ID")
    task_run_id: str = Field(description="任务运行 ID")
    write_id: str = Field(description="写入操作唯一 ID")
    route_id: str = Field(description="接口路由，如 POST:/api/users")
    method: str = Field(description="HTTP 方法")
    path: str = Field(description="接口路径")
    parameters: dict = Field(default_factory=dict, description="请求参数")
    reasoning: str = Field(default="", description="AI 为什么要执行这个写入")
    safety_level: str = Field(default="soft_write", description="安全等级")


class AgenticIterationEvent(BaseModel):
    """Agentic Loop 轮次通知事件"""

    event: EventType = Field(default=EventType.AGENTIC_ITERATION, frozen=True)
    session_id: str = Field(description="会话 ID")
    task_run_id: str = Field(description="任务运行 ID")
    iteration: int = Field(description="当前轮次（从 1 开始）")
    think: str | None = Field(default=None, description="本轮 AI 推理摘要（可为空）")

