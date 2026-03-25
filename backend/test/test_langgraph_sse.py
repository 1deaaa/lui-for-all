"""测试 SSE 流并捕获后端日志"""
import asyncio
import httpx
import sys
import os

# 添加后端路径
sys.path.insert(0, 'd:/Desktop/talk-to-interface/backend')
os.chdir('d:/Desktop/talk-to-interface/backend')

async def test():
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 创建 session
        resp = await client.post(
            'http://localhost:8000/api/sessions/',
            json={'project_id': 'a10c0bd3-1716-4d5e-83ae-6fe7f5ccf206'}
        )
        session = resp.json()
        session_id = session['session_id']
        print(f'Session: {session_id}')
        
        # 发送消息
        resp = await client.post(
            f'http://localhost:8000/api/sessions/{session_id}/messages',
            json={'content': '查看公告历史'}
        )
        msg = resp.json()
        task_run_id = msg['task_run_id']
        print(f'TaskRun: {task_run_id}')
        
        # 直接调用 LangGraph 测试
        from app.graph.graph import graph_app
        from app.models.project import CapabilityRecord
        from sqlalchemy import select
        from app.db import async_session
        
        async with async_session() as db:
            result = await db.execute(
                select(CapabilityRecord)
                .where(CapabilityRecord.project_id == 'a10c0bd3-1716-4d5e-83ae-6fe7f5ccf206')
                .limit(20)
            )
            caps = result.scalars().all()
            
            available_capabilities = [
                {
                    'capability_id': c.capability_id,
                    'name': c.name,
                    'description': c.description,
                    'domain': c.domain,
                    'safety_level': c.safety_level,
                    'backed_by_routes': c.backed_by_routes,
                }
                for c in caps
            ]
        
        # 构建初始状态
        initial_state = {
            'session_id': session_id,
            'project_id': 'a10c0bd3-1716-4d5e-83ae-6fe7f5ccf206',
            'trace_id': 'test',
            'user_message': '查看公告历史',
            'normalized_intent': None,
            'available_capabilities': available_capabilities,
            'selected_capabilities': [],
            'task_plan': None,
            'policy_verdicts': [],
            'approval_status': 'pending',
            'execution_artifacts': [],
            'summary_text': None,
            'ui_blocks': [],
            'error': None,
            'current_node': None,
        }
        
        # 执行图
        config = {'configurable': {'thread_id': session_id}}
        
        print("\n--- Direct LangGraph execution ---")
        final_state = None
        async for event in graph_app.astream(initial_state, config, stream_mode="values"):
            if event.get("current_node"):
                print(f"Node: {event.get('current_node')}")
                print(f"  SelCaps: {len(event.get('selected_capabilities', []))}")
                print(f"  Plan: {'Yes' if event.get('task_plan') else 'No'}")
                print(f"  Error: {event.get('error')}")
            final_state = event
        
        print(f"\n--- Final state ---")
        print(f"Summary: {final_state.get('summary_text')}")
        print(f"Artifacts: {len(final_state.get('execution_artifacts', []))}")

if __name__ == '__main__':
    asyncio.run(test())
