"""
LangGraph 图定义（Agentic Loop 版本）
简洁三层架构：
  agent_entry → agentic_loop（自回环）→ summarize → emit_blocks → END
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    agent_entry_node,
    emit_blocks_node,
    summarize_node,
)
from app.graph.nodes_agentic import agentic_loop_node
from app.graph.state import GraphState


def _entry_router(state: GraphState) -> str:
    """
    根据 agent_entry 的决策路由：
    - direct  → END（直接回答，不走工具调用）
    - agentic → agentic_loop（进入多轮工具调用循环）
    """
    error = state.get("error")
    if error:
        return END

    complexity = state.get("request_complexity", "agentic")
    if complexity == "direct":
        return END
    return "agentic_loop"


def _loop_router(state: GraphState) -> str:
    """
    根据每轮 agentic_loop 的输出决定是否继续：
    - agentic_done=True  → summarize
    - 有 error           → END（跳过汇总）
    - 否则               → agentic_loop（自回环）
    """
    if state.get("error"):
        return END
    if state.get("agentic_done", False):
        return "summarize"
    return "agentic_loop"


def create_talk_to_interface_graph(use_sqlite: bool = True):
    """创建 Agentic Loop 图"""
    workflow = StateGraph(GraphState)

    # ── 节点注册 ──
    workflow.add_node("agent_entry", agent_entry_node)
    workflow.add_node("agentic_loop", agentic_loop_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("emit_blocks", emit_blocks_node)

    # ── 入口 ──
    workflow.set_entry_point("agent_entry")

    # ── 入口路由：direct 直接结束，其余进 agentic_loop ──
    workflow.add_conditional_edges(
        "agent_entry",
        _entry_router,
        {
            "agentic_loop": "agentic_loop",
            END: END,
        },
    )

    # ── Agentic Loop 自回环路由 ──
    workflow.add_conditional_edges(
        "agentic_loop",
        _loop_router,
        {
            "agentic_loop": "agentic_loop",   # 继续循环
            "summarize": "summarize",          # 完成，进入汇总
            END: END,                          # 出错，直接终止
        },
    )

    # ── 汇总链路 ──
    workflow.add_edge("summarize", "emit_blocks")
    workflow.add_edge("emit_blocks", END)

    # ── 编译（内存 checkpointer，支持 interrupt 恢复）──
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# 默认实例
graph_app = create_talk_to_interface_graph(use_sqlite=False)
