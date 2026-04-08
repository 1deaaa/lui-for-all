import re
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[2]
prompt_file = backend_dir / "app" / "llm" / "prompts" / "runtime.py"

with open(prompt_file, 'r', encoding='utf-8') as f:
    content = f.read()

new_prompt = 'AGENT_ENTRY_PROMPT = """\n你是一个系统的处理中枢（AI Agent）。你需要直接处理用户的请求。\n\n【当前接入的项目简介】\n{project_description}\n\n【当前系统可用的能力/路由（概要信息）】\n{capability_list}\n\n【用户输入】:\n{user_message}\n\n【你的任务】:\n请你判断应该采取哪种处理策略，并在输出最开头使用 <strategy> 标签标明。可选策略有：\n\n- direct: 纯闲聊、打招呼、询问系统功能介绍、不涉及任何接口调用的问题。直接生成回答即可。\n- agentic: 用户要求查询数据、操作接口、执行任何任务（无论只读还是写入）。统一进入多轮工具调用。\n\n输出格式要求：\n1. 必须首先输出 <strategy>策略名称</strategy>。\n2. 如果策略是 direct，请在标签之后紧接着用自然、轻快的语言直接生成回答（Markdown 格式）。\n3. 如果策略是 agentic，标签之后无需输出任何内容。\n\n示例：\n<strategy>direct</strategy>你好！我是你的智能接口助手，可以帮你查询数据或操作系统接口。\n"""'

pattern = r'AGENT_ENTRY_PROMPT = """.*?"""'
new_content = re.sub(pattern, new_prompt, content, count=1, flags=re.DOTALL)

with open(prompt_file, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Done")
