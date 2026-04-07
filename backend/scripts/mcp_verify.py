"""
MCP 连接桥验证脚本
测试：initialize → tools/list → tools/call(list_projects) → tools/call(chat)
"""
import os
import json
import httpx

BASE = "http://localhost:6689/mcp/"
HEADERS_BASE = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def parse_sse_result(content: str) -> dict | None:
    """从 SSE 响应体解析第一个 data: 行。"""
    for line in content.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return None


def parse_sse_events(content: str) -> list[dict]:
    """从 SSE 响应体解析全部 data 事件。"""
    events: list[dict] = []
    for line in content.splitlines():
        if line.startswith("data:"):
            try:
                events.append(json.loads(line[5:].strip()))
            except Exception:
                continue
    return events


def parse_rpc_response(resp: httpx.Response, expected_id: int | None = None) -> dict:
    """兼容解析 SSE 或普通 JSON 响应，并优先返回指定 id 的响应事件。"""
    events = parse_sse_events(resp.text)
    if events:
        if expected_id is not None:
            for event in events:
                if event.get("id") == expected_id:
                    return event
        return events[-1]

    try:
        return resp.json()
    except Exception:
        return {"error": {"message": resp.text or "empty response"}}


def load_mcp_token(client: httpx.Client) -> str:
    """优先从环境变量读取 token，其次回退读取 /api/settings。"""
    env_token = (os.getenv("LUI_MCP_API_TOKEN") or "").strip()
    if env_token:
        return env_token

    try:
        settings_resp = client.get("http://localhost:6689/api/settings")
        settings_resp.raise_for_status()
        payload = settings_resp.json()
        return (payload.get("mcp_api_token") or "").strip()
    except Exception:
        return ""


def main():
    with httpx.Client(timeout=30) as client:
        token = load_mcp_token(client)
        headers = dict(HEADERS_BASE)
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # ── Step 1: initialize ──
        print("=== Step 1: initialize ===")
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "mcp-verify", "version": "1.0"},
            },
        }
        r = client.post(BASE, json=init_payload, headers=headers)
        if r.status_code >= 400:
            raise RuntimeError(f"initialize 失败: HTTP {r.status_code} {r.text}")

        session_id = r.headers.get("mcp-session-id", "")
        result = parse_rpc_response(r, expected_id=1)
        if "result" not in result:
            raise RuntimeError(f"initialize 返回异常: {result}")

        print(f"  Session ID : {session_id}")
        print(f"  Protocol   : {result['result'].get('protocolVersion')}")
        print(f"  Server name: {result['result'].get('serverInfo', {}).get('name')}")

        session_headers = {**headers, "mcp-session-id": session_id}

        # ── Step 2: initialized notification ──
        client.post(
            BASE,
            json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            headers=session_headers,
        )

        # ── Step 3: tools/list ──
        print("\n=== Step 2: tools/list ===")
        r2 = client.post(
            BASE,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers=session_headers,
        )
        result2 = parse_rpc_response(r2, expected_id=2)
        if "result" not in result2:
            raise RuntimeError(f"tools/list 返回异常: {result2}")

        tools = result2["result"]["tools"]
        print(f"  已注册工具数量: {len(tools)}")
        for t in tools:
            print(f"    ✓ {t['name']}: {t['description'][:60]}...")

        # ── Step 4: list_projects ──
        print("\n=== Step 3: tools/call(list_projects) ===")
        r3 = client.post(
            BASE,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_projects", "arguments": {}},
            },
            headers=session_headers,
        )
        result3 = parse_rpc_response(r3, expected_id=3)
        structured = result3.get("result", {}).get("structuredContent", {})
        projects = structured.get("result", [])
        print(f"  已导入项目数量: {len(projects)}")
        for p in projects:
            print(f"    - [{p['project_id'][:8]}...] {p['name']}（{p.get('capability_count', 0)} 个能力）")

        if projects:
            print("\n=== Step 4: tools/call(chat) ===")
            first_project_id = projects[0]["project_id"]
            r4 = client.post(
                BASE,
                json={
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "chat",
                        "arguments": {
                            "project_id": first_project_id,
                            "message": "请用一句话回复：MCP chat 连接测试通过。",
                        },
                    },
                },
                headers=session_headers,
            )
            result4 = parse_rpc_response(r4, expected_id=4)
            is_error = bool(result4.get("result", {}).get("isError"))
            if is_error:
                raise RuntimeError(f"chat 调用失败: {result4}")

            text_items = result4.get("result", {}).get("content", [])
            preview = text_items[0].get("text", "")[:120] if text_items else ""
            print(f"  chat 返回预览: {preview}")

        print("\n✅ MCP 连接桥验证通过！")


if __name__ == "__main__":
    main()
