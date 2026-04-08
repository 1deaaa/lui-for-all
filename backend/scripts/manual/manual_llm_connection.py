"""测试 LLM API 连接"""
import asyncio
import httpx
import os

print(f'HTTP_PROXY: {os.environ.get("HTTP_PROXY", "Not set")}')
print(f'HTTPS_PROXY: {os.environ.get("HTTPS_PROXY", "Not set")}')

async def test():
    # 测试直接连接
    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            response = await client.get('https://api.devlens.top/v1/models')
            print(f'Direct Status: {response.status_code}')
    except Exception as e:
        print(f'Direct error: {type(e).__name__}: {e}')
    
    # 测试代理连接
    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False, proxy='http://127.0.0.1:7890') as client:
            response = await client.get('https://api.devlens.top/v1/models')
            print(f'Proxy Status: {response.status_code}')
    except Exception as e:
        print(f'Proxy error: {type(e).__name__}: {e}')

if __name__ == '__main__':
    asyncio.run(test())
