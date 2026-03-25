"""
LangGraph 图定义
构建完整的执行流程图，使用 SQLite 持久化 checkpoint
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph

from app.config import settings
from app.graph.nodes import (
    approval_gate_node,
    draft_plan_node,
    emit_blocks_node,
    execute_requests_node,
    parse_intent_node,
    policy_check_node,
    select_capabilities_node,
    summarize_node,
)
from app.graph.state import GraphState
from app.schemas.task import ApprovalStatus


def get_checkpointer():
    """获取 checkpointer 实例"""
    # 确保目录存在
    db_path = Path(settings.checkpoint_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 使用 SQLite checkpointer
    # 注意: AsyncSqliteSaver 需要在异步上下文中使用
    # 这里返回一个工厂函数
    return lambda: AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path)


def create_talk_to_interface_graph(use_sqlite: bool = True):
    """创建 Talk-to-Interface 执行图"""
    # 创建状态图
    workflow = StateGraph(GraphState)

    # 添加节点
    workflow.add_node("parse_intent", parse_intent_node)
    workflow.add_node("select_capabilities", select_capabilities_node)
    workflow.add_node("draft_plan", draft_plan_node)
    workflow.add_node("policy_check", policy_check_node)
    workflow.add_node("approval_gate", approval_gate_node)
    workflow.add_node("execute_requests", execute_requests_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("emit_blocks", emit_blocks_node)

    # 设置入口点
    workflow.set_entry_point("parse_intent")

    # 添加边
    workflow.add_edge("parse_intent", "select_capabilities")
    workflow.add_edge("select_capabilities", "draft_plan")
    workflow.add_edge("draft_plan", "policy_check")
    workflow.add_edge("policy_check", "approval_gate")

    # 条件边：审批结果
    def approval_router(state: GraphState) -> str:
        error = state.get("error")
        approval_status = state.get("approval_status")
        
        # 调试日志
        print(f"[approval_router] error={error}, approval_status={approval_status}")
        
        if error:
            print(f"[approval_router] Routing to END due to error")
            return END
        if approval_status == "rejected" or approval_status == ApprovalStatus.REJECTED:
            print(f"[approval_router] Routing to END due to rejection")
            return END
        
        print(f"[approval_router] Routing to execute_requests")
        return "execute_requests"

    workflow.add_conditional_edges(
        "approval_gate",
        approval_router,
        {
            "execute_requests": "execute_requests",
            END: END,
        },
    )

    workflow.add_edge("execute_requests", "summarize")
    workflow.add_edge("summarize", "emit_blocks")
    workflow.add_edge("emit_blocks", END)

    # 编译图
    if use_sqlite:
        # 使用 SQLite checkpointer (生产环境)
        # 注意: 需要在异步上下文中创建
        memory_saver = MemorySaver()  # 临时使用，实际运行时替换
        app = workflow.compile(checkpointer=memory_saver)
    else:
        # 使用内存 checkpointer (开发/测试)
        memory_saver = MemorySaver()
        app = workflow.compile(checkpointer=memory_saver)

    return app


# 创建图实例 (默认使用内存，运行时可切换)
graph_app = create_talk_to_interface_graph(use_sqlite=False)
