"""测试 LangGraph 执行"""
import asyncio
from app.graph.graph import graph_app

async def test():
    # 模拟项目能力列表
    available_capabilities = [
        {
            "capability_id": "list_characters",
            "name": "列出所有角色",
            "description": "获取系统中所有角色的列表",
            "domain": "content",
            "safety_level": "readonly_safe",
            "backed_by_routes": [{"route_id": "get_characters", "role": "primary"}],
            "user_intent_examples": ["列出角色", "查看所有角色"],
            "permission_level": "authenticated",
            "data_sensitivity": "low",
            "best_modalities": ["text_block"],
            "requires_confirmation": False,
            "parameter_hints": {},
        }
    ]
    
    state = {
        'session_id': 'test',
        'project_id': 'test',
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
    config = {'configurable': {'thread_id': 'test'}}
    try:
        async for event in graph_app.astream(state, config, stream_mode='values'):
            print(f'Node: {event.get("current_node")}, Error: {event.get("error")}')
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test())
