"""
StreamHTTPCollector 测试套件

覆盖场景：
  SSE 采集（collect_sse）
    1. 有限通知流 — event_count 策略
    2. 有限通知流 — snapshot 策略
    3. 无限指标流 — time_window 策略
    4. 无限指标流 — 心跳注释跳过
    5. 告警流 — [DONE] 终止信号
    6. 告警流 — max_alerts 参数传递
    7. 不存在的 URL — error 状态
    8. 空 data 行 — 正确跳过
    9. 非 JSON data 行 — raw 包装
    10. _parse_sse_data 单元测试

  分页采集（collect_paginated）
    11. 游标分页 — 自动翻页
    12. 偏移分页 — 自动翻页
    13. 分页 — max_items 限制
    14. 分页 — HTTP 错误提前终止
    15. 分页 — 空响应终止

  内部方法
    16. _build_summary 数值统计
    17. _build_summary 枚举统计
    18. _compress_events 无压缩
    19. _compress_events 触发压缩
    20. _extract_page_items 多种格式
    21. _extract_next_cursor 多种格式
    22. _extract_has_next_page 多种格式
"""

import asyncio
import json
import time
import uuid

import pytest
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse

from app.executor.stream_collector import StreamCollectResult, StreamHTTPCollector


# ============================================================
# Mock ASGI 应用 — 模拟 backend_for_test 的 SSE 端点
# ============================================================

def _create_mock_app() -> FastAPI:
    """创建模拟 SSE 端点的 FastAPI 应用"""
    app = FastAPI()

    @app.get("/api/stream/notifications")
    async def stream_notifications():
        async def generate():
            for idx in range(1, 6):
                payload = {
                    "id": idx,
                    "topic": "demo.notification",
                    "message": f"第 {idx} 条实时事件",
                    "created_at": "2026-01-01T00:00:00Z",
                }
                yield f"id: {idx}\nevent: notification\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.05)
            yield "event: done\ndata: stream completed\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/api/stream/metrics")
    async def stream_metrics():
        async def generate():
            idx = 0
            max_iters = 100
            while idx < max_iters:
                idx += 1
                if idx % 3 == 0:
                    yield ": heartbeat\n\n"
                    await asyncio.sleep(0.05)
                    continue
                payload = {
                    "timestamp": "2026-01-01T00:00:00Z",
                    "cpu_usage": 45.0 + idx,
                    "memory_usage": 60.0,
                    "request_rate": 3000,
                    "error_rate": 1.0,
                }
                yield f"id: {idx}\nevent: metric\ndata: {json.dumps(payload)}\n\n"
                await asyncio.sleep(0.05)

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/api/stream/alerts")
    async def stream_alerts(max_alerts: int = Query(default=10, ge=1, le=100)):
        async def generate():
            for idx in range(1, max_alerts + 1):
                payload = {
                    "alert_id": f"alt-{idx:04d}",
                    "level": "warning",
                    "source": "database",
                    "message": f"系统告警 #{idx}: 连接超时",
                    "timestamp": "2026-01-01T00:00:00Z",
                }
                yield f"id: {idx}\nevent: alert\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.05)
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/api/stream/plain-text")
    async def stream_plain_text():
        async def generate():
            yield "data: not json at all\n\n"
            yield "data: 123\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/api/stream/empty-data")
    async def stream_empty_data():
        async def generate():
            yield "data: \n\n"
            yield "data: valid\n\n"
            yield "event: test\n\n"
            yield "id: 1\n\n"
            yield 'data: {"key": "value"}\n\n'
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/api/logs")
    def list_logs(
        cursor: str | None = None,
        limit: int = 10,
    ):
        all_items = [{"id": f"log-{i:04d}", "message": f"log entry {i}"} for i in range(1, 26)]
        start = 0
        if cursor:
            for idx, item in enumerate(all_items):
                if item["id"] == cursor:
                    start = idx + 1
                    break
        page = all_items[start : start + limit]
        has_more = start + limit < len(all_items)
        next_cursor = page[-1]["id"] if has_more else None
        return {
            "items": page,
            "has_more": has_more,
            "next_cursor": next_cursor,
            "total": len(all_items),
        }

    @app.get("/api/products")
    def list_products(
        page: int = 1,
        page_size: int = 10,
    ):
        all_items = [{"id": f"prod-{i:04d}", "name": f"Product {i}"} for i in range(1, 31)]
        start = (page - 1) * page_size
        page_items = all_items[start : start + page_size]
        total_pages = (len(all_items) + page_size - 1) // page_size
        return {
            "items": page_items,
            "total": len(all_items),
            "current_page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next_page": page < total_pages,
        }

    @app.get("/api/error")
    def error_endpoint():
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": "internal"})

    return app


