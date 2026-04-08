import asyncio, httpx, time

async def test():
    async with httpx.AsyncClient() as client:
            res = await client.post("http://127.0.0.1:6689/api/sessions/", json={"project_id": "a76fae98-5b7a-414f-b161-fc3ebf892d13"}, timeout=10)
        session_id = res.json()["session_id"]
            res2 = await client.post(f"http://127.0.0.1:6689/api/sessions/{session_id}/messages", json={"content": "讲一个30个字的小故事"}, timeout=10)
        task_id = res2.json()["task_run_id"]
        
        print(f"Starting stream for task {task_id}...")
            async with client.stream("GET", f"http://127.0.0.1:6689/api/sessions/{session_id}/events/stream?task_run_id={task_id}", timeout=60) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    import json
                    try:
                        data = json.loads(line[5:])
                        if data.get("event") == "token_emitted":
                            print(f"{time.time():.3f} - TOKEN: {data.get('token')}")
                    except Exception as e:
                        pass

if __name__ == "__main__":
    asyncio.run(test())
