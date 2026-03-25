"""测试 SSE 流"""
import asyncio
import httpx

async def test():
    url = 'http://localhost:8000/api/sessions/1ee1f44b-cbec-4cc1-b326-346ac6801877/events/stream?task_run_id=dd63367e-6adc-4ce6-a260-aab8de60742a'
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream('GET', url) as response:
            print(f'Status: {response.status_code}')
            async for data in response.aiter_bytes():
                print(f'Data: {data}')

if __name__ == '__main__':
    asyncio.run(test())