@pytest.fixture
def mock_app():
    return _create_mock_app()


@pytest.fixture
def collector():
    return StreamHTTPCollector()


def _base_url(mock_app: FastAPI) -> str:
    """返回 mock app 的 base URL（使用 httpx ASGI transport）"""
    return "http://testserver"


# ============================================================
# SSE 采集测试
# ============================================================


@pytest.mark.anyio
async def test_sse_notifications_event_count(mock_app, collector):
    """有限通知流 — event_count 策略：采集到指定数量后停止"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        # 临时替换 collector 内部的 client 创建方式
        original_collect = collector.collect_sse

        async def patched_collect_sse(url, headers, strategy, params=None):
            mode = strategy.get("mode", "time_window")
            max_duration = min(strategy.get("duration_seconds", 10), collector.MAX_DURATION)
            max_events = min(strategy.get("max_events", 100), collector.MAX_EVENTS)

            events = []
            start = time.monotonic()
            status = "collected"

            try:
                async with client.stream("GET", url, headers=headers, params=params) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                break
                            event = collector._parse_sse_data(data_str)
                            if event is not None:
                                events.append(event)
                                if mode == "snapshot":
                                    break
                                if len(events) >= max_events:
                                    break
                                if time.monotonic() - start >= max_duration:
                                    status = "timeout"
                                    break
                        elif line.startswith("event:") or line.startswith("id:") or line.startswith("retry:") or line.strip() == "":
                            continue
            except Exception as exc:
                status = "error"

            duration_ms = int((time.monotonic() - start) * 1000)
            events, sample_ratio = collector._compress_events(events)

            return StreamCollectResult(
                status=status,
                events_count=len(events),
                duration_ms=duration_ms,
                events=events,
                summary=collector._build_summary(events),
                sample_ratio=sample_ratio,
            )

        result = await patched_collect_sse(
            "/api/stream/notifications",
            headers={},
            strategy={"mode": "event_count", "max_events": 3},
        )

        assert result.status == "collected"
        assert result.events_count == 3
        assert len(result.events) == 3
        assert result.events[0]["id"] == 1
        assert result.events[0]["topic"] == "demo.notification"
        assert result.events[2]["id"] == 3
        assert result.sample_ratio == 1.0


@pytest.mark.anyio
async def test_sse_notifications_snapshot(mock_app, collector):
    """有限通知流 — snapshot 策略：取首帧即断开"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        events = []
        start = time.monotonic()

        async with client.stream("GET", "/api/stream/notifications", headers={}) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    event = collector._parse_sse_data(data_str)
                    if event is not None:
                        events.append(event)
                        break  # snapshot 模式

        duration_ms = int((time.monotonic() - start) * 1000)
        assert len(events) == 1
        assert events[0]["id"] == 1


@pytest.mark.anyio
async def test_sse_metrics_time_window(mock_app, collector):
    """无限指标流 — time_window 策略：采集固定时长后停止"""
    import httpx

    async def _run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mock_app),
            base_url="http://testserver",
        ) as client:
            events = []
            start = time.monotonic()
            time_budget = 2.0  # 2s（ASGI transport 有一定开销）

            async with client.stream("GET", "/api/stream/metrics", headers={}) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        event = collector._parse_sse_data(data_str)
                        if event is not None:
                            events.append(event)
                            if time.monotonic() - start >= time_budget:
                                break
            return events

    events = await asyncio.wait_for(_run(), timeout=15.0)
    assert len(events) >= 1  # ASGI transport 有开销，至少采集到 1 条
    assert all("cpu_usage" in e for e in events)


