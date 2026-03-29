"""
LangGraph 图定义
双路图：classify_request 后分为简单流(simple) / 完整流(complex) / 直接回答(direct)
"""

from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

try:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
except ModuleNotFoundError:
    AsyncSqliteSaver = None

from app.config import settings
from app.graph.nodes import (
    agent_entry_node,
    approval_gate_node,
    direct_answer_node,
    draft_plan_node,
    emit_blocks_node,
    execute_requests_node,
    parse_intent_node,
    policy_check_node,
    select_capabilities_node,
    simple_execute_node,
    summarize_node,
)
from app.graph.state import GraphState
from app.schemas.task import ApprovalStatus


def get_checkpointer():
    """获取 checkpointer 实例"""
    db_path = Path(settings.checkpoint_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if AsyncSqliteSaver is None:
        return MemorySaver()

    return AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path)


def _complexity_router(state: GraphState) -> str:
    """根据分类结果路由到不同子图"""
    complexity = state.get("request_complexity", "complex")
    error = state.get("error")

    if error:
        return END

    if complexity == "direct":
        return "direct_answer"
    elif complexity == "simple":
        return "simple_execute"
    else:
        # complex → 走完整链路
        return "parse_intent"


def _approval_router(state: GraphState) -> str:
    """审批结果路由"""
    error = state.get("error")
    approval_status = state.get("approval_status")

    if error:
        return END
    if approval_status == "rejected" or approval_status == ApprovalStatus.REJECTED:
        return END

    return "execute_requests"


def create_talk_to_interface_graph(use_sqlite: bool = True):
    """创建双路 Talk-to-Interface 执行图"""
    workflow = StateGraph(GraphState)

    # ── 公共入口节点 ──
    workflow.add_node("agent_entry", agent_entry_node)

    # ── 直接回答节点（流式） ──
    workflow.add_node("direct_answer", direct_answer_node)

    # ── 简单流节点（simple） ──
    workflow.add_node("simple_execute", simple_execute_node)

    # ── 完整流节点（complex） ──
    workflow.add_node("parse_intent", parse_intent_node)
    workflow.add_node("select_capabilities", select_capabilities_node)
    workflow.add_node("draft_plan", draft_plan_node)
    workflow.add_node("policy_check", policy_check_node)
    workflow.add_node("approval_gate", approval_gate_node)
    workflow.add_node("execute_requests", execute_requests_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("emit_blocks", emit_blocks_node)

    # ── 入口 ──
    workflow.set_entry_point("agent_entry")

    # ── 决策后路由 ──
    workflow.add_conditional_edges(
        "agent_entry",
        _complexity_router,
        {
            "direct_answer": "direct_answer",
            "simple_execute": "simple_execute",
            "parse_intent": "parse_intent",
            END: END,
        },
    )

    # ── 通往导出 ──
    workflow.add_edge("direct_answer", "emit_blocks")
    workflow.add_edge("simple_execute", END)

    # ── 完整流主链 ──
    workflow.add_edge("parse_intent", "select_capabilities")
    workflow.add_edge("select_capabilities", "draft_plan")
    workflow.add_edge("draft_plan", "policy_check")
    workflow.add_edge("policy_check", "approval_gate")

    # ── 审批门路由 ──
    workflow.add_conditional_edges(
        "approval_gate",
        _approval_router,
        {
            "execute_requests": "execute_requests",
            END: END,
        },
    )

    workflow.add_edge("execute_requests", "summarize")
    workflow.add_edge("summarize", "emit_blocks")
    workflow.add_edge("emit_blocks", END)

    # ── 编译 ──
    checkpointer = get_checkpointer() if use_sqlite else MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# 默认实例（内存持久化，避免 SQLite 初始化副作用）
graph_app = create_talk_to_interface_graph(use_sqlite=False)
