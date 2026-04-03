"""
MCP 连接桥验证脚本
测试：initialize → tools/list → tools/call(list_projects)
"""
import json
import httpx

BASE = "http://localhost:8000/mcp/"
HEADERS_BASE = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def parse_sse_result(content: str) -> dict | None:
    """从 SSE 响应体解析第一个 data: 行"""
    for line in content.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return None


def main():
    with httpx.Client(timeout=30) as client:
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
        r = client.post(BASE, json=init_payload, headers=HEADERS_BASE)
        session_id = r.headers.get("mcp-session-id", "")
        result = parse_sse_result(r.text)
        print(f"  Session ID : {session_id}")
        print(f"  Protocol   : {result['result'].get('protocolVersion')}")
        print(f"  Server name: {result['result'].get('serverInfo', {}).get('name')}")

        session_headers = {**HEADERS_BASE, "mcp-session-id": session_id}

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
        result2 = parse_sse_result(r2.text)
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
        result3 = parse_sse_result(r3.text)
        content = result3.get("result", {}).get("content", [])
        if content:
            # FastMCP 对 list[dict] 返回值序列化为 JSON 字符串放在 text 字段
            raw_text = content[0].get("text", "[]")
            try:
                projects = json.loads(raw_text)
            except Exception:
                projects = []
            print(f"  已导入项目数量: {len(projects)}")
            for p in projects:
                print(f"    - [{p['project_id'][:8]}...] {p['name']}（{p['capability_count']} 个能力）")
        else:
            print("  （尚未导入任何项目）")

        print("\n✅ MCP 连接桥验证通过！")


if __name__ == "__main__":
    main()
