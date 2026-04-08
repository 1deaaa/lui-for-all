"""
测试全量源码 AI 建图模块
此脚本将触发一个基于 FastAPI 测试的后端发现流程。
"""

import asyncio
import os
import sys
from pathlib import Path

# 将应用路径加入 sys.path
backend_path = Path(__file__).resolve().parents[2]
if str(backend_path) not in sys.path:
    sys.path.append(str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

if not os.getenv("LUI_LLM_API_KEY"):
    raise RuntimeError("请先设置环境变量 LUI_LLM_API_KEY")

from app.db import Base
from app.schemas.route_map import RouteMap, RouteInfo, HttpMethod
from app.discovery.capability_builder import build_capability_graph

async def simulate_discovery():
    print("🚀 启动大模型全量扫描测试...")
    
    # 构建内存 SQLite 会话
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # 模拟从 OpenAPI 收集到了这两条路由
    mock_routes = [
        RouteInfo(
            route_id="POST:/api/projects/import",
            path="/api/projects/import",
            method=HttpMethod.POST,
            summary="导入项目",
            description="从用户提交的地址导入远端项目信息",
            tags=["Project"],
            parameters=[],
        ),
        RouteInfo(
            route_id="GET:/api/projects/{project_id}/capabilities",
            path="/api/projects/{project_id}/capabilities",
            method=HttpMethod.GET,
            summary="获取项目的能力图谱",
            description="获取所有路由推演出的详细用语规范与能力列表",
            tags=["Project"],
            parameters=[],
        )
    ]
    
    mock_route_map = RouteMap(
        project_id="test-proj-001",
        version="1.0",
        base_url="http://localhost",
        routes=mock_routes,
        discovered_at="2026-03-25T00:00:00Z"
    )
    
    try:
        # 调用我们大改的核心方法
        graph = await build_capability_graph(mock_route_map)
        
        print(f"\n✅ 成功生成能力图谱, 包含 {len(graph.capabilities)} 个能力。")
        for cap in graph.capabilities:
            print(f"================================================")
            print(f"⚡ 能力 ID: {cap.capability_id}")
            print(f"   名称: {cap.name}")
            print(f"   安全等级: {cap.safety_level.value}")
            print(f"   业务领域: {cap.domain.value}")
            print(f"   必需确认: {cap.requires_confirmation}")
            print(f"   UI 组件: {[m.value for m in cap.best_modalities]}")
            print(f"   [LLM 提取规范 (AI Usage)]: {cap.ai_usage_guidelines}")
            print(f"   [源码推断说明 (Analysis)]: {cap.source_code_analysis}")
            print(f"================================================\n")
            
    except Exception as e:
        import traceback
        print(f"❌ 分析过程崩溃: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(simulate_discovery())
