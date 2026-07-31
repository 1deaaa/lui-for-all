"""
端到端 AI 对话 SSE 采集测试

测试链路：用户消息 → AI 决策 → 调用 SSE 端点 → 采集流数据 → 处理结果 → 流式回复

用法：
  python test_e2e_ai_sse.py
"""

import json
import sys
import time

import httpx
import jwt
import datetime

BASE_URL = "http://localhost:6689"
JWT_SECRET = "lui-for-all-jwt-secret-2024"
PROJECT_ID = "97db94ee-82ec-4de0-b52f-15598f6eb2ea"  # FastAPI 示例项目


def make_token() -> str:
    return jwt.encode(
        {
            "sub": "lui-admin",
            "iat": datetime.datetime.now(datetime.UTC),
            "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def parse_sse_lines(raw: bytes) -> list[dict]:
    """从原始 SSE 字节流中解析事件"""
    events = []
    current_event = {}
    for line in raw.decode("utf-8", errors="replace").split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            current_event["event"] = line[6:].strip()
        elif line.startswith("data:"):
            data_str = line[5:].strip()
            try:
                current_event["data"] = json.loads(data_str)
            except json.JSONDecodeError:
                current_event["data"] = data_str
        elif line == "" and current_event:
            events.append(current_event)
            current_event = {}
    if current_event:
        events.append(current_event)
    return events


def manual_test_notification_sse(token: str):
    """测试1：让 AI 采集 /api/stream/notifications 的 SSE 数据"""
    print("\n" + "=" * 60)
    print("测试1：AI 采集通知流 SSE → /api/stream/notifications")
    print("=" * 60)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "project_id": PROJECT_ID,
        "content": "请调用 stream_call 方式采集 http://localhost:8010/api/stream/notifications 的 SSE 数据，使用 event_count 策略采集 5 条事件，然后告诉我你采集到了什么内容",
    }

    start = time.time()
    print(f"\n发送请求... ({time.strftime('%H:%M:%S')})")

    with httpx.Client(timeout=120.0) as client:
        with client.stream("POST", f"{BASE_URL}/api/chat/stream", json=payload, headers=headers) as resp:
            print(f"状态码: {resp.status_code}")
            print(f"Content-Type: {resp.headers.get('content-type')}")

            all_events = []
            buffer = ""
            for chunk in resp.iter_bytes():
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n\n" in buffer:
                    raw_event, buffer = buffer.split("\n\n", 1)
                    event = {}
                    for line in raw_event.strip().split("\n"):
                        if line.startswith("event:"):
                            event["event"] = line[6:].strip()
                        elif line.startswith("data:"):
                            data_str = line[5:].strip()
                            try:
                                event["data"] = json.loads(data_str)
                            except json.JSONDecodeError:
                                event["data"] = data_str
                    if event:
                        all_events.append(event)

    elapsed = time.time() - start
    print(f"\n耗时: {elapsed:.1f}s")
    print(f"收到 {len(all_events)} 个 SSE 事件")

    print("\n--- 事件流概览 ---")
    for i, ev in enumerate(all_events):
        event_type = ev.get("event", "unknown")
        data = ev.get("data", {})
        if isinstance(data, dict):
            # 简化输出
            if event_type == "token_emitted":
                token_text = data.get("token", "")
                if token_text:
                    print(f"  [{i}] {event_type}: {token_text[:80]}{'...' if len(token_text) > 80 else ''}")
            elif event_type == "tool_started":
                print(f"  [{i}] {event_type}: tool={data.get('tool_name')} title={data.get('title')}")
            elif event_type == "tool_completed":
                print(f"  [{i}] {event_type}: tool={data.get('tool_name')} status={data.get('status_code')}")
            elif event_type == "task_completed":
                print(f"  [{i}] {event_type}: summary={str(data.get('summary', ''))[:100]}")
            elif event_type == "task_failed":
                print(f"  [{i}] {event_type}: error={data.get('error_message')}")
            else:
                summary = str(data)[:120]
                print(f"  [{i}] {event_type}: {summary}")
        else:
            print(f"  [{i}] {event_type}: {str(data)[:100]}")

    # 验证关键事件
    event_types = [ev.get("event") for ev in all_events]
    print("\n--- 验证 ---")

    checks = {
        "session_started": "session_started" in event_types,
        "task_started": "task_started" in event_types,
        "token_emitted (有AI回复)": "token_emitted" in event_types,
        "task_completed (任务完成)": "task_completed" in event_types,
    }

    # 检查是否有工具调用
    tool_calls = [ev for ev in all_events if ev.get("event") in ("tool_started", "tool_completed")]
    checks["tool_started (有工具调用)"] = len(tool_calls) > 0

    # 检查 token 内容是否包含有意义的回复
    tokens = [
        ev.get("data", {}).get("token", "")
        for ev in all_events
        if ev.get("event") == "token_emitted" and isinstance(ev.get("data"), dict)
    ]
    full_reply = "".join(tokens)
    checks["token 内容非空"] = len(full_reply) > 10
    if full_reply:
        print(f"\nAI 完整回复:\n{full_reply[:500]}{'...' if len(full_reply) > 500 else ''}")

    all_pass = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_pass = False

    return all_pass


def manual_test_alerts_sse(token: str):
    """测试2：让 AI 采集 /api/stream/alerts 的 SSE 数据"""
    print("\n" + "=" * 60)
    print("测试2：AI 采集告警流 SSE → /api/stream/alerts")
    print("=" * 60)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "project_id": PROJECT_ID,
        "content": "请调用 stream_call 方式采集 http://localhost:8010/api/stream/alerts?max_alerts=3 的 SSE 数据，使用 event_count 策略采集 3 条事件，然后把采集到的告警内容总结给我",
    }

    start = time.time()
    print(f"\n发送请求... ({time.strftime('%H:%M:%S')})")

    with httpx.Client(timeout=120.0) as client:
        with client.stream("POST", f"{BASE_URL}/api/chat/stream", json=payload, headers=headers) as resp:
            print(f"状态码: {resp.status_code}")

            all_events = []
            buffer = ""
            for chunk in resp.iter_bytes():
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n\n" in buffer:
                    raw_event, buffer = buffer.split("\n\n", 1)
                    event = {}
                    for line in raw_event.strip().split("\n"):
                        if line.startswith("event:"):
                            event["event"] = line[6:].strip()
                        elif line.startswith("data:"):
                            data_str = line[5:].strip()
                            try:
                                event["data"] = json.loads(data_str)
                            except json.JSONDecodeError:
                                event["data"] = data_str
                    if event:
                        all_events.append(event)

    elapsed = time.time() - start
    print(f"\n耗时: {elapsed:.1f}s")
    print(f"收到 {len(all_events)} 个 SSE 事件")

    event_types = [ev.get("event") for ev in all_events]

    print("\n--- 事件流概览 ---")
    for i, ev in enumerate(all_events):
        event_type = ev.get("event", "unknown")
        data = ev.get("data", {})
        if isinstance(data, dict):
            if event_type == "token_emitted":
                token_text = data.get("token", "")
                if token_text:
                    print(f"  [{i}] {event_type}: {token_text[:80]}")
            elif event_type == "tool_started":
                print(f"  [{i}] {event_type}: tool={data.get('tool_name')} detail={str(data.get('detail', ''))[:80]}")
            elif event_type == "tool_completed":
                print(f"  [{i}] {event_type}: tool={data.get('tool_name')}")
            elif event_type == "task_completed":
                print(f"  [{i}] {event_type}: summary={str(data.get('summary', ''))[:100]}")
            elif event_type == "task_failed":
                print(f"  [{i}] {event_type}: error={data.get('error_message')}")
            else:
                print(f"  [{i}] {event_type}: {str(data)[:100]}")
        else:
            print(f"  [{i}] {event_type}: {str(data)[:100]}")

    print("\n--- 验证 ---")
    checks = {
        "session_started": "session_started" in event_types,
        "task_started": "task_started" in event_types,
        "token_emitted (有AI回复)": "token_emitted" in event_types,
        "task_completed (任务完成)": "task_completed" in event_types,
    }

    tokens = [
        ev.get("data", {}).get("token", "")
        for ev in all_events
        if ev.get("event") == "token_emitted" and isinstance(ev.get("data"), dict)
    ]
    full_reply = "".join(tokens)
    checks["token 内容非空"] = len(full_reply) > 10

    if full_reply:
        print(f"\nAI 完整回复:\n{full_reply[:500]}{'...' if len(full_reply) > 500 else ''}")

    all_pass = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_pass = False

    return all_pass


def main():
    print("=" * 60)
    print("LUI-for-All AI 对话 SSE 采集端到端测试")
    print("=" * 60)

    token = make_token()
    print(f"JWT Token 已生成")

    results = {}
    results["通知流SSE"] = manual_test_notification_sse(token)
    results["告警流SSE"] = manual_test_alerts_sse(token)

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {name}")

    all_pass = all(results.values())
    print(f"\n总体: {'✅ 全部通过' if all_pass else '❌ 存在失败'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
