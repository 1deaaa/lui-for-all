import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
backend_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(backend_dir))
load_dotenv(backend_dir / ".env")

platform_api_key = os.getenv("LUI_MATCHBOX_PLATFORM_API_KEY")
if not platform_api_key:
    raise RuntimeError("请先设置环境变量 LUI_MATCHBOX_PLATFORM_API_KEY")

from app.llm.agent_matchbox import initialize_matchbox, matchbox

print("Initializing matchbox...")
initialize_matchbox(ensure_defaults=True)

mgr = matchbox()

print("Fetching platforms...")
platforms = mgr.get_platforms("-1")
target_plat_id = None
for p in platforms:
    print("Found platform:", p["name"], p["platform_id"])
    if "阿里云百炼" in p["name"]:
        target_plat_id = p["platform_id"]
        break

if target_plat_id:
    # 为目标平台配置 API Key（来自环境变量）
    mgr.update_platform_config("-1", target_plat_id, platform_api_key)
    print(f"✅ Successfully set API key for 阿里云百炼 (ID: {target_plat_id})")
    
    # 探测一下有哪些模型或者直接拿这个平台加一个 qwen3.5flash 模型用于专门测试
    models = mgr.get_platform_models("-1")
    flash_id = None
    for m in models:
        if m["platform_id"] == target_plat_id and "qwen" in m["model_name"]:
            print("Found model:", m["model_name"], "->", m["display_name"])
            if m["model_name"] == "qwen3.5flash" or m["display_name"] == "qwen3.5flash":
                flash_id = m["model_id"]
    
    if not flash_id:
        print("Adding model qwen3.5flash to 阿里云百炼")
        mgr.add_model(
            platform_id=target_plat_id,
            model_name="qwen3.5flash",
            display_name="qwen3.5-flash",
            admin_mode=True
        )
        print("Model added.")
else:
    print("❌ Could not find platform 阿里云百炼")
