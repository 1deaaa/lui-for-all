"""
Agentic Loop 核心节点
实现 ReAct 多轮工具调用循环：Think → Call → Observe → Think → ... → Finish
"""

import asyncio
import json
import logging
import re
import uuid
from typing import Any

from langchain_core.runnables.config import RunnableConfig
from langgraph.types import interrupt

# 全局内存缓存：专门对抗 LangGraph interrupt 的恢复重跑机制，拦截重复副作用
_task_run_llm_cache = {}

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

# 项目级认证缓存：{ project_id: {token, auth_mode, cookie_name} }
# 进程内持久化，同一个项目的所有会话共享，无需每轮重新登录
_project_token_cache: dict[str, dict] = {}
# 每个项目的登录锁，防止并发竞态导致重复登录
_project_login_locks: dict[str, asyncio.Lock] = {}


async def _ensure_project_token(state: GraphState) -> str | None:
    """
    确保当前项目已登录并持有有效 token。
    使用每项目锁防止并发竞态导致重复登录。
    """
    project_id = state.get("project_id", "")
    if project_id in _project_token_cache:
        return _project_token_cache[project_id].get("token")

    login_route_id = state.get("project_login_route_id")
    username = state.get("project_username") or ""
    password = state.get("project_password") or ""
    if not (login_route_id and username):
        logger.info(f"[token_cache] project={project_id} 未配置登录路由或用户名，跳过自动登录")
        return None

    # 获取或创建该项目的登录锁
    if project_id not in _project_login_locks:
        _project_login_locks[project_id] = asyncio.Lock()
    async with _project_login_locks[project_id]:
        # double-check：锁内再次检查，避免多个协程串行重复登录
        if project_id in _project_token_cache:
            return _project_token_cache[project_id].get("token")

        user_field = state.get("project_login_field_username") or "username"
        pass_field = state.get("project_login_field_password") or "password"

        logger.info(f"[token_cache] project={project_id} 开始自动登录 route={login_route_id} user_field={user_field}")
        result = await _execute_http(
            route_id=login_route_id,
            parameters={user_field: username, pass_field: password},
            state=state,
            bearer_token=None,
        )
        token = result.get("captured_token")
        auth_mode = result.get("captured_auth_mode", "bearer")
        cookie_name = result.get("captured_cookie_name")
        if token:
            _project_token_cache[project_id] = {
                "token": token,
                "auth_mode": auth_mode,
                "cookie_name": cookie_name,
            }
            logger.info(
                f"[token_cache] project={project_id} 登录成功 "
                f"auth_mode={auth_mode} cookie_name={cookie_name} "
                f"token={token[:8]}..."
            )
        else:
            logger.warning(
                f"[token_cache] project={project_id} 登录失败，"
                f"状态码={result.get('status_code')} "
                f"响应体={str(result.get('response_body', ''))[:200]}"
            )
        return token


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
    login_route = state.get("project_login_route_id") or ""
    caps = [
        c for c in state.get("available_capabilities", [])
        if not login_route or not any(
            isinstance(r, dict) and r.get("route_id") == login_route
            for r in c.get("backed_by_routes", [])
        )
    ]
    system_prompt = AGENTIC_LOOP_SYSTEM_PROMPT.format(
        project_description=state.get("project_description") or "未知",
        capability_list=_build_capability_list(caps),
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


async def _execute_http(
    route_id: str,
    parameters: dict,
    state: GraphState,
    bearer_token: str | None,
    auth_mode: str = "bearer",
    cookie_name: str | None = None,
) -> dict:
    """底层 HTTP 执行，返回 {status_code, response_body, duration_ms, captured_token}"""
    from app.executor.http_executor import HTTPExecutor
    from app.services.auth_session_service import AuthSessionService

    method, path = _parse_route(route_id)

    # 替换路径模板变量
    path_param_keys = re.findall(r'\{(\w+)\}', path)
    remaining = dict(parameters)
    for key in path_param_keys:
        if key in remaining:
            path = path.replace(f'{{{key}}}', str(remaining.pop(key)))
    parameters = remaining

    base_url = state.get("project_base_url", "http://localhost:8000").rstrip("/")
    auth = AuthSessionService()
    if bearer_token:
        auth._token = bearer_token
        auth._auth_mode = auth_mode
        auth._cookie_name = cookie_name
    headers = auth.build_headers({"Content-Type": "application/json"})

    executor = HTTPExecutor(base_url=base_url, trace_id=state.get("trace_id"))
    norm_path = path if path.startswith("/") else f"/{path}"
    full_url = f"{base_url}{norm_path}"

    logger.info(
        f"[http] {method} {full_url} | "
        f"has_token={bool(bearer_token)} | "
        f"params={list(parameters.keys()) if parameters else []}"
    )

    status_code, response_body, duration_ms = await executor.execute(
        method=method,
        path=norm_path,
        headers=headers,
        params=parameters if method == "GET" else None,
        body=parameters if method in ("POST", "PUT", "PATCH") else None,
    )

    # 先尝试从响应体捕获 token（Bearer 模式）
    auth.capture_token(response_body)
    # 再尝试从响应 cookies 捕获（Cookie/Session 模式）
    auth.capture_from_cookies(executor.last_response_cookies)

    logger.info(
        f"[http] {method} {full_url} → {status_code} ({duration_ms}ms) | "
        f"resp_cookies={list(executor.last_response_cookies.keys())} | "
        f"captured_token={bool(auth.token)} | auth_mode={auth.auth_mode}"
    )
    if status_code == 401:
        logger.warning(
            f"[http] 401 详情 | url={full_url} | "
            f"sent_token={bearer_token[:8] + '...' if bearer_token else 'None'} | "
            f"resp_body={str(response_body)[:200]} | "
            f"resp_cookies={executor.last_response_cookies} | "
            f"resp_headers_auth={executor.last_response_headers.get('www-authenticate', 'N/A')}"
        )

    return {
        "status_code": status_code,
        "response_body": response_body,
        "duration_ms": duration_ms,
        "captured_token": auth.token,
        "captured_auth_mode": auth.auth_mode,
        "captured_cookie_name": auth.cookie_name,
        "url": full_url,
        "method": method,
        "parameters": parameters,
    }


async def _execute_read_call(
    call: dict,
    state: GraphState,
    current_token: str | None = None,
) -> dict:
    """执行一个接口调用，自动处理项目级 token 缓存，返回结果摘要"""
    route_id = call.get("route_id", "")
    parameters = call.get("parameters", {})
    call_id = call.get("call_id", str(uuid.uuid4()))
    step_id = str(uuid.uuid4())

    _emit(
        "tool_started",
        tool_name="http_request",
        title=f"调用 {route_id}",
        detail=call.get("reasoning", ""),
        step_id=step_id,
        route_id=route_id,
    )

    # 从缓存取完整 auth 信息（token + mode + cookie_name）
    project_id = state.get("project_id", "")
    cached = _project_token_cache.get(project_id, {})
    token = current_token or cached.get("token")
    auth_mode = cached.get("auth_mode", "bearer")
    cookie_name = cached.get("cookie_name")

    # 无缓存时自动登录
    if not token:
        token = await _ensure_project_token(state)
        cached = _project_token_cache.get(project_id, {})
        auth_mode = cached.get("auth_mode", "bearer")
        cookie_name = cached.get("cookie_name")

    try:
        result = await _execute_http(
            route_id, parameters, state,
            bearer_token=token, auth_mode=auth_mode, cookie_name=cookie_name,
        )
        status_code = result["status_code"]
        response_body = result["response_body"]
        duration_ms = result["duration_ms"]

        # 若收到 401，清除缓存并重新登录后重试一次
        if status_code == 401:
            logger.warning(f"[exec] 401 收到，清除缓存重试 project={project_id}")
            _project_token_cache.pop(project_id, None)
            new_token = await _ensure_project_token(state)
            new_cached = _project_token_cache.get(project_id, {})
            if new_token and new_token != token:
                result = await _execute_http(
                    route_id, parameters, state,
                    bearer_token=new_token,
                    auth_mode=new_cached.get("auth_mode", "bearer"),
                    cookie_name=new_cached.get("cookie_name"),
                )
                status_code = result["status_code"]
                response_body = result["response_body"]
                duration_ms = result["duration_ms"]
                token = new_token

        # 若本次响应捕获到新 token，更新缓存（含 auth_mode 和 cookie_name）
        if result.get("captured_token") and result["captured_token"] != token:
            if project_id:
                _project_token_cache[project_id] = {
                    "token": result["captured_token"],
                    "auth_mode": result.get("captured_auth_mode", "bearer"),
                    "cookie_name": result.get("captured_cookie_name"),
                }

        _emit(
            "tool_completed",
            tool_name="http_request",
            title=f"✓ {route_id} → HTTP {status_code}",
            detail=f"耗时 {duration_ms}ms",
            step_id=step_id,
            route_id=route_id,
            status_code=status_code,
        )

        body_str = json.dumps(response_body, ensure_ascii=False)
        if len(body_str) > 32000:
            body_str = body_str[:32000] + "... [数据过长，已被系统从 32K 处截断]"

        return {
            "call_id": call_id,
            "route_id": route_id,
            "status": "success",
            "status_code": status_code,
            "result": body_str,
            "captured_token": result.get("captured_token"),
            "artifact": {
                "artifact_id": str(uuid.uuid4()),
                "step_id": step_id,
                "route_id": route_id,
                "method": result["method"],
                "url": result["url"],
                "request_body": result["parameters"],
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


async def agentic_loop_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """
    Agentic Loop 核心节点（ReAct 模式）
    每次调用：
    1. 构建上下文（历史 + 系统提示 + 可用接口）
    2. 流式调用 LLM，解析决策 JSON
    3. action=call → 执行只读，排队写入（等审批）
    4. action=finish → 流式输出最终报告，结束循环
    """
    iterations = state.get("agentic_iterations", 0) + 1
    logger.debug(f"[agentic_loop] 第 {iterations} 轮开始")

    # 超限保护
    if iterations > MAX_ITERATIONS:
        logger.warning(f"[agentic_loop] 超过最大轮次 {MAX_ITERATIONS}，强制结束")
        return {
            "agentic_done": True,
            "agentic_iterations": iterations,
            "summary_text": f"执行超过最大轮次 {MAX_ITERATIONS} 轮，已强制终止。",
        }

    task_run_id = config.get("configurable", {}).get("thread_id", "")
    cache_key = f"{task_run_id}_{iterations}"

    if cache_key in _task_run_llm_cache:
        logger.info(f"[agentic_loop] 命中打断恢复缓存，跳过 LLM 重复调用: {cache_key}")
        cached = _task_run_llm_cache[cache_key]
        decision = cached.get("decision", {})
        full_text = cached.get("full_text", "")
        think_text = cached.get("think_text", "")
    else:
        # ── 正常情况执行 LLM 推理计算 ──
        # 发射轮次通知 (由于使用了防重放缓存，重跑节点时不会重复发送通知)
        _emit("agentic_iteration", iteration=iterations)
        _emit("task_progress", node_name="agentic_loop", progress=min(0.85, 0.1 + iterations * 0.12), message=f"第 {iterations} 轮推理中")

        # 构建消息
        messages = _build_messages(state)

        # 流式调用 LLM
        full_text = ""
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

    is_first_run_of_this_iteration = cache_key not in _task_run_llm_cache

    if is_first_run_of_this_iteration:
        # 新产生的有效决策，写入防重放缓存
        _task_run_llm_cache[cache_key] = {
            "decision": decision,
            "full_text": full_text,
            "think_text": decision.get("think", ""),
        }
        
    action = decision.get("action", "finish")
    think_text = decision.get("think", "")

    # 首次执行时，发射本轮推理思考到前端
    if is_first_run_of_this_iteration and think_text:
        _emit("thought_emitted", token=f"\n**[第{iterations}轮]** {think_text}\n")

    # 追加 AI 本轮决策到历史
    history_entry_ai: dict[str, Any] = {
        "role": "assistant",
        "content": full_text,
    }
    new_history: list[dict[str, Any]] = [history_entry_ai]
    new_artifacts: list[Any] = []

    existing_history: list[dict[str, Any]] = state.get("agentic_history") or []

    if action == "finish":
        # 完结此轮和缓存
        _task_run_llm_cache.pop(cache_key, None)
        logger.info(f"[agentic_loop] 正常完成任务。")
        # AI 决定结束，交给总结节点汇报
        return {
            "agentic_done": True,
            "agentic_iterations": iterations,
            "agentic_history": existing_history + new_history,
            "execution_artifacts": new_artifacts,
        }

    elif action == "call":
        calls: list[dict] = decision.get("calls", [])
        if not calls:
            logger.warning("[agentic_loop] action=call 但 calls 为空，视为 finish")
            return {
                "agentic_done": True,
                "agentic_iterations": iterations,
                "agentic_history": existing_history + new_history,
                "execution_artifacts": new_artifacts,
            }

        # 分流：只读立即执行，写入排队审批
        read_calls = [c for c in calls if c.get("safety_level", "readonly_safe") in READ_ONLY_SAFETY]
        write_calls = [c for c in calls if c.get("safety_level", "readonly_safe") in WRITE_SAFETY]

        # 执行所有只读调用（token 由 _ensure_project_token 自动管理）
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
                except Exception as e:
                    logger.error(f"[agentic_loop] Failed to parse ExecutionArtifact: {e}", exc_info=True)

        # 处理写入调用——批量审批（带自动放行缓存）
        approved_write_results: list[str] = []

        # 准备自动放行缓存
        approved_cache = state.get("approved_writes_cache") or []
        new_approved_cache = list(approved_cache)

        if write_calls:
            items_to_approve = []

            for wc in write_calls:
                rid = wc.get("route_id", "")
                params = wc.get("parameters", {})
                m, p = _parse_route(rid)

                # 生成指纹：route + params
                params_str = json.dumps(params, sort_keys=True)
                fingerprint = f"{rid}|{params_str}"

                # 1. 检查缓存是否已批准
                if fingerprint in approved_cache:
                    logger.info(f"[agentic_loop] 自动放行已批准过的请求: {fingerprint}")
                    write_result = await _execute_read_call(wc, state)
                    approved_write_results.append(
                        f'write_id=cached route={rid} status={write_result["status_code"]}\n(自动放行) 结果: {write_result["result"]}'
                    )
                    if write_result.get("artifact"):
                        from app.schemas.task import ExecutionArtifact
                        try:
                            artifact = ExecutionArtifact(**write_result["artifact"])
                            new_artifacts.append(artifact)
                        except Exception as e:
                            logger.error(f"[agentic_loop] Failed to parse ExecutionArtifact for cached write: {e}", exc_info=True)
                    continue

                import hashlib
                # 使用确定性的哈希值作为 write_id，防止 langgraph 恢复重新执行节点时 ID 变化
                deterministic_id = hashlib.md5(fingerprint.encode("utf-8")).hexdigest()
                
                # 2. 加入待审批列表
                items_to_approve.append({
                    "write_id": deterministic_id,
                    "fingerprint": fingerprint,
                    "route_id": rid,
                    "method": m,
                    "path": p,
                    "parameters": params,
                    "reasoning": wc.get("reasoning", ""),
                    "safety_level": wc.get("safety_level", "soft_write"),
                    "_wc": wc  # 暂存原始调用对象
                })

            if items_to_approve:
                import hashlib
                # batch_id 也必须是确定性的，以包含的所有 write_id 为基础计算签名的哈希
                all_ids = sorted([item["write_id"] for item in items_to_approve])
                batch_id = hashlib.md5("".join(all_ids).encode("utf-8")).hexdigest()
                
                serializable_items = [{k: v for k, v in it.items() if k not in ("_wc", "fingerprint")} for it in items_to_approve]

                # 只有在这是该批次“第一次”被评估时，才向前端发射审批请求事件
                # (langgraph 恢复重跑该节点时，无需重复发送事件)
                _emit("write_approval_required", batch_id=batch_id, items=serializable_items)

                # interrupt：暂停图执行，等待一次性批量审批
                approval_response = interrupt({
                    "type": "batch_write_approval",
                    "batch_id": batch_id,
                    "items": serializable_items
                })

                approved_ids = set(approval_response.get("approved_ids", []))

                # 逐个执行被批准的项
                for item in items_to_approve:
                    wid = item["write_id"]
                    rid = item["route_id"]
                    wc = item["_wc"]

                    if wid in approved_ids:
                        # 加入缓存，防止本轮之后 AI 重试时重复弹出
                        if item["fingerprint"] not in new_approved_cache:
                            new_approved_cache.append(item["fingerprint"])

                        write_result = await _execute_read_call(wc, state)
                        approved_write_results.append(
                            f'write_id={wid} route={rid} status={write_result["status_code"]}\n结果: {write_result["result"]}'
                        )
                        if write_result.get("artifact"):
                            from app.schemas.task import ExecutionArtifact
                            try:
                                artifact = ExecutionArtifact(**write_result["artifact"])
                                new_artifacts.append(artifact)
                            except Exception as e:
                                logger.error(f"[agentic_loop] Failed to parse ExecutionArtifact for write: {e}", exc_info=True)
                    else:
                        approved_write_results.append(f'write_id={wid} route={rid} → 用户已拒绝')

        # 将本轮工具结果追加为 observation 消息
        all_results = tool_results_summary + approved_write_results
        if all_results:
            observation_content = "【工具执行结果】\n" + "\n\n".join(all_results)
            new_history.append({
                "role": "user",
                "content": observation_content,
            })

        # 本轮结束，清理缓存
        _task_run_llm_cache.pop(cache_key, None)

        return {
            "agentic_done": False,
            "agentic_iterations": iterations,
            "agentic_history": existing_history + new_history,
            "execution_artifacts": new_artifacts,
            "approved_writes_cache": new_approved_cache[-20:]
        }

    else:
        # 未知 action，强制结束
        logger.warning(f"[agentic_loop] 未知 action: {action}，强制结束")
        return {
            "agentic_done": True,
            "agentic_iterations": iterations,
            "agentic_history": existing_history + new_history,
            "summary_text": f"AI 输出了未知指令 action={action}，任务中止。",
        }
