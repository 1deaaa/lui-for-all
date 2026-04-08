"""
LangGraph 节点实现（精简版）
保留三个核心节点：agent_entry, summarize, emit_blocks
工具调用逻辑已全部迁移到 nodes_agentic.py
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

from app.graph.llm_client import llm_client
from app.graph.state import GraphState
from app.llm.prompts import DIRECT_ANSWER_PROMPT, SUMMARY_PROMPT
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
        strategy = "agentic"
        reply_content = ""
        user_message = str(state.get("user_message") or "")

        # 构建能力列表（简短摘要，供入口决策参考）
        available_capabilities = state.get("available_capabilities", [])
        cap_list_lines = []
        for cap in available_capabilities:
            cap_id = cap.get("capability_id", "")
            summary = cap.get("summary") or cap.get("name") or cap.get("description") or ""
            cap_list_lines.append(f"- {cap_id}: {summary}")
        capability_list = "\n".join(cap_list_lines) if cap_list_lines else "（当前项目没有任何导入的能力）"

        response_language = state.get("response_language") or "简体中文"

        emit_runtime_event("task_progress", node_name="agent_entry", progress=0.05, message="AI 正在判断请求类型")

        # 第一阶段：仅做路由判定，避免把正文与策略混在同一流里造成前端“假流式”观感。
        decision_prompt = (
            "你是请求路由判定器。\n"
            "如果用户只是闲聊、打招呼、询问系统能力介绍，输出 direct。\n"
            "如果用户要求查询数据、调用接口、执行任务，输出 agentic。\n"
            "只允许输出一个词：direct 或 agentic。\n\n"
            f"用户输入：{user_message}"
        )

        decision_raw = await llm_client.simple_completion(
            prompt=decision_prompt,
            temperature=0.0,
            max_tokens=8,
        )
        decision_text = str(decision_raw or "").strip().lower()
        if "direct" in decision_text and "agentic" not in decision_text:
            strategy = "direct"

        # 第二阶段：direct 分支单独发起云端流式回答，token 原样透传。
        if strategy == "direct":
            direct_system_prompt = (
                DIRECT_ANSWER_PROMPT.format(
                    capability_list=capability_list,
                    user_message=user_message,
                )
                + f"\n\n补充要求：优先使用 {response_language} 输出。"
            )
            direct_messages: list[dict[str, str]] = [{"role": "system", "content": direct_system_prompt}]
            for msg in state.get("chat_history", []):
                role = str(msg.get("role") or "")
                if role in ("user", "assistant"):
                    direct_messages.append({"role": role, "content": str(msg.get("content") or "")})
            direct_messages.append({"role": "user", "content": user_message})

            async for chunk_type, token in llm_client.stream_chat_completion(
                messages=direct_messages,
                temperature=0.4,
            ):
                if chunk_type == "reasoning":
                    emit_runtime_event("thought_emitted", token=token)
                else:
                    token_text = str(token or "")
                    if not token_text:
                        continue
                    reply_content += token_text
                    emit_runtime_event("token_emitted", token=token_text)

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
    final_answer_draft = str(state.get("final_answer_draft") or "").strip()
    response_language = state.get("response_language") or "简体中文"
    response_locale = (state.get("response_locale") or "zh-CN").lower()
    emit_runtime_event("task_progress", node_name="summarize", progress=0.90, message="正在整理执行结果并生成总结")

    if not artifacts:
        if final_answer_draft:
            prompt = (
                "你是结果整理助手。请将下面的任务结论整理为给用户的最终回复，"
                "保留事实，不要新增臆测，使用 Markdown，语言优先使用 "
                f"{response_language}。\n\n"
                f"用户原始请求:\n{state['user_message']}\n\n"
                f"任务结论草稿:\n{final_answer_draft}\n"
            )

            full_summary = ""
            async for chunk_type, token in llm_client.stream_chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.3,
            ):
                if chunk_type == "reasoning":
                    emit_runtime_event("thought_emitted", token=token)
                else:
                    token_text = str(token or "")
                    if not token_text:
                        continue
                    full_summary += token_text
                    emit_runtime_event("token_emitted", token=token_text)

            return {"summary_text": full_summary or final_answer_draft, "current_node": "summarize"}

        if response_locale.startswith("en"):
            no_result_summary = "No operation was executed."
        elif response_locale.startswith("ja"):
            no_result_summary = "操作は実行されませんでした。"
        else:
            no_result_summary = "没有执行任何操作。"
        return {"summary_text": no_result_summary, "current_node": "summarize"}

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
                response_language=response_language,
            )}],
            temperature=0.5,
        ):
            if chunk_type == "reasoning":
                emit_runtime_event("thought_emitted", token=token)
            else:
                token_text = str(token or "")
                if not token_text:
                    continue
                full_summary += token_text
                emit_runtime_event("token_emitted", token=token_text)

        return {"summary_text": full_summary, "current_node": "summarize"}

    except Exception as e:
        logger.error(f"[summarize] 失败: {e}", exc_info=True)
        return {"summary_text": f"执行完成，但总结生成失败: {e}", "current_node": "summarize"}


# ==================== UI Block 生成节点 ====================

async def emit_blocks_node(state: GraphState) -> dict[str, Any]:
    """UI Block 生成节点（仅保留审批类 block，执行记录由运行时事件流承载）"""
    emit_runtime_event("task_progress", node_name="emit_blocks", progress=0.98, message="正在组织前端展示结构")
    return {"ui_blocks": [], "current_node": "emit_blocks"}