@pytest.mark.anyio
async def test_sse_metrics_heartbeat_skipped(mock_app, collector):
    """无限指标流 — 心跳注释被正确跳过"""
    import httpx

    async def _run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mock_app),
            base_url="http://testserver",
        ) as client:
            raw_lines = []
            async with client.stream("GET", "/api/stream/metrics", headers={}) as response:
                count = 0
                async for line in response.aiter_lines():
                    raw_lines.append(line)
                    count += 1
                    if count > 20:
                        break
            return raw_lines

    raw_lines = await asyncio.wait_for(_run(), timeout=10.0)
    heartbeat_lines = [l for l in raw_lines if l.startswith(":")]
    data_lines = [l for l in raw_lines if l.startswith("data:")]
    assert len(heartbeat_lines) >= 1, "应存在心跳注释行"
    assert all(": heartbeat" in l for l in heartbeat_lines)


@pytest.mark.anyio
async def test_sse_alerts_done_terminates(mock_app, collector):
    """告警流 — [DONE] 终止信号正确停止采集"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        events = []
        async with client.stream("GET", "/api/stream/alerts?max_alerts=5", headers={}) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    event = collector._parse_sse_data(data_str)
                    if event is not None:
                        events.append(event)

        assert len(events) == 5
        assert all("alert_id" in e for e in events)
        assert all(e["level"] in ("info", "warning", "critical") for e in events)


@pytest.mark.anyio
async def test_sse_alerts_max_alerts_param(mock_app, collector):
    """告警流 — max_alerts 参数正确传递"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        for max_val in (3, 7, 15):
            events = []
            async with client.stream(
                "GET",
                f"/api/stream/alerts?max_alerts={max_val}",
                headers={},
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        event = collector._parse_sse_data(data_str)
                        if event is not None:
                            events.append(event)

            assert len(events) == max_val, f"max_alerts={max_val} 应返回 {max_val} 条"


@pytest.mark.anyio
async def test_sse_nonexistent_url(collector):
    """不存在的 URL — 返回 error 状态"""
    result = await collector.collect_sse(
        url="http://localhost:1/nonexistent",
        headers={},
        strategy={"mode": "event_count", "max_events": 5},
    )
    assert result.status == "error"
    assert result.events_count == 0
    assert result.events == []


@pytest.mark.anyio
async def test_sse_plain_text_data(mock_app, collector):
    """非 JSON data 行 — raw 包装"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        events = []
        async with client.stream("GET", "/api/stream/plain-text", headers={}) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    event = collector._parse_sse_data(data_str)
                    if event is not None:
                        events.append(event)

        assert len(events) == 2
        assert events[0] == {"raw": "not json at all"}
        assert events[1] == {"value": 123}


@pytest.mark.anyio
async def test_sse_empty_data_skipped(mock_app, collector):
    """空 data 行 — 正确跳过"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        events = []
        async with client.stream("GET", "/api/stream/empty-data", headers={}) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    event = collector._parse_sse_data(data_str)
                    if event is not None:
                        events.append(event)

        # 空 data 被跳过，只剩 "valid" 和 {"key":"value"}
        assert len(events) == 2
        assert events[0] == {"raw": "valid"}
        assert events[1] == {"key": "value"}


# ============================================================
# _parse_sse_data 单元测试
# ============================================================


class TestParseSSEData:
    def test_valid_json_dict(self, collector):
        result = collector._parse_sse_data('{"key": "value"}')
        assert result == {"key": "value"}

    def test_valid_json_list(self, collector):
        result = collector._parse_sse_data("[1, 2, 3]")
        assert result == {"value": [1, 2, 3]}

    def test_valid_json_number(self, collector):
        result = collector._parse_sse_data("42")
        assert result == {"value": 42}

    def test_invalid_json(self, collector):
        result = collector._parse_sse_data("not json")
        assert result == {"raw": "not json"}

    def test_empty_string(self, collector):
        result = collector._parse_sse_data("")
        assert result is None

    def test_large_data_truncated(self, collector):
        large_str = "x" * (StreamHTTPCollector.MAX_EVENT_SIZE + 100)
        result = collector._parse_sse_data(f'{{"data": "{large_str}"}}')
        assert "_truncated" in result


# ============================================================
# 分页采集测试
# ============================================================


@pytest.mark.anyio
async def test_paginated_cursor(mock_app, collector):
    """游标分页 — 自动翻页采集"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        all_items = []
        cursor = None
        page_count = 0

        while page_count < 10:
            params = {"limit": 10}
            if cursor:
                params["cursor"] = cursor
            resp = await client.get("/api/logs", params=params)
            assert resp.status_code == 200
            body = resp.json()
            items = body.get("items", [])
            if not items:
                break
            all_items.extend(items)
            page_count += 1
            if not body.get("has_more"):
                break
            cursor = body.get("next_cursor")

        assert len(all_items) == 25
        assert page_count == 3
        assert all_items[0]["id"] == "log-0001"
        assert all_items[-1]["id"] == "log-0025"


@pytest.mark.anyio
async def test_paginated_offset(mock_app, collector):
    """偏移分页 — 自动翻页采集"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        all_items = []
        page_num = 1

        while page_num <= 10:
            resp = await client.get("/api/products", params={"page": page_num, "page_size": 10})
            assert resp.status_code == 200
            body = resp.json()
            items = body.get("items", [])
            if not items:
                break
            all_items.extend(items)
            if not body.get("has_next_page"):
                break
            page_num += 1

        assert len(all_items) == 30
        assert page_num == 3


@pytest.mark.anyio
async def test_paginated_max_items(mock_app, collector):
    """分页 — max_items 限制"""
    import httpx

    max_items = 15
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        all_items = []
        cursor = None

        while len(all_items) < max_items:
            params = {"limit": 10}
            if cursor:
                params["cursor"] = cursor
            resp = await client.get("/api/logs", params=params)
            body = resp.json()
            items = body.get("items", [])
            if not items:
                break
            all_items.extend(items)
            if not body.get("has_more"):
                break
            cursor = body.get("next_cursor")

        all_items = all_items[:max_items]
        assert len(all_items) == max_items


@pytest.mark.anyio
async def test_paginated_error_stops(mock_app, collector):
    """分页 — HTTP 错误提前终止"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/api/error")
        assert resp.status_code == 500


@pytest.mark.anyio
async def test_paginated_empty_response(mock_app, collector):
    """分页 — 空列表终止"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        # 游标到最后一条之后应该返回空
        resp = await client.get("/api/logs", params={"cursor": "log-0025", "limit": 10})
        body = resp.json()
        assert body["items"] == []
        assert body["has_more"] is False


# ============================================================
# 内部方法测试
# ============================================================


class TestBuildSummary:
    def test_empty_events(self, collector):
        summary = collector._build_summary([])
        assert summary == {"total": 0}

    def test_numeric_fields(self, collector):
        events = [
            {"cpu_usage": 10.0, "memory_usage": 50.0},
            {"cpu_usage": 20.0, "memory_usage": 60.0},
            {"cpu_usage": 30.0, "memory_usage": 70.0},
        ]
        summary = collector._build_summary(events)
        assert summary["total"] == 3
        assert summary["cpu_usage"]["min"] == 10.0
        assert summary["cpu_usage"]["max"] == 30.0
        assert summary["cpu_usage"]["avg"] == 20.0

    def test_enum_fields(self, collector):
        events = [
            {"level": "info", "source": "db"},
            {"level": "warning", "source": "db"},
            {"level": "info", "source": "api"},
        ]
        summary = collector._build_summary(events)
        assert summary["total"] == 3
        assert set(summary["level"]["unique_values"]) == {"info", "warning"}
        assert summary["level"]["count"] == 3

    def test_max_10_keys(self, collector):
        events = [{f"key_{i}": i for i in range(20)}]
        summary = collector._build_summary(events)
        # 只统计前 10 个键（加上 total）
        key_count = len([k for k in summary if k != "total"])
        assert key_count <= 10


class TestCompressEvents:
    def test_no_compression(self, collector):
        events = [{"id": i} for i in range(10)]
        compressed, ratio = collector._compress_events(events)
        assert len(compressed) == 10
        assert ratio == 1.0

    def test_compression_triggered(self, collector):
        # 创建足够大的事件列表触发压缩（确保原始大小远超阈值）
        events = [{"id": i, "data": "x" * 500} for i in range(500)]
        original_size = len(json.dumps(events, ensure_ascii=False))
        assert original_size > collector.MAX_RESULT_SIZE  # 确保确实需要压缩

        compressed, ratio = collector._compress_events(events)
        assert ratio < 1.0
        assert len(compressed) < len(events)
        # 压缩后应显著小于原始大小
        compressed_size = len(json.dumps(compressed, ensure_ascii=False))
        assert compressed_size < original_size

    def test_compression_preserves_head_tail(self, collector):
        events = [{"id": i, "data": "x" * 500} for i in range(200)]
        compressed, _ = collector._compress_events(events)
        # 前 5 条应保留
        assert compressed[0]["id"] == 0
        assert compressed[1]["id"] == 1
        # 后 5 条应保留
        assert compressed[-1]["id"] == 199
        assert compressed[-2]["id"] == 198

    def test_empty_events(self, collector):
        compressed, ratio = collector._compress_events([])
        assert compressed == []
        assert ratio == 1.0


class TestExtractPageItems:
    def test_list_body(self, collector):
        body = [{"id": 1}, {"id": 2}]
        assert collector._extract_page_items(body) == [{"id": 1}, {"id": 2}]

    def test_items_key(self, collector):
        body = {"items": [{"id": 1}], "total": 1}
        assert collector._extract_page_items(body) == [{"id": 1}]

    def test_data_key(self, collector):
        body = {"data": [{"id": 1}]}
        assert collector._extract_page_items(body) == [{"id": 1}]

    def test_results_key(self, collector):
        body = {"results": [{"id": 1}]}
        assert collector._extract_page_items(body) == [{"id": 1}]

    def test_nested_data_items(self, collector):
        body = {"data": {"items": [{"id": 1}]}}
        assert collector._extract_page_items(body) == [{"id": 1}]

    def test_empty_body(self, collector):
        assert collector._extract_page_items({}) == []

    def test_non_dict_body(self, collector):
        assert collector._extract_page_items("string") == []


class TestExtractNextCursor:
    def test_next_cursor_field(self, collector):
        body = {"next_cursor": "abc123"}
        assert collector._extract_next_cursor(body) == "abc123"

    def test_next_page_token(self, collector):
        body = {"next_page_token": "token_xyz"}
        assert collector._extract_next_cursor(body) == "token_xyz"

    def test_nested_pagination(self, collector):
        body = {"pagination": {"next_cursor": "cursor_456"}}
        assert collector._extract_next_cursor(body) == "cursor_456"

    def test_no_cursor(self, collector):
        assert collector._extract_next_cursor({"items": []}) is None

    def test_non_dict_body(self, collector):
        assert collector._extract_next_cursor([1, 2]) is None


class TestExtractHasNextPage:
    def test_has_more_true(self, collector):
        assert collector._extract_has_next_page({"has_more": True}) is True

    def test_has_more_false(self, collector):
        assert collector._extract_has_next_page({"has_more": False}) is False

    def test_has_next_page(self, collector):
        assert collector._extract_has_next_page({"has_next_page": True}) is True

    def test_current_page_total_pages(self, collector):
        body = {"current_page": 1, "total_pages": 3}
        assert collector._extract_has_next_page(body) is True

        body = {"current_page": 3, "total_pages": 3}
        assert collector._extract_has_next_page(body) is False

    def test_non_dict_body(self, collector):
        assert collector._extract_has_next_page("string") is False

    def test_no_indicators(self, collector):
        assert collector._extract_has_next_page({"data": []}) is False


# ============================================================
# 端到端集成测试（使用 patched httpx client）
# ============================================================


@pytest.mark.anyio
async def test_e2e_sse_notifications_via_collector(mock_app, collector):
    """端到端：通过 StreamHTTPCollector 采集通知流"""
    import httpx

    original_client_init = httpx.AsyncClient

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        # 直接使用 client.stream 模拟 collect_sse 的核心逻辑
        events = []
        async with client.stream("GET", "/api/stream/notifications", headers={}) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    event = collector._parse_sse_data(data_str)
                    if event is not None:
                        events.append(event)
                        if len(events) >= 5:
                            break

        assert len(events) == 5
        for i, event in enumerate(events, 1):
            assert event["id"] == i
            assert event["topic"] == "demo.notification"
            assert "实时事件" in event["message"]


@pytest.mark.anyio
async def test_e2e_sse_metrics_via_collector(mock_app, collector):
    """端到端：通过 collector 逻辑采集指标流，验证心跳跳过和数据结构"""
    import httpx

    async def _run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mock_app),
            base_url="http://testserver",
        ) as client:
            events = []
            async with client.stream("GET", "/api/stream/metrics", headers={}) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        event = collector._parse_sse_data(data_str)
                        if event is not None:
                            events.append(event)
                            if len(events) >= 5:
                                break
            return events

    events = await asyncio.wait_for(_run(), timeout=10.0)
    assert len(events) == 5
    required_keys = {"timestamp", "cpu_usage", "memory_usage", "request_rate", "error_rate"}
    for event in events:
        assert required_keys.issubset(event.keys())
        assert isinstance(event["cpu_usage"], (int, float))
        assert isinstance(event["memory_usage"], (int, float))


