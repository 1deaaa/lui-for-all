import asyncio, httpx, time, json
async def test():
    async with httpx.AsyncClient() as client:
        res = await client.post('http://127.0.0.1:6689/api/sessions/', json={'project_id': 'a76fae98-5b7a-414f-b161-fc4c13a1a809'}, timeout=10)
        session_id = res.json()['session_id']
        res2 = await client.post(f'http://127.0.0.1:6689/api/sessions/{session_id}/messages', json={'content': '你好，介绍一下你自己，详细描述你的思考过程并逐步打出'}, timeout=10)
        task_id = res2.json()['task_run_id']
        
        start_t = time.time()
        print('Starting stream...')
        async with client.stream('GET', f'http://127.0.0.1:6689/api/sessions/{session_id}/events/stream?task_run_id={task_id}', timeout=60) as response:
            async for line in response.aiter_lines():
                if line.startswith('data:'):
                    try:
                        data = json.loads(line[5:])
                        if data.get('event') == 'token_emitted':
                            print(f'{time.time() - start_t:.3f}s: {data.get("token")}')
                        elif data.get('event') == 'task_progress':
                            print(f'{time.time() - start_t:.3f}s: PROGRESS {data.get("message")}')
                    except Exception:
                        pass
asyncio.run(test())
