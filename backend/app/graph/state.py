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
    project_description: str | None  # 项目全局业务描述（由 AI 或用户填写）

    # 整个对话上下文历史
    chat_history: list[dict[str, Any]]

    # 用户输入
    user_message: str

    # 请求类型: "direct"(纯聊天) | "agentic"(工具调用循环)
    request_complexity: str | None

    # 可用能力列表（预加载，只读，供所有节点参考）
    available_capabilities: list[dict[str, Any]]

    # ───── Agentic Loop 核心字段 ─────
    # 多轮对话历史（包含 AI 决策 + 工具结果），采用 append-only 策略
    agentic_history: Annotated[list[dict[str, Any]], merge_lists]
    # 本轮 Loop 是否已结束（AI 决定汇报时设为 True）
    agentic_done: bool
    # 当前循环轮次（防止无限循环，最多 MAX_ITER 轮）
    agentic_iterations: int
    # 本轮 AI 决策中发现的待审批写入操作列表（每轮开始时重置）
    pending_writes: list[dict[str, Any]]

    # 执行产物（所有轮次的 HTTP 执行结果汇总）
    execution_artifacts: Annotated[list[ExecutionArtifact], merge_lists]

    # 最终结果
    summary_text: str | None

    # UI 输出
    ui_blocks: Annotated[list[dict[str, Any]], merge_lists]

    # 错误
    error: str | None

    # 当前节点名称（用于调试）
    current_node: str | None


class IntentParseResult(BaseModel):
    """意图解析结果（仅保留供审计字段）"""

    normalized_intent: str = Field(description="规范化后的意图")
    domain: str | None = Field(default=None, description="识别的业务领域")
    keywords: list[str] = Field(default_factory=list, description="关键词列表")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")


class SummaryResult(BaseModel):
    """总结结果"""

    summary_text: str = Field(description="总结文本")
    key_findings: list[str] = Field(default_factory=list, description="关键发现")


class UIBlockDecision(BaseModel):
    """UI Block 决策结果"""

    block_type: str = Field(description="Block 类型")
    block_data: dict[str, Any] = Field(default_factory=dict, description="Block 数据")
    priority: int = Field(default=0, description="显示优先级")
