"""测试 SSE 流详细日志"""
import asyncio
import httpx
import json

async def test_sse():
    # 创建 session 和 message
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 创建 session
        resp = await client.post(
            'http://localhost:8000/api/sessions/',
            json={"project_id": "a10c0bd3-1716-4d5e-83ae-6fe7f5ccf206"}
        )
        session = resp.json()
        session_id = session["session_id"]
        print(f"Session: {session_id}")
        
        # 发送消息
        resp = await client.post(
            f'http://localhost:8000/api/sessions/{session_id}/messages',
            json={"content": "查看公告历史"}
        )
        msg = resp.json()
        task_run_id = msg["task_run_id"]
        print(f"TaskRun: {task_run_id}")
        
        # 连接 SSE 流
        url = f'http://localhost:8000/api/sessions/{session_id}/events/stream?task_run_id={task_run_id}'
        print(f"URL: {url}")
        
        async with client.stream('GET', url) as response:
            print(f"Status: {response.status_code}")
            async for line in response.aiter_lines():
                if line.startswith('data:'):
                    try:
                        data = json.loads(line[5:].strip())
                        if 'summary' in data or 'error' in data:
                            print(f"Event: {line}")
                    except:
                        pass

if __name__ == '__main__':
    asyncio.run(test_sse())
