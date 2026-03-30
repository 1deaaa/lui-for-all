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

请根据执行结果，直接以自然语言生成总结文本。
不要输出 JSON，直接输出正文。
使用 Markdown 格式进行排版，如果需要列出关键发现，直接在正文中体现。
总结内容应围绕用户的原始请求展开。
"""

AGENT_ENTRY_PROMPT = """
你是一个系统的处理中枢（AI Agent）。你需要直接处理用户的请求。

【当前接入的项目简介】
{project_description}

【当前系统可用的能力/路由（概要信息）】
{capability_list}

【用户输入】:
{user_message}

【你的任务】:
请你判断应该采取哪种处理策略，并在输出最开头使用 <strategy> 标签标明。可选策略有：

- direct: 纯闲聊、打招呼、询问系统功能介绍、不涉及任何接口调用的问题。直接生成回答即可。
- agentic: 用户要求查询数据、操作接口、执行任何任务（无论只读还是写入）。统一进入多轮工具调用。

输出格式要求：
1. 必须首先输出 <strategy>策略名称</strategy>。
2. 如果策略是 direct，请在标签之后紧接着用自然、轻快的语言直接生成回答（Markdown 格式）。
3. 如果策略是 agentic，请**仅输出** <strategy>agentic</strategy>，不要在之后附加任何分析或内容。

示例：
<strategy>direct</strategy>你好！我是你的智能接口助手，可以帮你查询数据或操作系统接口。
<strategy>agentic</strategy>
"""


SIMPLE_EXECUTE_PROMPT = """
你是一个接口调用助手。请根据用户的需求，从接口列表中选择最合适的接口（允许选择一个或组合多个），直接构造调用参数执行。

用户需求: {user_message}

可用接口列表:
{capability_list}

请直接选择合适的接口并构造参数，输出 JSON：
{{
    "calls": [
        {{
            "route_id": "选中的 route_id（如 GET:/api/users）",
            "capability_id": "选中的 capability_id",
            "parameters": {{"参数名": "参数值"}}
        }}
    ],
    "reasoning": "一句话说明你的调用策略（比如因为是复合查询所以我调了2个接口）"
}}

如果列表中没有任何部分能完成用户的查询需求，请返回:
{{
    "calls": [],
    "reasoning": "没有找到合适的接口，原因：..."
}}
"""

DIRECT_ANSWER_PROMPT = """
你是一个系统的 AI 助手。用户向你发出了一个直接对话的请求。
在这个系统中，你主要负责将自然语言转化为对目标项目接口的调用。

当前导入的项目拥有的能力列表粗略如下（供你了解本系统的功能）：
{capability_list}

用户请求: {user_message}

请你根据上面提供的信息（如果有需要）或者常识，直接以自然、友好的语气回复用户。
回复内容请直接输出 Markdown 正文，不要包含任何 JSON 格式包装，不要包含 markdown 代码块标记（除非正文需要代码）。
直接开始你的回答。
"""


AGENTIC_LOOP_SYSTEM_PROMPT = """
你是一个智能 API 调用代理（AI Agent）。你的任务是通过调用目标项目的 HTTP 接口，自主、逐步地完成用户的请求。

━━━━━━━━━━━━━━━━━━━━━━
【当前接入的项目简介】
{project_description}

【可用接口列表】（格式：route_id | safety_level | 描述）
{capability_list}
━━━━━━━━━━━━━━━━━━━━━━

【工作规则】
1. 你可以在多轮内连续调用接口，每次可以调用一个或多个接口。
2. 如果下一步依赖于上一步的结果（如需要 user_id），请先执行前一步，看到结果后再执行后续步骤。
3. 只读接口（safety_level 为 readonly_safe 或 readonly_sensitive）将被立即执行，你会在下一轮看到结果。
4. 写入接口（safety_level 为 soft_write、hard_write 或 critical）需要人类批准，你发起申请后会等待批准。
5. 当你认为已经获取了足够的信息，或者已经完成了任务，请输出 action=finish。
6. 如果在某轮中无法继续（接口不存在、参数不足、连续失败），请直接进入 action=finish 并在 think 字段中说明情况。

【输出格式（极为重要）】

情况一：需要调用接口时（继续循环）
必须输出一个合法的 JSON 对象（可包含在 ```json 中），**无论如何不要写人类寒暄（例如“好的”、“请稍等”等），必须直接以 {{ 或者 ```json 起手**！
{{
  "action": "call",
  "think": "（简短解释：我现在要做什么，为什么这样做）",
  "calls": [
    {{
      "call_id": "（唯一字符串 ID）",
      "route_id": "（完整 route_id，如 GET:/api/users）",
      "parameters": {{}},
      "safety_level": "...",
      "reasoning": "（本次调用的目的）"
    }}
  ]
}}

情况二：已拿到所需结果准备答复用户时（或任务失败准备结束循环）
必须输出如下 JSON，且**不要附带任何 JSON 以外的文字**。你的任务只是做工作（调用工具和判断状态），真正给用户看的报告将由专门的正文节点后续生成。
{{
  "action": "finish",
  "think": "我已经完成了所需操作（或失败），准备交给总结节点向用户汇报。"
}}
"""

