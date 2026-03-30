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
        
        current_event = None
        
        async with client.stream("GET", f"{BASE_URL}/api/sessions/{session_id}/events/stream", params={"task_run_id": task_run_id}) as response:
            print(f"DEBUG: Response status: {response.status_code}")
            async for line in response.aiter_lines():
                if not line.strip():
                    current_event = None
                    continue
                
                if line.startswith("event: "):
                    current_event = line[7:].strip()
                    # print(f"DEBUG: Found event type: {current_event}")
                elif line.startswith("data: "):
                    try:
                        data_json = json.loads(line[6:])
                        
                        event_type = current_event or data_json.get("event")
                        
                        if event_type == "thought_emitted":
                            token = data_json.get("token", "")
                            print(f"\033[90m{token}\033[0m", end="", flush=True)
                        
                        elif event_type == "token_emitted":
                            token = data_json.get("token", "")
                            print(f"\033[92m{token}\033[0m", end="", flush=True)
                        
                        elif event_type == "task_progress":
                            msg = data_json.get("message", "")
                            prog = data_json.get("progress", 0)
                            print(f"\n\033[94m[PROGRESS {prog*100:.0f}%]\033[0m {msg}")
                            
                        elif event_type == "task_completed":
                            print(f"\n\n\033[96m[COMPLETED]\033[0m 任务完成。")
                            break
                            
                        elif event_type == "error":
                            print(f"\n\n\033[91m[ERROR]\033[0m {data_json.get('error_message')}")
                            # print(f"DEBUG ERROR RAW: {data_json}")
                            break
                        
                        elif event_type == "session_started":
                            print(f"\033[95m[SESSION STARTED]\033[0m")
                            
                    except Exception as e:
                        print(f"DEBUG: Parse error on line: {line} - {e}")

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "你好，帮我算一下 1+2+3 是多少"
    asyncio.run(test_streaming(query))
