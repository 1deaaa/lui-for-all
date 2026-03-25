"""
任务 Schema
定义任务状态和执行上下文
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_PARAMS = "waiting_params"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(str, Enum):
    """审批状态"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class TaskPlan(BaseModel):
    """任务计划"""

    plan_id: str = Field(description="计划 ID")
    description: str = Field(description="计划描述")
    steps: list["TaskStep"] = Field(default_factory=list, description="执行步骤")
    estimated_duration_ms: int | None = Field(default=None, description="预估耗时")


class TaskStep(BaseModel):
    """任务步骤"""

    step_id: str = Field(description="步骤 ID")
    order: int = Field(description="步骤顺序")
    capability_id: str = Field(description="能力 ID")
    route_id: str = Field(description="路由 ID")
    action: str = Field(description="动作描述")
    parameters: dict[str, Any] = Field(default_factory=dict, description="参数")
    safety_level: str = Field(description="安全等级")
    requires_confirmation: bool = Field(default=False, description="是否需要确认")


class ExecutionArtifact(BaseModel):
    """执行产物"""

    artifact_id: str = Field(description="产物 ID")
    step_id: str = Field(description="步骤 ID")
    route_id: str = Field(description="路由 ID")
    method: str = Field(description="HTTP 方法")
    url: str = Field(description="请求 URL")
    request_headers: dict[str, str] = Field(
        default_factory=dict,
        description="请求头",
    )
    request_body: dict[str, Any] | None = Field(
        default=None,
        description="请求体",
    )
    status_code: int | None = Field(default=None, description="响应状态码")
    response_body: dict[str, Any] | None = Field(
        default=None,
        description="响应体",
    )
    duration_ms: int | None = Field(default=None, description="耗时 (毫秒)")
    redacted: bool = Field(default=False, description="是否已脱敏")
    error: str | None = Field(default=None, description="错误信息")


class TaskRun(BaseModel):
    """任务运行记录"""

    task_run_id: str = Field(description="任务运行 ID")
    session_id: str = Field(description="会话 ID")
    project_id: str = Field(description="项目 ID")
    user_message: str = Field(description="用户消息")
    normalized_intent: str | None = Field(default=None, description="规范化意图")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    plan: TaskPlan | None = Field(default=None, description="任务计划")
    execution_artifacts: list[ExecutionArtifact] = Field(
        default_factory=list,
        description="执行产物",
    )
    summary_text: str | None = Field(default=None, description="总结文本")
    error: str | None = Field(default=None, description="错误信息")
    trace_id: str = Field(description="追踪 ID")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


# 更新 forward references
TaskPlan.model_rebuild()
