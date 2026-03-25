"""测试 LangGraph 执行 - 使用真实数据库能力"""
import asyncio
from app.graph.graph import graph_app
from app.models.project import CapabilityRecord
from sqlalchemy import select
from app.db import async_session

async def test_with_db():
    async with async_session() as db:
        result = await db.execute(
            select(CapabilityRecord)
            .where(CapabilityRecord.project_id == 'a10c0bd3-1716-4d5e-83ae-6fe7f5ccf206')
            .limit(10)
        )
        caps = result.scalars().all()
        print(f'Found {len(caps)} capabilities')
        for c in caps:
            print(f'  - {c.capability_id}: {c.name}')
        
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
            'user_message': '列出所有角色',
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
        config = {'configurable': {'thread_id': 'test_real_db'}}
        
        print('\n--- Starting LangGraph execution ---')
        async for event in graph_app.astream(state, config, stream_mode='values'):
            node = event.get('current_node')
            error = event.get('error')
            print(f'Node: {node}, Error: {error}')
            if error:
                break

if __name__ == '__main__':
    asyncio.run(test_with_db())