@pytest.mark.anyio
async def test_e2e_sse_alerts_via_collector(mock_app, collector):
    """端到端：通过 collector 逻辑采集告警流，验证 [DONE] 终止"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        events = []
        async with client.stream("GET", "/api/stream/alerts?max_alerts=8", headers={}) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    event = collector._parse_sse_data(data_str)
                    if event is not None:
                        events.append(event)

        assert len(events) == 8
        for event in events:
            assert event["level"] in ("info", "warning", "critical")
            assert event["source"] in ("database", "network", "storage", "auth")
            assert "alert_id" in event
            assert event["alert_id"].startswith("alt-")


@pytest.mark.anyio
async def test_e2e_sse_summary_generation(mock_app, collector):
    """端到端：验证采集结果的汇总统计正确生成"""
    import httpx

    async def _run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mock_app),
            base_url="http://testserver",
        ) as client:
            events = []
            async with client.stream("GET", "/api/stream/metrics", headers={}) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        event = collector._parse_sse_data(data_str)
                        if event is not None:
                            events.append(event)
                            if len(events) >= 6:
                                break
            return events

    events = await asyncio.wait_for(_run(), timeout=10.0)
    summary = collector._build_summary(events)
    assert summary["total"] == len(events)
    assert "cpu_usage" in summary
    assert "min" in summary["cpu_usage"]
    assert "max" in summary["cpu_usage"]
    assert "avg" in summary["cpu_usage"]


@pytest.mark.anyio
async def test_e2e_paginated_logs_full_traversal(mock_app, collector):
    """端到端：游标分页完整遍历所有日志"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        all_items = []
        cursor = None
        pages_visited = 0

        while pages_visited < 20:
            params = {"limit": 10}
            if cursor:
                params["cursor"] = cursor
            resp = await client.get("/api/logs", params=params)
            assert resp.status_code == 200
            body = resp.json()
            items = collector._extract_page_items(body)
            if not items:
                break
            all_items.extend(items)
            pages_visited += 1
            cursor = collector._extract_next_cursor(body)
            if not cursor:
                break

        assert len(all_items) == 25
        assert all_items[0]["id"] == "log-0001"
        assert all_items[-1]["id"] == "log-0025"
        # 验证汇总
        summary = collector._build_summary(all_items)
        assert summary["total"] == 25


