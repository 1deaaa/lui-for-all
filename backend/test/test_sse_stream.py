"""测试 SSE 流端到端"""
import asyncio
import httpx

async def test_sse():
    url = 'http://localhost:8000/api/sessions/39770a2e-dcd5-4ba7-a60f-9276b186ace1/events/stream?task_run_id=f85d833b-b5ee-4c5e-bb71-8f0606ce987b'
    
    print(f"Connecting to SSE stream...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream('GET', url) as response:
            print(f"Status: {response.status_code}")
            async for line in response.aiter_lines():
                print(f"Event: {line}")

if __name__ == '__main__':
    asyncio.run(test_sse())
