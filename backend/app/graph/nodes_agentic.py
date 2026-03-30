"""
Agentic Loop 核心节点
实现 ReAct 多轮工具调用循环：Think → Call → Observe → Think → ... → Finish
"""

import json
import logging
import uuid
from typing import Any

from langgraph.types import interrupt

from app.graph.llm_client import llm_client
from app.graph.state import GraphState
from app.llm.prompts import AGENTIC_LOOP_SYSTEM_PROMPT
from app.runtime import get_runtime_emitter
from app.services.execution_service import ExecutionService

logger = logging.getLogger(__name__)

# 最大循环轮次，防止失控
MAX_ITERATIONS = 10

# 只读安全等级
READ_ONLY_SAFETY = {"readonly_safe", "readonly_sensitive"}
# 写入安全等级（需要审批）
WRITE_SAFETY = {"soft_write", "hard_write", "critical"}


def _emit(event: str, **payload: Any):
    """向 LangGraph 自定义流通道发送运行时事件"""
    get_runtime_emitter().emit(event, **payload)


def _build_capability_list(available_capabilities: list[dict]) -> str:
    """构建接口列表文本，注入 Agentic System Prompt"""
    lines = []
    for cap in available_capabilities[:80]:
        cap_id = cap.get("capability_id", "")
        safety = cap.get("safety_level", "readonly_safe")
        name = cap.get("name") or ""
        desc = (cap.get("description") or "")[:60]
        routes = cap.get("backed_by_routes", [])
        # 取第一个路由作为 route_id 示例
        route_id = ""
        if routes and isinstance(routes, list):
            first = routes[0]
            if isinstance(first, dict):
                route_id = first.get("route_id", "")
        lines.append(f"- {route_id or cap_id} | {safety} | {name}：{desc}")
    return "\n".join(lines) if lines else "（无可用接口）"


def _build_messages(state: GraphState) -> list[dict]:
    """构建本轮 LLM 消息列表"""
    system_prompt = AGENTIC_LOOP_SYSTEM_PROMPT.format(
        project_description=state.get("project_description") or "未知",
        capability_list=_build_capability_list(state.get("available_capabilities", [])),
    )

    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    # 历史多轮对话上下文（非 Agentic 循环的外部对话历史）
    for msg in state.get("chat_history", []):
        messages.append({"role": msg["role"], "content": msg["content"]})

    # 本次任务：进入真正的流式调度
    messages.append({"role": "user", "content": state["user_message"]})

    # 后续轮：加入历史记录（AI 的决策 + 工具执行结果）
    for entry in state.get("agentic_history", []):
        role = entry.get("role", "assistant")
        content = entry.get("content", "")
        messages.append({"role": role, "content": content})

    return messages


def _parse_route(route_id: str) -> tuple[str, str]:
    """将 route_id 解析为 (method, path)"""
    parts = route_id.split(":", 1)
    if len(parts) == 2:
        return parts[0].strip().upper(), parts[1].strip()
    return "GET", route_id


async def _execute_read_call(
    call: dict,
    state: GraphState,
) -> dict:
    """立即执行一个只读接口调用，返回结果摘要"""
    route_id = call.get("route_id", "")
    parameters = call.get("parameters", {})
    call_id = call.get("call_id", str(uuid.uuid4()))
    step_id = str(uuid.uuid4())

    method, path = _parse_route(route_id)

    _emit(
        "tool_started",
        tool_name="http_request",
        title=f"调用 {route_id}",
        detail=call.get("reasoning", ""),
        step_id=step_id,
        route_id=route_id,
    )

    base_url = state.get("project_base_url", "http://localhost:8000").rstrip("/")
    from app.executor.http_executor import HTTPExecutor
    from app.services.auth_session_service import AuthSessionService

    auth = AuthSessionService()
    headers = auth.build_headers({"Content-Type": "application/json"})

    try:
        executor = HTTPExecutor(base_url=base_url, trace_id=state.get("trace_id"))
        status_code, response_body, duration_ms = await executor.execute(
            method=method,
            path=path if path.startswith("/") else f"/{path}",
            headers=headers,
            params=parameters if method == "GET" else None,
            body=parameters if method in ("POST", "PUT", "PATCH") else None,
        )
        auth.capture_token(response_body)

        _emit(
            "tool_completed",
            tool_name="http_request",
            title=f"✓ {route_id} → HTTP {status_code}",
            detail=f"耗时 {duration_ms}ms",
            step_id=step_id,
            route_id=route_id,
            status_code=status_code,
        )

        # 截断超大响应，避免 LLM token 爆炸
        body_str = json.dumps(response_body, ensure_ascii=False)
        if len(body_str) > 4000:
            body_str = body_str[:4000] + "... [已截断]"

        return {
            "call_id": call_id,
            "route_id": route_id,
            "status": "success",
            "status_code": status_code,
            "result": body_str,
            "artifact": {
                "artifact_id": str(uuid.uuid4()),
                "step_id": step_id,
                "route_id": route_id,
                "method": method,
                "url": f"{base_url}{path if path.startswith('/') else '/' + path}",
                "request_body": parameters,
                "status_code": status_code,
                "response_body": response_body if isinstance(response_body, dict) else {"text": str(response_body)},
                "duration_ms": duration_ms,
                "redacted": False,
                "error": None,
            }
        }

    except Exception as exc:
        _emit(
            "tool_completed",
            tool_name="http_request",
            title=f"✗ {route_id} 调用失败",
            detail=str(exc),
            step_id=step_id,
            route_id=route_id,
            status_code=0,
        )
        return {
            "call_id": call_id,
            "route_id": route_id,
            "status": "error",
            "status_code": 0,
            "result": f"调用失败: {exc}",
        }