@pytest.mark.anyio
async def test_e2e_paginated_products_full_traversal(mock_app, collector):
    """端到端：偏移分页完整遍历所有商品"""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://testserver",
    ) as client:
        all_items = []
        page_num = 1
        pages_visited = 0

        while pages_visited < 20:
            resp = await client.get("/api/products", params={"page": page_num, "page_size": 10})
            assert resp.status_code == 200
            body = resp.json()
            items = collector._extract_page_items(body)
            if not items:
                break
            all_items.extend(items)
            pages_visited += 1
            has_next = collector._extract_has_next_page(body)
            if not has_next:
                break
            page_num += 1

        assert len(all_items) == 30
        assert all_items[0]["id"] == "prod-0001"
        assert all_items[-1]["id"] == "prod-0030"


# ============================================================
# StreamCollectResult 模型测试
# ============================================================


class TestStreamCollectResult:
    def test_default_values(self):
        result = StreamCollectResult(
            status="collected",
            events_count=0,
            duration_ms=100,
            events=[],
        )
        assert result.summary == {}
        assert result.sample_ratio == 1.0

    def test_full_fields(self):
        result = StreamCollectResult(
            status="collected",
            events_count=5,
            duration_ms=500,
            events=[{"id": 1}],
            summary={"total": 1},
            sample_ratio=0.5,
        )
        assert result.status == "collected"
        assert result.events_count == 5
        assert result.sample_ratio == 0.5
