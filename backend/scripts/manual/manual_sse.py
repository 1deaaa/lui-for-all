"""测试 SSE 流"""
import asyncio
import httpx

async def test_sse():
    url = "http://localhost:6689/api/sessions/a1a397dc-98f1-47fa-8286-09dfbffccc3e/events/stream?task_run_id=7fe3efe7-254f-44e9-8b09-02fd00e3e18a"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("GET", url) as response:
            print(f"Status: {response.status_code}")
            async for line in response.aiter_lines():
                print(f"Line: {line}")

if __name__ == '__main__':
    asyncio.run(test_sse())
