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
from app.schemas.capability import Capability, ModalityType
from app.schemas.policy import PolicyAction, PolicyVerdict
from app.schemas.task import ApprovalStatus, ExecutionArtifact, TaskPlan, TaskStep


# ==================== 意图解析节点 ====================

INTENT_PARSE_PROMPT = """
你是一个意图解析助手。请分析用户的自然语言输入，提取出结构化的意图信息。

用户输入: {user_message}

已知的能力领域: {domains}

请输出 JSON 格式:
{{
    "normalized_intent": "规范化后的意图描述",
    "domain": "识别的业务领域 (如 auth, customer, finance 等，如果不确定填 null)",
    "keywords": ["关键词1", "关键词2"],
    "confidence": 0.0-1.0 之间的置信度
}}
"""


async def parse_intent_node(state: GraphState) -> dict[str, Any]:
    """解析用户意图"""
    try:
        # 调用 LLM 解析意图
        result = await llm_client.parse_json_response(
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


# ==================== 能力选择节点 ====================

CAPABILITY_SELECT_PROMPT = """
你是一个能力匹配助手。根据用户的意图，从已知的能力列表中选择最合适的能力。

用户意图: {intent}

可用能力列表:
{capabilities}

请选择最相关的 1-3 个能力，输出 JSON 格式:
{{
    "capabilities": [
        {{
            "capability_id": "能力ID",
            "name": "能力名称",
            "description": "能力描述",
            "domain": "领域",
            "safety_level": "安全等级",
            "backed_by_routes": [{{"route_id": "xxx", "role": "primary"}}],
            "user_intent_examples": [],
            "required_permission_level": "authenticated",
            "data_sensitivity": "low",
            "best_modalities": ["text_block"],
            "requires_confirmation": false,
            "evidence_refs": [],
            "parameter_hints": {{}}
        }}
    ],
    "reasoning": "选择理由"
}}
"""


async def select_capabilities_node(state: GraphState) -> dict[str, Any]:
    """选择匹配的能力"""
    # 从状态中获取预加载的能力列表
    available_capabilities = state.get("available_capabilities", [])
    
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

        result = await llm_client.parse_json_response(
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
                cap = Capability(
                    capability_id=original_cap.get("capability_id", str(uuid.uuid4())),
                    name=original_cap.get("name", ""),
                    description=original_cap.get("description", ""),
                    domain=original_cap.get("domain", "unknown"),
                    safety_level=original_cap.get("safety_level", "readonly_safe"),
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


# ==================== 任务计划节点 ====================

TASK_PLAN_PROMPT = """
你是一个任务规划助手。根据选中的能力，制定执行计划。

用户意图: {intent}

选中的能力:
{capabilities}

上下文环境提供以下目标系统预设认证信息（如有）供登录API使用:
Username: {username}
Password: {password}
若您选定的操作被认为是 "authenticated" 权限要求，并且您在图中找到了对方系统的登录路由（如 /login、/auth/token），您可以放心地将该登录请求设为 plan 的第一个 step（传递上方给您的账号密码）。引擎会自动捕获响应报文里的 jwt / token 并在后续步骤中代为注入 Authorization 表头。

请制定执行计划，输出 JSON 格式:
{{
    "plan": {{
        "plan_id": "计划ID",
        "description": "计划描述",
        "steps": [
            {{
                "step_id": "步骤ID",
                "order": 1,
                "capability_id": "能力ID",
                "route_id": "路由ID",
                "action": "动作描述",
                "parameters": {{}},
                "safety_level": "安全等级",
                "requires_confirmation": false
            }}
        ],
        "estimated_duration_ms": 5000
    }},
    "reasoning": "计划理由"
}}
"""


async def draft_plan_node(state: GraphState) -> dict[str, Any]:
    """制定任务计划"""
    capabilities = state.get("selected_capabilities", [])
    
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

        result = await llm_client.parse_json_response(
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
    if not plan:
        return {
            "error": "没有任务计划可供检查",
            "current_node": "policy_check",
        }

    verdicts: list[PolicyVerdict] = []

    for step in plan.steps:
        # 根据安全等级判定动作
        safety_level = step.safety_level

        if safety_level in ["readonly_safe"]:
            action = PolicyAction.ALLOW
        elif safety_level in ["readonly_sensitive"]:
            action = PolicyAction.REDACT
        elif safety_level in ["soft_write"]:
            action = PolicyAction.CONFIRM
        else:
            action = PolicyAction.BLOCK

        verdict = PolicyVerdict(
            verdict_id=str(uuid.uuid4()),
            route_id=step.route_id,
            capability_id=step.capability_id,
            action=action,
            safety_level=safety_level,
            permission_level="authenticated",
            reasons=[f"安全等级为 {safety_level}"],
            evidence={},
            redaction_fields=[],
            approval_timeout_seconds=300,
            approval_message=f"此操作需要确认: {step.action}",
            block_reason=None if action != PolicyAction.BLOCK else "操作被安全策略阻断",
        )
        verdicts.append(verdict)

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

    # 使用 interrupt 暂停执行
    approval_result = interrupt(
        {
            "type": "approval_required",
            "approval_id": approval_id,
            "title": "操作需要确认",
            "description": "以下操作需要您的确认才能继续执行",
            "actions": [
                {
                    "step_id": v.route_id,
                    "action": v.approval_message,
                    "risk_level": v.safety_level,
                }
                for v in verdicts
                if v.action == PolicyAction.CONFIRM
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
    import httpx
    
    logger.info(f"[execute_requests] Plan steps: {len(plan.steps) if plan else 0}")
    if plan and plan.steps:
        logger.debug(f"[execute_requests] First step: {plan.steps[0].route_id if plan.steps else 'N/A'}")

    if not plan:
        return {
            "error": "没有任务计划可供执行",
            "current_node": "execute_requests",
        }

    artifacts: list[ExecutionArtifact] = []
    
    # 从状态获取项目基础 URL
    project_id = state.get("project_id")
    base_url = state.get("project_base_url", "http://localhost:8000").rstrip("/")
    username = state.get("project_username")
    password = state.get("project_password")

    logger.info(f"[execute_requests] Starting execution with {len(plan.steps)} steps against target {base_url}")
    
    extracted_token = None
    
    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        for i, step in enumerate(plan.steps):
            logger.info(f"[execute_requests] Step {i+1}: {step.route_id}")
            
            # 检查是否被阻断
            verdict = next(
                (v for v in verdicts if v.route_id == step.route_id),
                None,
            )

            if verdict and verdict.action == PolicyAction.BLOCK:
                logger.warning(f"[execute_requests] Step {i+1} blocked by policy")
                continue

            # 解析 route_id 格式: "METHOD:/path"
            route_parts = step.route_id.split(":", 1)
            if len(route_parts) == 2:
                method = route_parts[0].strip()
                path = route_parts[1].strip()
            else:
                method = "GET"
                path = step.route_id

            # 构建完整 URL
            url = f"{base_url}{path if path.startswith('/') else '/' + path}"
            
            headers = {"Content-Type": "application/json"}
            # 自动挂载接力嗅探到的 Token
            if extracted_token:
                headers["Authorization"] = f"Bearer {extracted_token}"
            elif username and password and len(plan.steps) == 1:
                # 极端弱后备：若只有单步且没 Token 但提供了账密，可尝试用 Basic Auth (兼容考量)
                # 仅在需要 authenticated 且没 token 时才会使用。这交由底层去处理。
                pass
            
            try:
                # 真实 API 调用
                response = await client.request(
                    method=method,
                    url=url,
                    json=step.parameters if method in ["POST", "PUT", "PATCH"] else None,
                    params=step.parameters if method == "GET" else None,
                    headers=headers,
                )
                
                # Token 嗅探自动机 (应对需要登录后的多步操作)
                is_json = response.headers.get("content-type", "").startswith("application/json")
                resp_data = response.json() if is_json else {"text": response.text[:500]}
                
                if is_json and isinstance(resp_data, dict) and not extracted_token:
                    for key in ["access_token", "token", "jwt", "id_token", "session_token"]:
                        if key in resp_data and isinstance(resp_data[key], str):
                            extracted_token = resp_data[key]
                            logger.info(f"[execute_requests] Successfully sniffed and cached token from {path} response.")
                            break
                
                artifact = ExecutionArtifact(
                    artifact_id=str(uuid.uuid4()),
                    step_id=step.step_id,
                    route_id=step.route_id,
                    method=method,
                    url=url,
                    request_headers={"Authorization": "***REDACTED***"} if extracted_token else {},
                    request_body=step.parameters,
                    status_code=response.status_code,
                    response_body=resp_data,
                    duration_ms=int(response.elapsed.total_seconds() * 1000),
                    redacted=verdict.action == PolicyAction.REDACT if verdict else False,
                    error=None,
                )
            except Exception as e:
                artifact = ExecutionArtifact(
                    artifact_id=str(uuid.uuid4()),
                    step_id=step.step_id,
                    route_id=step.route_id,
                    method=method,
                    url=url,
                    request_headers={},
                    request_body=step.parameters,
                    status_code=0,
                    response_body={},
                    duration_ms=0,
                    redacted=False,
                    error=str(e),
                )

            artifacts.append(artifact)

    return {
        "execution_artifacts": artifacts,
        "current_node": "execute_requests",
    }


# ==================== 总结节点 ====================

SUMMARY_PROMPT = """
你是一个结果总结助手。根据执行结果，生成用户友好的总结。

用户原始请求: {user_message}

执行结果:
{results}

请输出 JSON 格式:
{{
    "summary_text": "总结文本，用自然语言描述执行结果",
    "key_findings": ["关键发现1", "关键发现2"]
}}
"""


async def summarize_node(state: GraphState) -> dict[str, Any]:
    """生成执行总结"""
    artifacts = state.get("execution_artifacts", [])

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

        result = await llm_client.parse_json_response(
            [
                {
                    "role": "user",
                    "content": SUMMARY_PROMPT.format(
                        user_message=state["user_message"],
                        results=results_json,
                    ),
                }
            ],
            SummaryResult,
            temperature=0.5,
        )

        return {
            "summary_text": result.summary_text,
            "current_node": "summarize",
        }
    except Exception as e:
        return {
            "summary_text": f"执行完成，但总结生成失败: {str(e)}",
            "current_node": "summarize",
        }


# ==================== UI Block 生成节点 ====================

async def emit_blocks_node(state: GraphState) -> dict[str, Any]:
    """生成 UI Block"""
    ui_blocks: list[dict[str, Any]] = []

    # 添加总结文本块
    if state.get("summary_text"):
        ui_blocks.append({
            "block_type": "text_block",
            "content": state["summary_text"],
            "format": "plain",
        })

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
