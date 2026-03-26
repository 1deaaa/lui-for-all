"""
运行时链路 Prompt 资源
"""

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
CLASSIFY_PROMPT = """
你是一个请求分类助手。请判断用户的输入属于哪一类：

用户输入: {user_message}

请从以下三类中选择一个，输出 JSON 格式：
- "direct": 问候、闲聊、询问系统功能、询问"你能做什么"等，不需要调用任何接口
- "simple": 意图清晰的单步只读查询（如：查看列表、获取详情、查统计），通常对应 GET 请求
- "complex": 需要多步操作、涉及写入/修改/删除、意图不明确或需要额外参数确认

输出格式:
{{
    "complexity": "direct" | "simple" | "complex",
    "reasoning": "一句话说明原因"
}}
"""  # noqa: E501


SIMPLE_EXECUTE_PROMPT = """
你是一个接口调用助手。请根据用户的需求，从接口列表中选择最合适的接口，直接构造调用参数。

用户需求: {user_message}

可用接口列表:
{capability_list}

请直接选择最合适的接口并构造参数，输出 JSON：
{{
    "route_id": "选中的 route_id（如 GET:/api/users）",
    "capability_id": "选中的 capability_id",
    "parameters": {{"参数名": "参数值"}},
    "reasoning": "一句话说明选择原因"
}}

如果列表中没有合适的接口，请返回:
{{
    "route_id": null,
    "capability_id": null,
    "parameters": {{}},
    "reasoning": "没有找到合适的接口，原因：..."
}}
"""
