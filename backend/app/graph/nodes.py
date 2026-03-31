"""
LangGraph 节点实现（精简版）
保留三个核心节点：agent_entry, summarize, emit_blocks
工具调用逻辑已全部迁移到 nodes_agentic.py
"""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

from app.graph.llm_client import llm_client
from app.graph.state import GraphState
from app.llm.prompts import AGENT_ENTRY_PROMPT, SUMMARY_PROMPT
from app.runtime import get_runtime_emitter
from app.schemas.task import ExecutionArtifact


def emit_runtime_event(event: str, **payload: Any):
    """向 LangGraph 自定义流通道发送运行时事件"""
    get_runtime_emitter().emit(event, **payload)


# ==================== Agent 入口决策节点 ====================

async def agent_entry_node(state: GraphState) -> dict[str, Any]:
    """
    第一层入口决策节点：
    - direct  → 直接流式回答（纯聊天/系统介绍）
    - agentic → 进入多轮工具调用循环
    """
    try:
        full_content = ""
        strategy = None
        reply_content = ""
        strategy_pattern = re.compile(r"<strategy>(.*?)</strategy>")

        # 构建能力列表（简短摘要，供入口决策参考）
        available_capabilities = state.get("available_capabilities", [])
        cap_list_lines = []
        for cap in available_capabilities[:60]:
            cap_id = cap.get("capability_id", "")
            summary = cap.get("summary") or cap.get("name") or cap.get("description", "")[:40]
            cap_list_lines.append(f"- {cap_id}: {summary}")
        capability_list = "\n".join(cap_list_lines) if cap_list_lines else "（当前项目没有任何导入的能力）"

        # 项目全局描述
        project_description = state.get("project_description") or "未知"

        emit_runtime_event("task_progress", node_name="agent_entry", progress=0.05, message="AI 正在判断请求类型")

        # 构建上下文消息
        messages = [{"role": "system", "content": AGENT_ENTRY_PROMPT.format(
            capability_list=capability_list,
            project_description=project_description,
            user_message=state["user_message"],
        )}]
        for msg in state.get("chat_history", []):
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": state["user_message"]})

        # 流式调用 LLM 进行决策
        async for chunk_type, token in llm_client.stream_chat_completion(
            messages=messages,
            temperature=0.3,
        ):
            if chunk_type == "reasoning":
                emit_runtime_event("thought_emitted", token=token)
            else:
                full_content += token
                if strategy is None:
                    if "</strategy>" in full_content:
                        match = strategy_pattern.search(full_content)
                        if match:
                            strategy_val = match.group(1).strip().lower()
                            # 只接受 direct / agentic 两种策略
                            if strategy_val in ("direct", "agentic"):
                                strategy = strategy_val
                            else:
                                strategy = "agentic"  # 兜底走工具调用
                            rest_text = full_content[match.end():]
                            if strategy == "direct" and rest_text:
                                reply_content += rest_text
                                emit_runtime_event("token_emitted", token=rest_text)
                else:
                    if strategy == "direct":
                        reply_content += token
                        emit_runtime_event("token_emitted", token=token)

        logger.debug(f"[agent_entry] AI 原始回复: {full_content}")
        # 兜底：未解析出策略，尝试从文本长度和内容特征推断
        if strategy is None:
            clean_reply = full_content.strip()
            greeting_keywords = ["你好", "您好", "hello", "hi", "助手", "功能", "做些什么"]
            is_simple_greeting = any(k in clean_reply.lower() for k in greeting_keywords)

            if is_simple_greeting or (len(clean_reply) > 0 and not clean_reply.startswith("{") and not clean_reply.startswith("```")):
                strategy = "direct"
                reply_content = clean_reply
                emit_runtime_event("token_emitted", token=reply_content)
            else:
                strategy = "agentic"

        logger.debug(f"[agent_entry] 决策策略: {strategy}")

        state_update: dict[str, Any] = {
            "request_complexity": strategy,
            "current_node": "agent_entry",
            "agentic_done": False,
            "agentic_iterations": 0,
        }

        if strategy == "direct":
            state_update["summary_text"] = reply_content.strip()
            state_update["agentic_done"] = True  # 直接回答，标记循环不需要启动

        return state_update

    except Exception as e:
        logger.warning(f"[agent_entry] 决策失败，降级为 agentic: {e}")
        return {
            "request_complexity": "agentic",
            "current_node": "agent_entry",
            "agentic_done": False,
            "agentic_iterations": 0,
        }


# ==================== 总结节点 ====================

async def summarize_node(state: GraphState) -> dict[str, Any]:
    """
    汇总节点：在 Agentic Loop 完成后对执行结果进行自然语言汇总。
    若 summary_text 已由 agentic_loop 填写（finish 动作），则跳过 LLM 调用。
    """
    # agentic_loop 在 action=finish 时已流式输出并写入 summary_text
    if state.get("summary_text"):
        emit_runtime_event("task_progress", node_name="summarize", progress=0.95, message="汇报完成")
        return {"current_node": "summarize"}

    artifacts = state.get("execution_artifacts", [])
    emit_runtime_event("task_progress", node_name="summarize", progress=0.90, message="正在整理执行结果并生成总结")

    if not artifacts:
        return {"summary_text": "没有执行任何操作。", "current_node": "summarize"}

    try:
        results_json = json.dumps(
            [a.model_dump() if hasattr(a, "model_dump") else a for a in artifacts],
            ensure_ascii=False,
            indent=2,
        )

        full_summary = ""
        async for chunk_type, token in llm_client.stream_chat_completion(
            [{"role": "user", "content": SUMMARY_PROMPT.format(
                user_message=state["user_message"],
                results=results_json,
            )}],
            temperature=0.5,
        ):
            if chunk_type == "reasoning":
                emit_runtime_event("thought_emitted", token=token)
            else:
                full_summary += token
                emit_runtime_event("token_emitted", token=token)

        return {"summary_text": full_summary, "current_node": "summarize"}

    except Exception as e:
        logger.error(f"[summarize] 失败: {e}", exc_info=True)
        return {"summary_text": f"执行完成，但总结生成失败: {e}", "current_node": "summarize"}


# ==================== UI Block 生成节点 ====================

async def emit_blocks_node(state: GraphState) -> dict[str, Any]:
    """UI Block 生成节点（仅保留审批类 block，执行记录由运行时事件流承载）"""
    emit_runtime_event("task_progress", node_name="emit_blocks", progress=0.98, message="正在组织前端展示结构")
    return {"ui_blocks": [], "current_node": "emit_blocks"}
