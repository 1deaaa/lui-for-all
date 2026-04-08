import sys
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))
load_dotenv(backend_dir / ".env")

from app.llm.agent_matchbox import initialize_matchbox, matchbox

# 1. 初始化
initialize_matchbox(ensure_defaults=True)
mgr = matchbox()

# 2. 找到 qwen3.5-flash 模型，如果需要的话可以强制绑定给当前用到的用户。
print("配置 -1 用户的 main slot 为 阿里云百炼 的 qwen3.5-flash")
plats = mgr.get_platforms("-1")
t_plat_id = None
for p in plats:
    if "阿里云百炼" in p["name"]:
        t_plat_id = p["platform_id"]
        break

t_model_id = None
if t_plat_id:
    models = mgr.get_platform_models("-1")
    for m in models:
        if m["platform_id"] == t_plat_id and "flash" in m["model_name"]:
            t_model_id = m["model_id"]
            break

if t_plat_id and t_model_id:
    mgr.save_user_selection("-1", t_plat_id, t_model_id, "main")
    print(f"✅ Slot updated to platform {t_plat_id}, model {t_model_id}")
else:
    print("Warning: could not forcefully bind qwen3.5-flash slot...")

# 3. 运行测试
from app.llm.client import llm_client

async def main():
    print("\n--- 全链路 LLM 流式与 Reasoning 字段解析测试 ---")
    print("Question: 帮我仔细一步步计算 1 + 2 + ... + 10 是多少，请一定展现你的深度思考过程。")
    
    reasoning_acc = ""
    content_acc = ""
    
    # 我们知道阿里云大模型的深度思考(如qwen-max-thinking或者某些配置)会发出 reasoning 字段。qwen-flash 可能不会发出 reasoning 但能发出 token。
    async for chunk_type, token in llm_client.stream_simple_completion(
        prompt="帮我仔细一步步计算 1 + 2 + ... + 10 是多少，请一定展现你的深度思考（或者用分步方式）。",
        system_prompt="你是一个聪明的数学助手。你需要展示极强的深度思考。"
    ):
        if chunk_type == "reasoning":
            reasoning_acc += token
            print(f"[\033[90mTHOUGHT\033[0m] {token}", end="", flush=True)
        else:
            content_acc += token
            print(f"[\033[92mCONTENT\033[0m] {token}", end="", flush=True)

    print("\n\n--- 测试完成 ---")
    print(f"Total Reasoning length: {len(reasoning_acc)}")
    print(f"Total Content length: {len(content_acc)}")

if __name__ == "__main__":
    asyncio.run(main())
