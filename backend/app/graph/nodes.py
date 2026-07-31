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
from app.schemas.ui_block import A2UIAction, A2UIBlock, A2UIComponent


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
        strategy: str | None = None
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

        project_description = state.get("project_description") or "未知"
        response_language = state.get("response_language") or "简体中文"

        emit_runtime_event("task_progress", node_name="agent_entry", progress=0.05, message="AI 正在判断请求类型")

        # 单次流式：同一轮同时完成策略判定与 direct 正文输出，避免 direct 走两次模型推理。
        entry_messages: list[dict[str, str]] = [{
            "role": "system",
            "content": AGENT_ENTRY_PROMPT.format(
                capability_list=capability_list,
                project_description=project_description,
                user_message=user_message,
                response_language=response_language,
            ),
        }]
        for msg in state.get("chat_history", []):
            role = str(msg.get("role") or "")
            if role in ("user", "assistant"):
                entry_messages.append({"role": role, "content": str(msg.get("content") or "")})
        entry_messages.append({"role": "user", "content": user_message})

        strategy_prefix_buffer = ""
        strategy_pattern = re.compile(r"<strategy>\s*(direct|agentic)\s*</strategy>", re.IGNORECASE)

        async for chunk_type, token in llm_client.stream_chat_completion(
            messages=entry_messages,
            temperature=0.3,
        ):
            if chunk_type == "reasoning":
                emit_runtime_event("thought_emitted", token=token)
                continue

            token_text = str(token or "")
            if not token_text:
                continue

            if strategy is None:
                strategy_prefix_buffer += token_text
                match = strategy_pattern.search(strategy_prefix_buffer)
                if not match:
                    # 防止异常输出导致缓冲无限增长；判定失败时降级走 agentic。
                    if len(strategy_prefix_buffer) > 2048:
                        logger.warning("[agent_entry] 未检测到策略标签，降级为 agentic")
                        strategy = "agentic"
                    continue

                strategy = match.group(1).strip().lower()
                remainder = strategy_prefix_buffer[match.end():]
                strategy_prefix_buffer = ""

                if strategy == "direct" and remainder:
                    reply_content += remainder
                    emit_runtime_event("token_emitted", token=remainder)
                continue

            if strategy == "direct":
                reply_content += token_text
                emit_runtime_event("token_emitted", token=token_text)

        if strategy not in ("direct", "agentic"):
            logger.warning("[agent_entry] 策略判定失败，降级为 agentic")
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


def _build_a2ui_fallback(state: GraphState) -> A2UIBlock:
    """在结构化模型输出不可用时，生成同样经过 schema 约束的结果界面。"""
    summary = str(state.get("summary_text") or "没有可展示的结果。").strip()
    components: list[A2UIComponent] = [
        A2UIComponent(
            component_id="result-title",
            component_type="heading",
            props={"text": "执行结果", "level": 2},
        ),
        A2UIComponent(
            component_id="result-summary",
            component_type="text",
            props={"text": summary, "tone": "default"},
            actions=[
                A2UIAction(
                    action_type="copy",
                    label="复制结果",
                    payload={"text": summary},
                )
            ],
        ),
    ]

    artifacts = state.get("execution_artifacts", []) or []
    rows = []
    for artifact in artifacts[:20]:
        item = artifact.model_dump() if hasattr(artifact, "model_dump") else dict(artifact)
        rows.append(
            {
                "method": str(item.get("method") or ""),
                "route": str(item.get("route_id") or ""),
                "status": item.get("status_code") if item.get("status_code") is not None else "失败",
                "duration": f"{item.get('duration_ms')} ms" if item.get("duration_ms") is not None else "-",
            }
        )

    if rows:
        components.append(
            A2UIComponent(
                component_id="execution-table",
                component_type="table",
                props={
                    "columns": [
                        {"key": "method", "label": "方法"},
                        {"key": "route", "label": "路由"},
                        {"key": "status", "label": "状态"},
                        {"key": "duration", "label": "耗时"},
                    ],
                    "rows": rows,
                },
            )
        )

    return A2UIBlock(
        surface_id=f"task-{str(state.get('session_id') or 'result')[:64]}",
        components=components,
    )


async def emit_blocks_node(state: GraphState) -> dict[str, Any]:
    """使用模型生成受控 A2UI，并在服务端校验后交给 SSE 事件流。"""
    emit_runtime_event("task_progress", node_name="emit_blocks", progress=0.98, message="正在组织前端展示结构")

    artifacts = state.get("execution_artifacts", []) or []
    artifact_summary = []
    for artifact in artifacts[:20]:
        item = artifact.model_dump() if hasattr(artifact, "model_dump") else dict(artifact)
        artifact_summary.append(
            {
                "method": item.get("method"),
                "route_id": item.get("route_id"),
                "status_code": item.get("status_code"),
                "duration_ms": item.get("duration_ms"),
                "error": item.get("error"),
            }
        )

    prompt = {
        "user_request": str(state.get("user_message") or ""),
        "summary": str(state.get("summary_text") or "没有可展示的结果。"),
        "execution_artifacts": artifact_summary,
    }
    generation_messages = [
        {
            "role": "user",
            "content": (
                "请为下面的任务结果生成一个 LUI 受控 A2UI 界面。只能输出符合给定结构的 JSON，"
                "不得输出 HTML、Markdown、JavaScript、模板表达式、URL 或自定义事件处理器。"
                "组件只能使用 heading、text、metric、table、status、button；属性只能使用各组件目录中允许的字段。"
                "优先生成简洁的结果摘要；只有在确有执行记录时才生成 table。"
                "button 只能使用 copy 或 submit 动作，copy 的 payload 只能包含 text。"
                "如果没有适合的交互动作，可以不生成 button。\n\n"
                "JSON 结构："
                '{"block_type":"a2ui","version":"0.1","surface_id":"task-result",'
                '"components":[{"component_id":"summary","component_type":"text",'
                '"props":{"text":"...","tone":"default"},"actions":[]}]}\n\n'
                f"任务数据：{json.dumps(prompt, ensure_ascii=False)}"
            ),
        }
    ]

    try:
        generated = await llm_client.parse_json_response(
            generation_messages,
            A2UIBlock,
            temperature=0.2,
            usage_key="main",
        )
        block = generated
    except Exception as exc:
        logger.warning("[emit_blocks] A2UI 结构化生成失败，使用受控兜底: %s", exc)
        block = _build_a2ui_fallback(state)

    return {
        "ui_blocks": [block.model_dump(mode="json")],
        "current_node": "emit_blocks",
    }