async def agentic_loop_node(state: GraphState) -> dict[str, Any]:
    """
    Agentic Loop 核心节点（ReAct 模式）
    每次调用：
    1. 构建上下文（历史 + 系统提示 + 可用接口）
    2. 流式调用 LLM，解析决策 JSON
    3. action=call → 执行只读，排队写入（等审批）
    4. action=finish → 流式输出最终报告，结束循环
    """
    iterations = state.get("agentic_iterations", 0) + 1
    logger.info(f"[agentic_loop] 第 {iterations} 轮开始")

    # 超限保护
    if iterations > MAX_ITERATIONS:
        logger.warning(f"[agentic_loop] 超过最大轮次 {MAX_ITERATIONS}，强制结束")
        return {
            "agentic_done": True,
            "agentic_iterations": iterations,
            "summary_text": f"执行超过最大轮次 {MAX_ITERATIONS} 轮，已强制终止。",
        }

    # 发射轮次通知
    _emit("agentic_iteration", iteration=iterations)
    _emit("task_progress", node_name="agentic_loop", progress=min(0.85, 0.1 + iterations * 0.12), message=f"第 {iterations} 轮推理中")

    # 构建消息
    messages = _build_messages(state)

    # 流式调用 LLM
    full_text = ""
    is_json_mode = None  # None:未判定, True:调用接口JSON, False:直接回答(纯文本)
    early_buffer = ""

    try:
        async for chunk_type, token in llm_client.stream_chat_completion(
            messages=messages,
            temperature=0.3,
        ):
            if chunk_type == "reasoning":
                _emit("thought_emitted", token=token)
            else:
                full_text += token

    except Exception as exc:
        logger.error(f"[agentic_loop] LLM 调用失败: {exc}", exc_info=True)
        return {
            "agentic_done": True,
            "agentic_iterations": iterations,
            "error": f"AI 决策失败: {exc}",
        }

    # 如果全为空（网络极度异常），或者走到这儿是 is_json_mode=True
    # 解析 JSON 决策
    try:
        import json_repair
        # 提取 JSON，LLM 可能包在 ```json ``` 内
        text_clean = full_text.strip()
        if text_clean.startswith("```"):
            text_clean = text_clean.split("```", 2)[1]
            if text_clean.startswith("json"):
                text_clean = text_clean[4:]
            text_clean = text_clean.rsplit("```", 1)[0].strip()

        decision = json_repair.loads(text_clean)
        # 如果 text_clean 没提取好，json_repair 甚至能直接解析原始带有 markdown 的文本
        if not isinstance(decision, dict):
            decision = json_repair.loads(full_text)
            
        if not isinstance(decision, dict):
            raise ValueError("解析结果不是 JSON 对象")
            
    except Exception as exc:
        logger.error(f"[agentic_loop] JSON 解析失败: {exc}\n原文: {full_text[:500]}")
        # 增加鲁棒性：如果无法解析 JSON，但内容看起来像是在直接回答，则强制 finish
        if len(full_text) > 20 and not full_text.strip().startswith("{"):
            import asyncio
            # 伪流式发射：每次发2个字符，间隔0.025秒（每秒约80字符，符合视觉习惯）
            for i in range(0, len(full_text), 2):
                _emit("token_emitted", token=full_text[i: i+2])
                await asyncio.sleep(0.025)
            
            return {
                "agentic_done": True,
                "agentic_iterations": iterations,
                "summary_text": full_text.strip(),
            }
        
        return {
            "agentic_done": True,
            "agentic_iterations": iterations,
            "error": f"AI 输出格式错误，无法解析决策 JSON: {exc}",
        }

    action = decision.get("action", "finish")
    think_text = decision.get("think", "")

    # 发射本轮推理思考到前端
    if think_text:
        _emit("thought_emitted", token=f"\n**[第{iterations}轮]** {think_text}\n")

    # 追加 AI 本轮决策到历史
    history_entry_ai: dict[str, Any] = {
        "role": "assistant",
        "content": full_text,
    }
    new_history: list[dict[str, Any]] = [history_entry_ai]
    new_artifacts: list[Any] = []

    if action == "finish":
        # AI 决定结束，交给总结节点汇报
        return {
            "agentic_done": True,
            "agentic_iterations": iterations,
            "agentic_history": new_history,
            "execution_artifacts": new_artifacts,
        }

    elif action == "call":
        calls: list[dict] = decision.get("calls", [])
        if not calls:
            logger.warning("[agentic_loop] action=call 但 calls 为空，强制结束")
            return {
                "agentic_done": True,
                "agentic_iterations": iterations,
                "agentic_history": new_history,
                "summary_text": "AI 决定调用接口但未提供具体接口，任务结束。",
            }

        # 分流：只读立即执行，写入排队审批
        read_calls = [c for c in calls if c.get("safety_level", "readonly_safe") in READ_ONLY_SAFETY]
        write_calls = [c for c in calls if c.get("safety_level", "readonly_safe") in WRITE_SAFETY]

        # 执行所有只读调用
        tool_results_summary: list[str] = []
        for call in read_calls:
            result = await _execute_read_call(call, state)
            tool_results_summary.append(
                f'call_id={result["call_id"]} route={result["route_id"]} status={result["status_code"]}\n结果: {result["result"]}'
            )
            # 收集执行产物
            if result.get("artifact"):
                from app.schemas.task import ExecutionArtifact
                try:
                    artifact = ExecutionArtifact(**result["artifact"])
                    new_artifacts.append(artifact)
                except Exception:
                    pass  # 非关键路径，忽略

        # 处理写入调用——审批
        approved_write_results: list[str] = []
        for write_call in write_calls:
            write_id = str(uuid.uuid4())
            route_id = write_call.get("route_id", "")
            method, path = _parse_route(route_id)

            # 向前端发射审批请求事件
            _emit(
                "write_approval_required",
                write_id=write_id,
                route_id=route_id,
                method=method,
                path=path,
                parameters=write_call.get("parameters", {}),
                reasoning=write_call.get("reasoning", ""),
                safety_level=write_call.get("safety_level", "soft_write"),
            )

            # interrupt：暂停图执行，等待用户操作
            approval_result = interrupt({
                "type": "write_approval",
                "write_id": write_id,
                "route_id": route_id,
                "method": method,
                "path": path,
                "parameters": write_call.get("parameters", {}),
                "reasoning": write_call.get("reasoning", ""),
                "safety_level": write_call.get("safety_level", "soft_write"),
            })

            approved = approval_result.get("approved", False)

            if approved:
                # 执行写入
                write_result = await _execute_read_call(write_call, state)  # 复用执行函数
                approved_write_results.append(
                    f'write_id={write_id} route={route_id} status={write_result["status_code"]}\n结果: {write_result["result"]}'
                )
                if write_result.get("artifact"):
                    from app.schemas.task import ExecutionArtifact
                    try:
                        artifact = ExecutionArtifact(**write_result["artifact"])
                        new_artifacts.append(artifact)
                    except Exception:
                        pass
            else:
                approved_write_results.append(
                    f'write_id={write_id} route={route_id} → 用户已拒绝，跳过执行'
                )

        # 将本轮工具结果追加为 observation 消息（供下轮 LLM 参考）
        all_results = tool_results_summary + approved_write_results
        if all_results:
            observation_content = "【工具执行结果】\n" + "\n\n".join(all_results)
            new_history.append({
                "role": "user",
                "content": observation_content,
            })

        return {
            "agentic_done": False,
            "agentic_iterations": iterations,
            "agentic_history": new_history,
            "execution_artifacts": new_artifacts,
        }

    else:
        # 未知 action，强制结束
        logger.warning(f"[agentic_loop] 未知 action: {action}，强制结束")
        return {
            "agentic_done": True,
            "agentic_iterations": iterations,
            "agentic_history": new_history,
            "summary_text": f"AI 输出了未知指令 action={action}，任务中止。",
        }
