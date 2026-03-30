import asyncio
import httpx
import json
import sys

BASE_URL = "http://127.0.0.1:8000"
PROJECT_ID = "a76fae98-5b7a-414f-b161-fc4c13a1a809"

async def test_streaming(query: str):
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. 创建会话
        print(f"\n[1/3] 创建会话，项目ID: {PROJECT_ID}...")
        resp = await client.post(f"{BASE_URL}/api/sessions/", json={"project_id": PROJECT_ID})
        resp.raise_for_status()
        session_id = resp.json()["session_id"]
        print(f"✅ 会话已创建: {session_id}")

        # 2. 发送消息
        print(f"[2/3] 发送消息: '{query}'...")
        resp = await client.post(f"{BASE_URL}/api/sessions/{session_id}/messages", json={"content": query})
        resp.raise_for_status()
        data = resp.json()
        task_run_id = data["task_run_id"]
        print(f"✅ 任务 ID: {task_run_id}")

        # 3. 监听 SSE 流
        print(f"[3/3] 正在建立 SSE 连接并监听流式输出...\n" + "="*50)
        
        async with client.stream("GET", f"{BASE_URL}/api/sessions/{session_id}/events/stream", params={"task_run_id": task_run_id}) as response:
            print(f"DEBUG: Response status: {response.status_code}")
            print(f"DEBUG: Response headers: {response.headers}")
            async for line in response.aiter_lines():
                print(f"DEBUG raw: {line}") # 可以在调试时开启
                if not line.strip():
                    continue
                
                if line.startswith("data: "):
                    try:
                        event_payload = json.loads(line[6:])
                        event_type = event_payload.get("event")
                        
                        if event_type == "thought_emitted":
                            # 推理内容（灰色）
                            token = event_payload.get("token", "")
                            print(f"\033[90m{token}\033[0m", end="", flush=True)
                        
                        elif event_type == "token_emitted":
                            # 正文内容（绿色）
                            token = event_payload.get("token", "")
                            print(f"\033[92m{token}\033[0m", end="", flush=True)
                        
                        elif event_type == "task_progress":
                            # 进度更新
                            msg = event_payload.get("message", "")
                            prog = event_payload.get("progress", 0)
                            print(f"\n\033[94m[PROGRESS {prog*100:.0f}%]\033[0m {msg}")
                            
                        elif event_type == "task_completed":
                            print(f"\n\n\033[96m[COMPLETED]\033[0m 任务完成。")
                            break
                            
                        elif event_type == "error":
                            print(f"\n\n\033[91m[ERROR]\033[0m {event_payload.get('error_message')}")
                            break
                            
                    except Exception as e:
                        pass # 忽略解析错误

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = sys.argv[1]
    else:
        query = "请帮我分析一下 1 + 2 + ... + 10 是多少，分步计算并展示你的深度思考。"
    
    asyncio.run(test_streaming(query))
