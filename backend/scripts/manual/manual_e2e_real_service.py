"""
测试完整端到端 AI 调度链 (Graph)
1. 导入项目 (针对 backendfortest 的 Uvicorn 真实服务)
2. 触发 AI 建图 (发现能力并总结限制)
3. 询问 LangGraph 自然语言
"""

import asyncio
import os
import sys
from pathlib import Path

# 注入运行路径并读取环境变量
backend_path = Path(__file__).resolve().parents[2]
if str(backend_path) not in sys.path:
    sys.path.append(str(backend_path))

if not os.getenv("LUI_LLM_API_KEY"):
    raise RuntimeError("请先设置环境变量 LUI_LLM_API_KEY")

os.environ.setdefault("LUI_DB_PATH", "workspace/lui.db")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.api.projects import import_project, ProjectImportRequest, trigger_discovery
from app.graph.graph import graph_app

async def main():
    print("🔥 准备环境与数据库...")
    engine = create_async_engine(f"sqlite+aiosqlite:///{backend_path / 'workspace' / 'lui.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_maker() as db:
        print("🌍 1. 导入测试项目 (backendfortest)")
        req = ProjectImportRequest(
            name="真实测试后端",
            base_url="http://127.0.0.1:6690",
            openapi_url="http://127.0.0.1:6690/openapi.json",
            description="用于测试 Uvicorn 端起的服务"
        )
        import_res = await import_project(req, db)
        project_id = import_res.project_id
        print(f"   项目已创建 ID: {project_id}")
        
        print("🧠 2. 触发 AI 发现与全量图谱重建 (可能需要 1~2 分钟)...")
        # 直接使用我们在 api 中的方法，因为那个方法读取了真实代码并让 LLM 进行推断
        await trigger_discovery(project_id, db)
        print("   ✅ 项目图谱发现完成！")
        
        print("💬 3. 使用自然语言提问，测试真实图谱选择")
        # 创建一个 LangGraph 会话
        config = {
            "configurable": {
                "thread_id": "test_e2e_thread_001",
                "project_id": project_id,
            }
        }
        
        # 提问："我想要获取当前系统运行的环境变量或配置列表"
        print("--------------------------------------------------")
        print("用户: 获取后端系统中所有的文件列表（假设存在此接口）。")
        
        async for event in graph_app.astream(
            {"messages": [("user", "获取后端系统中所有的文件列表")]},
            config=config,
            stream_mode="updates",
        ):
            for node, values in event.items():
                print(f"[{node}] 节点执行完毕。")
                if isinstance(values, dict) and "messages" in values and values["messages"]:
                    latest_msg = values["messages"][-1]
                    # 有些消息可能没有 content 属性，用 getattr 保底
                    content = getattr(latest_msg, "content", str(latest_msg))
                    print(f"       >> {content}")

        # 如果没有确切的文件列表，我们可以改问一个明确存在的能力，再走一次
        print("--------------------------------------------------")
        print("用户: 看看这后端有什么可用的测试能力？")
        async for event in graph_app.astream(
            {"messages": [("user", "看看这后端有什么可用的测试能力？")]},
            config=config,
            stream_mode="updates",
        ):
            for node, values in event.items():
                print(f"[{node}] 节点执行完毕。")
                if isinstance(values, dict) and "messages" in values and values["messages"]:
                    latest_msg = values["messages"][-1]
                    content = getattr(latest_msg, "content", str(latest_msg))
                    print(f"       >> {content}")

if __name__ == "__main__":
    asyncio.run(main())
