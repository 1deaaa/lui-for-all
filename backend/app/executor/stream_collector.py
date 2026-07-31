"""
流式 HTTP 采集器
支持 SSE（Server-Sent Events）和分页追加型接口的数据采集，
按策略自动停止并返回压缩后的汇总结果。
"""

import json
import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ==================== 采集结果 ====================

class StreamCollectResult(BaseModel):
    """流式采集结果"""

    status: str = Field(
        description="采集状态: collected(正常完成) / timeout(超时) / error(异常)"
    )
    events_count: int = Field(description="采集到的事件/条目数")
    duration_ms: int = Field(description="实际采集耗时（毫秒）")
    events: list[dict[str, Any]] = Field(description="采集到的事件列表（可能被采样）")
    summary: dict[str, Any] = Field(
        default_factory=dict,
        description="汇总统计（字段分布、值域等）",
    )
    sample_ratio: float = Field(
        default=1.0,
        description="采样率（1.0=未采样，0.5=半采样）",
    )


# ==================== 采集器 ====================

class StreamHTTPCollector:
    """流式 HTTP 采集器"""

    # 系统硬限制（AI 无法覆盖）
    MAX_DURATION = 60  # 最大采集秒数
    MAX_EVENTS = 500  # 最大事件数
    MAX_EVENT_SIZE = 4096  # 单事件最大字节
    MAX_RESULT_SIZE = 32000  # 总结果最大字节（JSON 序列化后）
    SSE_TIMEOUT_BUFFER = 5  # SSE 连接超时缓冲秒数

    # ── SSE 采集 ──

    async def collect_sse(
        self,
        url: str,
        headers: dict[str, str],
        strategy: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> StreamCollectResult:
        """
        连接 SSE 端点，按策略采集事件。

        策略 mode:
        - time_window: 采集固定时长 (duration_seconds)
        - event_count: 采集到指定数量后停止 (max_events)
        - snapshot: 取首个数据帧即断开
        """
        mode = strategy.get("mode", "time_window")
        max_duration = min(
            strategy.get("duration_seconds", 10), self.MAX_DURATION
        )
        max_events = min(
            strategy.get("max_events", 100), self.MAX_EVENTS
        )

        events: list[dict[str, Any]] = []
        start = time.monotonic()
        status = "collected"

        try:
            async with httpx.AsyncClient(
                timeout=max_duration + self.SSE_TIMEOUT_BUFFER
            ) as client:
                async with client.stream(
                    "GET", url, headers=headers, params=params
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        # 解析 SSE 行
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                break
                            event = self._parse_sse_data(data_str)
                            if event is not None:
                                events.append(event)

                                # 策略检查
                                if mode == "snapshot":
                                    break
                                if len(events) >= max_events:
                                    break
                                if time.monotonic() - start >= max_duration:
                                    status = "timeout"
                                    break

                        # 也处理 SSE event: 行（忽略 event name，只取 data）
                        elif line.startswith("event:") or line.startswith("id:") or line.startswith("retry:") or line.strip() == "":
                            continue

        except httpx.TimeoutException:
            status = "timeout"
            logger.info(f"[stream_collector] SSE 采集超时: {url}")
        except Exception as exc:
            status = "error"
            logger.error(f"[stream_collector] SSE 采集异常: {exc}", exc_info=True)

        duration_ms = int((time.monotonic() - start) * 1000)

        # 结果压缩
        events, sample_ratio = self._compress_events(events)

        return StreamCollectResult(
            status=status,
            events_count=len(events),
            duration_ms=duration_ms,
            events=events,
            summary=self._build_summary(events),
            sample_ratio=sample_ratio,
        )

    # ── 分页采集 ──

    async def collect_paginated(
        self,
        url: str,
        headers: dict[str, str],
        strategy: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> StreamCollectResult:
        """
        对分页追加型接口执行多次请求，自动翻页直到策略满足。

        策略参数:
        - max_pages: 最大翻页数（默认5，上限20）
        - max_items: 最大条目数（默认100，上限500）
        - timeout_seconds: 总超时（默认30，上限120）
        """
        max_pages = min(strategy.get("max_pages", 5), 20)
        max_items = min(strategy.get("max_items", 100), self.MAX_EVENTS)
        timeout_seconds = min(strategy.get("timeout_seconds", 30), 120)

        all_items: list[dict[str, Any]] = []
        start = time.monotonic()
        status = "collected"
        cursor = None
        # 偏移分页状态
        page_num = None  # 当前页码（从响应体推断）
        page_size_param = None  # 每页条数参数名
        page_param = None  # 页码参数名

        for page_idx in range(max_pages):
            if time.monotonic() - start >= timeout_seconds:
                status = "timeout"
                break

            req_params = dict(params or {})

            # 游标分页：注入 cursor 参数
            if cursor:
                req_params.setdefault("cursor", cursor)

            # 偏移分页：注入 page 参数
            if page_num is not None and page_param:
                req_params[page_param] = page_num

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(url, headers=headers, params=req_params)

                if resp.status_code >= 400:
                    logger.warning(
                        f"[stream_collector] 分页请求失败: status={resp.status_code}"
                    )
                    break

                body = resp.json()
            except Exception as exc:
                logger.error(f"[stream_collector] 分页请求异常: {exc}")
                break

            # 从响应体中提取条目列表
            items = self._extract_page_items(body)
            if not items:
                break

            all_items.extend(items)

            # 首次请求：探测分页模式
            if page_idx == 0 and cursor is None and page_num is None:
                cursor = self._extract_next_cursor(body)
                if not cursor:
                    # 无游标 → 尝试偏移分页
                    page_num, page_param, page_size_param = self._detect_offset_pagination(body, req_params)

            # 游标分页：提取下一页游标
            if cursor is not None and page_num is None:
                cursor = self._extract_next_cursor(body)
                if not cursor:
                    break
            # 偏移分页：递增页码
            elif page_num is not None:
                has_next = self._extract_has_next_page(body)
                if not has_next:
                    break
                page_num += 1
            else:
                break

            if len(all_items) >= max_items:
                all_items = all_items[:max_items]
                break

        duration_ms = int((time.monotonic() - start) * 1000)

        # 结果压缩
        all_items, sample_ratio = self._compress_events(all_items)

        return StreamCollectResult(
            status=status,
            events_count=len(all_items),
            duration_ms=duration_ms,
            events=all_items,
            summary=self._build_summary(all_items),
            sample_ratio=sample_ratio,
        )

    # ── 内部方法 ──

    def _parse_sse_data(self, data_str: str) -> dict[str, Any] | None:
        """解析 SSE data 行为 JSON，失败则包装为 raw"""
        if not data_str:
            return None
        try:
            event = json.loads(data_str)
            if not isinstance(event, dict):
                event = {"value": event}
            # 单事件大小限制
            event_str = json.dumps(event, ensure_ascii=False)
            if len(event_str) > self.MAX_EVENT_SIZE:
                event = {"_truncated": event_str[: self.MAX_EVENT_SIZE]}
            return event
        except json.JSONDecodeError:
            return {"raw": data_str[: self.MAX_EVENT_SIZE]}

    def _compress_events(
        self, events: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], float]:
        """
        压缩事件列表：超出 MAX_RESULT_SIZE 时均匀采样 + 保留首尾。
        返回 (压缩后列表, 采样率)。
        """
        if not events:
            return events, 1.0

        result_str = json.dumps(events, ensure_ascii=False)
        if len(result_str) <= self.MAX_RESULT_SIZE:
            return events, 1.0

        # 需要采样：保留首尾，中间均匀采样
        target_size = self.MAX_RESULT_SIZE - 2000  # 留余量给首尾
        keep_head = min(5, len(events))
        keep_tail = min(5, len(events))
        middle_events = events[keep_head : len(events) - keep_tail]

        # 估算中间部分需要保留多少条
        avg_event_size = len(result_str) / len(events)
        middle_budget = target_size / avg_event_size
        keep_middle = max(1, int(middle_budget))

        # 均匀采样中间部分
        step = max(1, len(middle_events) // keep_middle)
        sampled_middle = middle_events[::step][:keep_middle]

        compressed = events[:keep_head] + sampled_middle + events[-keep_tail:]
        sample_ratio = len(compressed) / len(events)

        logger.info(
            f"[stream_collector] 结果压缩: {len(events)} → {len(compressed)} 条 "
            f"(采样率 {sample_ratio:.2f})"
        )
        return compressed, round(sample_ratio, 2)

    def _build_summary(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """生成事件汇总统计"""
        if not events:
            return {"total": 0}

        summary: dict[str, Any] = {"total": len(events)}

        # 采集所有顶层键
        all_keys: set[str] = set()
        for ev in events:
            if isinstance(ev, dict):
                all_keys.update(ev.keys())

        # 对每个键做简单统计
        for key in list(all_keys)[:10]:  # 最多统计10个键
            values = [ev.get(key) for ev in events if isinstance(ev, dict) and key in ev]
            if not values:
                continue

            # 数值型：统计 min/max/avg
            numeric_values = [v for v in values if isinstance(v, (int, float))]
            if numeric_values and len(numeric_values) > len(values) * 0.5:
                summary[key] = {
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "avg": round(sum(numeric_values) / len(numeric_values), 2),
                    "count": len(numeric_values),
                }
            else:
                # 枚举型：统计唯一值
                unique = set(str(v) for v in values[:100])
                if len(unique) <= 20:
                    summary[key] = {"unique_values": list(unique), "count": len(values)}
                else:
                    summary[key] = {
                        "unique_count": len(unique),
                        "sample_values": list(unique)[:5],
                        "count": len(values),
                    }

        return summary

    def _extract_page_items(self, body: Any) -> list[dict[str, Any]]:
        """从分页响应体中提取条目列表"""
        if isinstance(body, list):
            return [item for item in body if isinstance(item, dict)]

        if not isinstance(body, dict):
            return []

        # 常见的列表字段名
        for key in ("items", "data", "results", "records", "rows", "content"):
            val = body.get(key)
            if isinstance(val, list):
                return [item for item in val if isinstance(item, dict)]

        # 嵌套结构：data.items / data.list
        data = body.get("data")
        if isinstance(data, dict):
            for key in ("items", "list", "results", "records"):
                val = data.get(key)
                if isinstance(val, list):
                    return [item for item in val if isinstance(item, dict)]

        return []

    def _extract_next_cursor(self, body: Any) -> str | None:
        """从分页响应体中提取下一页游标"""
        if not isinstance(body, dict):
            return None

        # 常见的游标字段名
        for key in (
            "next_cursor",
            "next_page_token",
            "next_token",
            "cursor",
            "after",
            "next",
            "continuation_token",
            "pagination.next_cursor",
        ):
            val = body.get(key)
            if val:
                return str(val)

        # 嵌套在 pagination / meta / page_info 中
        for section_key in ("pagination", "meta", "page_info", "paging"):
            section = body.get(section_key)
            if isinstance(section, dict):
                for key in ("next_cursor", "next", "cursor", "after"):
                    val = section.get(key)
                    if val:
                        return str(val)

        return None

    def _detect_offset_pagination(
        self, body: Any, req_params: dict[str, Any]
    ) -> tuple[int | None, str | None, str | None]:
        """
        从首次响应体和请求参数中探测偏移分页模式。
        返回 (当前页码, 页码参数名, 每页条数参数名)，无法识别时返回 (None, None, None)。
        """
        if not isinstance(body, dict):
            return None, None, None

        # 从响应体中找当前页码
        current_page = None
        page_param = None
        for key in ("current_page", "page", "page_number", "currentPage", "pageNumber"):
            val = body.get(key)
            if isinstance(val, (int, float)) and val >= 1:
                current_page = int(val)
                # 推断请求参数名
                if key in req_params:
                    page_param = key
                else:
                    # 常见映射
                    page_param = "page"
                break

        if current_page is None:
            return None, None, None

        # 从请求参数中找 page_size 参数
        page_size_param = None
        for key in ("page_size", "pageSize", "per_page", "perPage", "limit", "size"):
            if key in req_params:
                page_size_param = key
                break

        return current_page, page_param, page_size_param

    def _extract_has_next_page(self, body: Any) -> bool:
        """从分页响应体中判断是否有下一页"""
        if not isinstance(body, dict):
            return False

        # 显式标志
        for key in ("has_more", "has_next_page", "more", "hasNext", "has_more_pages"):
            val = body.get(key)
            if val is True:
                return True
            if val is False:
                return False

        # 通过 current_page / total_pages 推断
        current = body.get("current_page") or body.get("page") or body.get("page_number")
        total = body.get("total_pages") or body.get("totalPages") or body.get("last_page")
        if isinstance(current, (int, float)) and isinstance(total, (int, float)):
            return int(current) < int(total)

        # 无法判断时保守返回 False
        return False
