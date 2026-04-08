"""测试 execute_requests_node"""
import asyncio
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[2]
os.chdir(backend_dir)
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.graph.nodes import execute_requests_node
from app.schemas.task import TaskPlan, TaskStep
from app.schemas.policy import PolicyVerdict, PolicyAction

async def test():
    # 创建测试状态
    plan = TaskPlan(
        plan_id='test_plan',
        description='测试计划',
        steps=[
            TaskStep(
                step_id='step_1',
                order=1,
                capability_id='get_user_info',
                route_id='GET:/api/user/info',
                action='获取用户信息',
                parameters={},
                safety_level='readonly_safe',
                requires_confirmation=False,
            )
        ],
        estimated_duration_ms=5000,
    )
    
    verdicts = [
        PolicyVerdict(
            verdict_id='v1',
            route_id='GET:/api/user/info',
            capability_id='get_user_info',
            action=PolicyAction.ALLOW,
            safety_level='readonly_safe',
            permission_level='authenticated',
            reasons=['测试'],
            evidence={},
            redaction_fields=[],
            approval_timeout_seconds=300,
            approval_message='',
            block_reason=None,
        )
    ]
    
    state = {
        'session_id': 'test',
        'project_id': 'test',
        'task_plan': plan,
        'policy_verdicts': verdicts,
        'execution_artifacts': [],
    }
    
    print('--- Testing execute_requests_node ---')
    result = await execute_requests_node(state)
    
    print(f'Error: {result.get("error")}')
    print(f'Artifacts: {len(result.get("execution_artifacts", []))}')
    for a in result.get('execution_artifacts', []):
        print(f'  - {a.route_id}: {a.status_code}')
        print(f'    Response: {a.response_body}')

if __name__ == '__main__':
    asyncio.run(test())
