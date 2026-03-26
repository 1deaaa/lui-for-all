"""
LangGraph 状态定义
定义 Talk-to-Interface 的状态机状态
"""

from typing import Annotated, Any

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app.schemas.capability import Capability, SafetyLevel
from app.schemas.policy import PolicyAction, PolicyVerdict
from app.schemas.task import ApprovalStatus, ExecutionArtifact, TaskPlan


def merge_lists(left: list, right: list) -> list:
    """合并列表的 reducer 函数"""
    return left + right


class GraphState(TypedDict):
    """LangGraph 状态定义"""

    # 会话标识
    session_id: str
    project_id: str
    trace_id: str
    project_base_url: str
    project_username: str | None
    project_password: str | None

    # 用户输入
    user_message: str
    normalized_intent: str | None

    # 请求复杂度分类: "direct"(纯聊天) | "simple"(单步只读) | "complex"(完整流程)
    request_complexity: str | None

    # 可用能力列表 (预加载)
    available_capabilities: list[dict[str, Any]]

    # 能力选择
    selected_capabilities: Annotated[list[Capability], merge_lists]

    # 任务计划
    task_plan: TaskPlan | None

    # 策略判定
    policy_verdicts: Annotated[list[PolicyVerdict], merge_lists]

    # 审批状态
    approval_status: ApprovalStatus

    # 执行产物
    execution_artifacts: list[ExecutionArtifact]

    # 结果
    summary_text: str | None

    # UI 输出
    ui_blocks: Annotated[list[dict[str, Any]], merge_lists]

    # 错误
    error: str | None

    # 当前节点名称 (用于调试)
    current_node: str | None


class IntentParseResult(BaseModel):
    """意图解析结果"""

    normalized_intent: str = Field(description="规范化后的意图")
    domain: str | None = Field(default=None, description="识别的业务领域")
    keywords: list[str] = Field(default_factory=list, description="关键词列表")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")


class CapabilitySelectionResult(BaseModel):
    """能力选择结果"""

    capabilities: list[Capability] = Field(default_factory=list, description="选中的能力列表")
    reasoning: str | None = Field(default=None, description="选择理由")


class TaskPlanResult(BaseModel):
    """任务计划结果"""

    plan: TaskPlan = Field(description="任务计划")
    reasoning: str | None = Field(default=None, description="计划理由")


class SummaryResult(BaseModel):
    """总结结果"""

    summary_text: str = Field(description="总结文本")
    key_findings: list[str] = Field(default_factory=list, description="关键发现")


class UIBlockDecision(BaseModel):
    """UI Block 决策结果"""

    block_type: str = Field(description="Block 类型")
    block_data: dict[str, Any] = Field(default_factory=dict, description="Block 数据")
    priority: int = Field(default=0, description="显示优先级")
