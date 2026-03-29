"""
LangGraph 节点实现
各处理节点的具体逻辑
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

from langgraph.types import interrupt

from app.config import settings
from app.graph.llm_client import llm_client
from app.graph.state import (
    CapabilitySelectionResult,
    GraphState,
    IntentParseResult,
    SummaryResult,
    TaskPlanResult,
)
from app.llm.prompts import (
    AGENT_ENTRY_PROMPT,
    CAPABILITY_SELECT_PROMPT,
    DIRECT_ANSWER_PROMPT,
    INTENT_PARSE_PROMPT,
    SIMPLE_EXECUTE_PROMPT,
    SUMMARY_PROMPT,
    TASK_PLAN_PROMPT,
)
from app.policy.service import PolicyService
from app.runtime import get_runtime_emitter
from app.schemas.capability import Capability, ModalityType
from app.schemas.policy import PolicyAction, PolicyVerdict
from app.schemas.task import ApprovalStatus, ExecutionArtifact, TaskPlan, TaskStep
from app.services.execution_service import ExecutionService


def emit_runtime_event(event: str, **payload: Any):
    """向 LangGraph 自定义流通道发送运行时事件"""
    get_runtime_emitter().emit(event, **payload)


async def parse_intent_node(state: GraphState) -> dict[str, Any]:
    """解析用户意图"""
    try:
        emit_runtime_event(
            "task_progress",
            node_name="parse_intent",
            progress=0.08,
            message="正在解析用户意图",
        )
        # on_token: 正文 token -> 发射到云端（丢弃：JSON 内容不需要展示）
        # on_reasoning: 推理内容 -> thought_emitted
        async def on_reasoning(token: str):
            emit_runtime_event("thought_emitted", token=token)

        result = await llm_client.stream_parse_json_response(
            [
                {
                    "role": "user",
                    "content": INTENT_PARSE_PROMPT.format(
                        user_message=state["user_message"],
                        domains="auth, customer, finance, inventory, content, analytics, operations, system",
                    ),
                }
            ],
            IntentParseResult,
            on_reasoning=on_reasoning,
            temperature=0.3,
        )
        
        logger.info(f"[parse_intent] Parsed intent: {result.normalized_intent}")

        return {
            "normalized_intent": result.normalized_intent,
            "current_node": "parse_intent",
        }
    except Exception as e:
        import traceback
        logger.error(f"[parse_intent] Exception: {e}", exc_info=True)
        return {
            "error": f"意图解析失败: {str(e)}",
            "current_node": "parse_intent",
        }


async def select_capabilities_node(state: GraphState) -> dict[str, Any]:
    """选择匹配的能力"""
    # 从状态中获取预加载的能力列表
    available_capabilities = state.get("available_capabilities", [])
    emit_runtime_event(
        "task_progress",
        node_name="select_capabilities",
        progress=0.22,
        message="正在匹配能力图谱",
    )
    
    if not available_capabilities:
        return {
            "error": "没有可用的能力来制定计划",
            "current_node": "select_capabilities",
        }

    try:
        # 构建能力摘要用于 LLM 选择
        cap_summaries = [
            {
                "capability_id": c.get("capability_id"),
                "name": c.get("name"),
                "description": c.get("description", "")[:200],  # 截断描述
                "domain": c.get("domain"),
                "safety_level": c.get("safety_level"),
            }
            for c in available_capabilities[:50]  # 限制数量避免 token 过多
        ]
        
        logger.info(f"[select_capabilities] Calling LLM with {len(cap_summaries)} capabilities")
        logger.info(f"[select_capabilities] Intent: {state.get('normalized_intent') or state['user_message']}")

        # on_reasoning: 推理内容 -> thought_emitted
        async def on_reasoning_cap(token: str):
            emit_runtime_event("thought_emitted", token=token)

        result = await llm_client.stream_parse_json_response(
            [
                {
                    "role": "user",
                    "content": CAPABILITY_SELECT_PROMPT.format(
                        intent=state.get("normalized_intent") or state["user_message"],
                        capabilities=json.dumps(cap_summaries, ensure_ascii=False, indent=2),
                    ),
                }
            ],
            CapabilitySelectionResult,
            on_reasoning=on_reasoning_cap,
            temperature=0.3,
        )
        
        logger.info(f"[select_capabilities] LLM returned {len(result.capabilities)} capabilities")
        logger.debug(f"[select_capabilities] Reasoning: {result.reasoning}")
        for cap_data in result.capabilities:
            logger.debug(f"  - capability_id: {getattr(cap_data, 'capability_id', 'N/A')}")

        # 转换为 Capability 对象，并从原始数据补充完整信息
        capabilities = []
        for cap_data in result.capabilities:
            # cap_data 是 Capability Pydantic 对象
            cap_id = cap_data.capability_id if hasattr(cap_data, 'capability_id') else str(uuid.uuid4())
            
            # 从原始能力列表查找完整数据
            original_cap = next(
                (c for c in available_capabilities if c.get("capability_id") == cap_id),
                None
            )
            
            if original_cap:
                # 鲁棒性处理：确保 safety_level 是合法的 Enum 值
                raw_safety = original_cap.get("safety_level", "readonly_safe")
                valid_safety_levels = ["readonly_safe", "readonly_sensitive", "soft_write", "hard_write", "critical"]
                if raw_safety not in valid_safety_levels:
                    # 如果原值非法（如 'low'），则根据 data_sensitivity 降级尝试
                    if original_cap.get("data_sensitivity") == "high":
                        raw_safety = "readonly_sensitive"
                    else:
                        raw_safety = "readonly_safe"

                cap = Capability(
                    capability_id=original_cap.get("capability_id", str(uuid.uuid4())),
                    name=original_cap.get("name", ""),
                    description=original_cap.get("description", ""),
                    domain=original_cap.get("domain", "unknown"),
                    safety_level=raw_safety,
                    backed_by_routes=original_cap.get("backed_by_routes", []),
                    user_intent_examples=original_cap.get("user_intent_examples", []),
                    required_permission_level=original_cap.get("permission_level", "authenticated"),
                    data_sensitivity=original_cap.get("data_sensitivity", "low"),
                    best_modalities=[ModalityType(m) for m in original_cap.get("best_modalities", ["text_block"])],
                    requires_confirmation=original_cap.get("requires_confirmation", False),
                    evidence_refs=[],
                    parameter_hints=original_cap.get("parameter_hints", {}),
                )
                capabilities.append(cap)

        return {
            "selected_capabilities": capabilities,
            "current_node": "select_capabilities",
        }
    except Exception as e:
        import traceback
        logger.error(f"[select_capabilities] Exception: {e}", exc_info=True)
        return {
            "error": f"能力选择失败: {str(e) or type(e).__name__}",
            "current_node": "select_capabilities",
        }


async def draft_plan_node(state: GraphState) -> dict[str, Any]:
    """制定任务计划"""
    capabilities = state.get("selected_capabilities", [])
    emit_runtime_event(
        "task_progress",
        node_name="draft_plan",
        progress=0.38,
        message="正在生成执行计划",
    )
    
    logger.info(f"[draft_plan] Selected capabilities: {len(capabilities)}")

    if not capabilities:
        return {
            "error": "没有可用的能力来制定计划",
            "current_node": "draft_plan",
        }

    try:
        caps_json = json.dumps(
            [c.model_dump() for c in capabilities],
            ensure_ascii=False,
            indent=2,
        )

        # on_reasoning: 推理内容 -> thought_emitted
        async def on_reasoning_plan(token: str):
            emit_runtime_event("thought_emitted", token=token)

        result = await llm_client.stream_parse_json_response(
            [
                {
                    "role": "user",
                    "content": TASK_PLAN_PROMPT.format(
                        intent=state.get("normalized_intent") or state["user_message"],
                        capabilities=caps_json,
                        username=state.get("project_username", "None"),
                        password=state.get("project_password", "None"),
                    ),
                }
            ],
            TaskPlanResult,
            on_reasoning=on_reasoning_plan,
            temperature=0.3,
        )

        return {
            "task_plan": result.plan,
            "current_node": "draft_plan",
        }
    except Exception as e:
        import traceback
        return {
            "error": f"任务计划失败: {str(e)}\n{traceback.format_exc()}",
            "current_node": "draft_plan",
        }


# ==================== 策略检查节点 ====================

async def policy_check_node(state: GraphState) -> dict[str, Any]:
    """检查安全策略"""
    plan = state.get("task_plan")
    emit_runtime_event(
        "task_progress",
        node_name="policy_check",
        progress=0.55,
        message="正在进行安全策略判定",
    )
    if not plan:
        return {
            "error": "没有任务计划可供检查",
            "current_node": "policy_check",
        }

    verdicts = PolicyService().evaluate_plan(plan)

    return {
        "policy_verdicts": verdicts,
        "current_node": "policy_check",
    }


# ==================== 审批门节点 ====================

async def approval_gate_node(state: GraphState) -> dict[str, Any]:
    """审批门 - 需要人工确认时中断"""
    verdicts = state.get("policy_verdicts", [])

    # 检查是否有需要确认的判定
    needs_approval = any(
        v.action == PolicyAction.CONFIRM for v in verdicts
    )

    if not needs_approval:
        return {
            "approval_status": ApprovalStatus.APPROVED,
            "current_node": "approval_gate",
        }

    # 构建审批请求
    approval_id = str(uuid.uuid4())

    confirm_actions = [
        {
            "step_id": v.route_id,
            "action": v.approval_message,
            "risk_level": v.safety_level,
        }
        for v in verdicts
        if v.action == PolicyAction.CONFIRM
    ]

    emit_runtime_event(
        "approval_required",
        approval_id=approval_id,
        title="操作需要确认",
        description="以下操作需要您的确认才能继续执行",
        actions=confirm_actions,
    )

    # 使用 interrupt 暂停执行
    approval_result = interrupt(
        {
            "type": "approval_required",
            "approval_id": approval_id,
            "title": "操作需要确认",
            "description": "以下操作需要您的确认才能继续执行",
            "actions": [
                *confirm_actions
            ],
        }
    )

    # 恢复执行后，获取审批结果
    if approval_result.get("approved"):
        return {
            "approval_status": ApprovalStatus.APPROVED,
            "current_node": "approval_gate",
        }
    else:
        return {
            "approval_status": ApprovalStatus.REJECTED,
            "error": "用户拒绝了操作",
            "current_node": "approval_gate",
        }


# ==================== 执行请求节点 ====================

async def execute_requests_node(state: GraphState) -> dict[str, Any]:
    """执行 HTTP 请求"""
    plan = state.get("task_plan")
    verdicts = state.get("policy_verdicts", [])
    emit_runtime_event(
        "task_progress",
        node_name="execute_requests",
        progress=0.68,
        message="开始执行目标接口调用",
    )
    
    logger.info(f"[execute_requests] Plan steps: {len(plan.steps) if plan else 0}")
    if plan and plan.steps:
        logger.debug(f"[execute_requests] First step: {plan.steps[0].route_id if plan.steps else 'N/A'}")

    if not plan:
        return {
            "error": "没有任务计划可供执行",
            "current_node": "execute_requests",
        }

    base_url = state.get("project_base_url", "http://localhost:8000").rstrip("/")

    logger.info(f"[execute_requests] Starting execution with {len(plan.steps)} steps against target {base_url}")
    artifacts = await ExecutionService(
        base_url=base_url,
        trace_id=state.get("trace_id"),
        emitter=get_runtime_emitter(),
    ).execute_plan(plan, verdicts)

    return {
        "execution_artifacts": artifacts,
        "current_node": "execute_requests",
    }


async def summarize_node(state: GraphState) -> dict[str, Any]:
    """生成执行总结"""
    artifacts = state.get("execution_artifacts", [])
    emit_runtime_event(
        "task_progress",
        node_name="summarize",
        progress=0.9,
        message="正在整理执行结果并生成总结",
    )

    if not artifacts:
        return {
            "summary_text": "没有执行任何操作",
            "current_node": "summarize",
        }

    try:
        results_json = json.dumps(
            [a.model_dump() for a in artifacts],
            ensure_ascii=False,
            indent=2,
        )

        full_summary = ""
        # 使用流式接口生成总结
        async for chunk_type, token in llm_client.stream_chat_completion(
            [
                {
                    "role": "user",
                    "content": SUMMARY_PROMPT.format(
                        user_message=state["user_message"],
                        results=results_json,
                    ),
                }
            ],
            temperature=0.5,
        ):
            if chunk_type == "reasoning":
                # 总结节点的推理过程通过 thought_emitted 展示
                emit_runtime_event("thought_emitted", token=token)
            else:
                full_summary += token
                # 实时发射 Token
                emit_runtime_event("token_emitted", token=token)

        return {
            "summary_text": full_summary,
            "current_node": "summarize",
        }
    except Exception as e:
        logger.error(f"[summarize] 失败: {e}", exc_info=True)
        return {
            "summary_text": f"执行完成，但总结生成失败: {str(e)}",
            "current_node": "summarize",
        }


# ==================== UI Block 生成节点 ====================

async def emit_blocks_node(state: GraphState) -> dict[str, Any]:
    """生成 UI Block"""
    ui_blocks: list[dict[str, Any]] = []
    emit_runtime_event(
        "task_progress",
        node_name="emit_blocks",
        progress=0.98,
        message="正在组织前端展示结构",
    )

    # 移除总结被硬编码为 ui_block 的逻辑，因为长文本已经被流式传入到普通聊天气泡中，避免重复


    # 添加执行时间线
    artifacts = state.get("execution_artifacts", [])
    if artifacts:
        events = [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "title": f"执行 {a.method} {a.url}",
                "description": f"状态码: {a.status_code}",
                "status": "completed" if a.status_code and a.status_code < 400 else "failed",
            }
            for a in artifacts
        ]
        ui_blocks.append({
            "block_type": "timeline_card",
            "title": "执行记录",
            "events": events,
        })

    return {
        "ui_blocks": ui_blocks,
        "current_node": "emit_blocks",
    }


# ==================== Agent 入口决策与响应节点（Fast Path 融合口）====================

async def agent_entry_node(state: GraphState) -> dict[str, Any]:
    """
    第一层智能体入口：
    1. 判断用户请求是否可直接解答（纯聊天、能力查询）。若是，生成答复并退出。
    2. 若需工具，下发简单(simple)或复杂(complex)的 API 处理任务往下走。
    """
    try:
        full_content = ""
        strategy = None
        reply_content = ""
        import re
        strategy_pattern = re.compile(r"<strategy>(.*?)</strategy>")

        # 调用 LLM 进行复合决策并流式吐词
        async for chunk_type, token in llm_client.stream_simple_completion(
            prompt=state["user_message"],
            system_prompt=AGENT_ENTRY_PROMPT.format(capability_list=capability_list),
            temperature=0.4,
        ):
            if chunk_type == "reasoning":
                emit_runtime_event("thought_emitted", token=token)
            else:
                full_content += token
                if strategy is None:
                    # 侦测策略标签是否已经完结
                    if "</strategy>" in full_content:
                        match = strategy_pattern.search(full_content)
                        if match:
                            strategy_val = match.group(1).strip().lower()
                            strategy = strategy_val if strategy_val in ("direct", "simple", "complex") else "complex"
                            
                            # 提取标签之后的部分，这部分属于正式的纯聊天回答内容
                            rest_text = full_content[match.end():]
                            if strategy == "direct" and rest_text:
                                reply_content += rest_text
                                emit_runtime_event("token_emitted", token=rest_text)
                else:
                    if strategy == "direct":
                        reply_content += token
                        emit_runtime_event("token_emitted", token=token)
        
        # 兜底：如果模型没有输出任何合法的策略标签
        if strategy is None:
            strategy = "complex"

        # 特别测试口令检测
        if "STREAM_TEST" in state.get("user_message", ""):
            strategy = "direct"

        logger.info(f"[agent_entry] 决策策略: {strategy}")

        state_update: dict[str, Any] = {
            "request_complexity": strategy,
            "current_node": "agent_entry"
        }

        if strategy == "direct":
            state_update["summary_text"] = reply_content.strip()

        return state_update
    except Exception as e:
        logger.warning(f"[agent_entry] 思考失败，降级为执行全流程: {e}")
        return {"request_complexity": "complex", "current_node": "agent_entry"}


# ==================== 直接回答节点 ====================



async def simple_execute_node(state: GraphState) -> dict[str, Any]:
    """
    简单流核心节点：将接口摘要注入上下文，AI 直接选接口并构造调用参数。
    跳过：select_capabilities → draft_plan → policy_check → approval_gate
    """
    from pydantic import BaseModel as _BaseModel

    class SimpleExecuteResult(_BaseModel):
        route_id: str | None = None
        capability_id: str | None = None
        parameters: dict[str, Any] = {}
        reasoning: str | None = None

    emit_runtime_event(
        "task_progress",
        node_name="simple_execute",
        progress=0.2,
        message="快速匹配接口中",
    )

    available_capabilities = state.get("available_capabilities", [])
    if not available_capabilities:
        return {
            "error": "没有可用的接口能力，请先完成项目建图",
            "current_node": "simple_execute",
        }

    # 只注入 capability_id、route_id 和 summary（极简上下文）
    cap_list_lines = []
    for cap in available_capabilities[:80]:
        cap_id = cap.get("capability_id", "")
        route_id = ""
        routes = cap.get("backed_by_routes", [])
        if routes and isinstance(routes, list) and len(routes) > 0:
            first_route = routes[0]
            if isinstance(first_route, dict):
                route_id = first_route.get("route_id", "")
        summary = cap.get("summary") or cap.get("name") or cap.get("description", "")[:30]
        cap_list_lines.append(f"- {cap_id} ({route_id}): {summary}")

    capability_list = "\n".join(cap_list_lines)

    try:
        result = await llm_client.parse_json_response(
            [
                {
                    "role": "user",
                    "content": SIMPLE_EXECUTE_PROMPT.format(
                        user_message=state["user_message"],
                        capability_list=capability_list,
                    ),
                }
            ],
            SimpleExecuteResult,
            temperature=0.2,
        )

        if not result.route_id:
            # 没找到合适接口，退化为文字回答
            fallback_msg = result.reasoning or "对不起，我在现有接口中没有找到能完成您需求的能力。"
            return {
                "summary_text": fallback_msg,
                "current_node": "simple_execute",
            }

        emit_runtime_event(
            "task_progress",
            node_name="simple_execute",
            progress=0.5,
            message=f"正在调用接口 {result.route_id}",
        )

        # 构造单步任务计划，复用 ExecutionService
        from app.schemas.task import TaskPlan, TaskStep
        plan = TaskPlan(
            plan_id=str(uuid.uuid4()),
            description=f"简单流: {result.reasoning}",
            steps=[
                TaskStep(
                    step_id=str(uuid.uuid4()),
                    order=1,
                    capability_id=result.capability_id or "",
                    route_id=result.route_id,
                    action=state["user_message"],
                    parameters=result.parameters,
                    safety_level="readonly_safe",
                    requires_confirmation=False,
                )
            ],
        )

        base_url = state.get("project_base_url", "http://localhost:8000").rstrip("/")
        artifacts = await ExecutionService(
            base_url=base_url,
            trace_id=state.get("trace_id"),
            emitter=get_runtime_emitter(),
        ).execute_plan(plan, [])

        emit_runtime_event(
            "task_progress",
            node_name="simple_execute",
            progress=0.85,
            message="正在生成回答",
        )

        # 生成总结
        results_json = json.dumps(
            [a.model_dump() for a in artifacts],
            ensure_ascii=False,
            indent=2,
        )
        summary_text = "执行完成"
        try:
            summary_result = await llm_client.parse_json_response(
                [{"role": "user", "content": SUMMARY_PROMPT.format(
                    user_message=state["user_message"],
                    results=results_json,
                )}],
                SummaryResult,
                temperature=0.5,
            )
            summary_text = summary_result.summary_text
        except Exception:
            pass

        return {
            "execution_artifacts": artifacts,
            "summary_text": summary_text,
            "current_node": "simple_execute",
        }

    except Exception as e:
        logger.error(f"[simple_execute] 失败: {e}", exc_info=True)
        return {
            "error": f"简单流执行失败: {str(e)}",
            "current_node": "simple_execute",
        }
