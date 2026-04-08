"""直接测试 LangGraph 执行"""
import asyncio
import sys
import os
from pathlib import Path

# 切换到 backend 目录以正确加载 .env 配置
backend_dir = Path(__file__).resolve().parents[2]
os.chdir(backend_dir)
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.graph.graph import graph_app
from app.models.project import CapabilityRecord
from sqlalchemy import select
from app.db import async_session

async def test():
    async with async_session() as db:
        result = await db.execute(
            select(CapabilityRecord)
            .where(CapabilityRecord.project_id == 'a10c0bd3-1716-4d5e-83ae-6fe7f5ccf206')
            .limit(20)
        )
        caps = result.scalars().all()
        print(f'Found {len(caps)} capabilities')
        
        available_capabilities = [
            {
                'capability_id': c.capability_id,
                'name': c.name,
                'description': c.description,
                'domain': c.domain,
                'safety_level': c.safety_level,
                'backed_by_routes': c.backed_by_routes,
                'user_intent_examples': c.user_intent_examples,
                'permission_level': c.permission_level,
                'data_sensitivity': c.data_sensitivity,
                'best_modalities': c.best_modalities,
                'requires_confirmation': c.requires_confirmation,
                'parameter_hints': c.parameter_hints,
            }
            for c in caps
        ]
        
        state = {
            'session_id': 'test',
            'project_id': 'a10c0bd3-1716-4d5e-83ae-6fe7f5ccf206',
            'trace_id': 'test',
            'user_message': '获取系统公告',
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
        config = {'configurable': {'thread_id': 'test_todo_3'}}
        
        print('\n--- Starting LangGraph execution ---')
        final_state = None
        async for event in graph_app.astream(state, config, stream_mode='values'):
            node = event.get('current_node')
            error = event.get('error')
            sel_caps = len(event.get('selected_capabilities', []))
            task_plan = 'Yes' if event.get('task_plan') else 'No'
            print(f'Node: {node}, SelCaps: {sel_caps}, Plan: {task_plan}, Error: {error}')
            final_state = event
        
        print(f'\n--- Final state ---')
        if final_state:
            print(f'Summary: {final_state.get("summary_text")}')
            print(f'Artifacts: {len(final_state.get("execution_artifacts", []))}')

if __name__ == '__main__':
    asyncio.run(test())
