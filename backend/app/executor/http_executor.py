"""
HTTP 执行器
带审计日志和 Trace ID 注入的 HTTP 客户端
"""

import time
import uuid
from typing import Any

import httpx
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from app.config import settings
from app.policy.redaction import default_redactor

# 获取 tracer
tracer = trace.get_tracer(__name__)


class HTTPExecutor:
    """HTTP 执行器"""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        trace_id: str | None = None,
    ):
        self.base_url = base_url or settings.target_base_url
        self.timeout = timeout
        self.trace_id = trace_id
        self.execution_log: list[dict[str, Any]] = []

    def _inject_trace_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """注入 Trace ID 到请求头"""
        result = headers.copy()

        # 注入自定义 Trace ID
        if self.trace_id:
            result["X-Trace-ID"] = self.trace_id
            result["X-Request-ID"] = str(uuid.uuid4())

        # 注入 OpenTelemetry 上下文
        span = trace.get_current_span()
        if span and span.get_span_context().trace_id:
            trace_context = span.get_span_context()
            result["traceparent"] = f"00-{trace_context.trace_id:032x}-{trace_context.span_id:016x}-01"

        return result

    def _log_execution(
        self,
        method: str,
        url: str,
        request_headers: dict[str, str],
        request_body: Any,
        status_code: int,
        response_body: Any,
        duration_ms: int,
        error: str | None = None,
    ):
        """记录执行日志"""
        log_entry = {
            "execution_id": str(uuid.uuid4()),
            "trace_id": self.trace_id,
            "method": method,
            "url": url,
            "request_headers": request_headers,
            "request_body": request_body,
            "status_code": status_code,
            "response_body": response_body,
            "duration_ms": duration_ms,
            "error": error,
        }
        self.execution_log.append(log_entry)

    async def execute(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        redact_response: bool = False,
    ) -> tuple[int, Any, int]:
        """
        执行 HTTP 请求

        Args:
            method: HTTP 方法
            path: 请求路径
            headers: 请求头
            params: 查询参数
            body: 请求体
            redact_response: 是否脱敏响应

        Returns:
            tuple: (状态码, 响应体, 耗时毫秒)
        """
        url = f"{self.base_url.rstrip('/')}{path}"
        request_headers = self._inject_trace_headers(headers or {})

        start_time = time.time()

        with tracer.start_as_current_span(
            f"HTTP {method} {path}",
            kind=trace.SpanKind.CLIENT,
        ) as span:
            span.set_attribute("http.method", method)
            span.set_attribute("http.url", url)
            span.set_attribute("http.target", path)

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=request_headers,
                        params=params,
                        json=body,
                    )

                elapsed_ms = int((time.time() - start_time) * 1000)

                # 解析响应
                try:
                    response_body = response.json()
                except Exception:
                    response_body = response.text

                # 脱敏处理
                if redact_response and isinstance(response_body, dict):
                    response_body = default_redactor.redact_dict(response_body)

                # 记录日志
                self._log_execution(
                    method=method,
                    url=url,
                    request_headers=request_headers,
                    request_body=body,
                    status_code=response.status_code,
                    response_body=response_body,
                    duration_ms=elapsed_ms,
                )

                # 设置 span 状态
                span.set_attribute("http.status_code", response.status_code)
                if response.status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                else:
                    span.set_status(Status(StatusCode.OK))

                return response.status_code, response_body, elapsed_ms

            except Exception as e:
                elapsed_ms = int((time.time() - start_time) * 1000)

                # 记录错误日志
                self._log_execution(
                    method=method,
                    url=url,
                    request_headers=request_headers,
                    request_body=body,
                    status_code=0,
                    response_body=None,
                    duration_ms=elapsed_ms,
                    error=str(e),
                )

                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        redact_response: bool = False,
    ) -> tuple[int, Any, int]:
        """GET 请求"""
        return await self.execute("GET", path, headers, params, None, redact_response)

    async def post(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        redact_response: bool = False,
    ) -> tuple[int, Any, int]:
        """POST 请求"""
        return await self.execute("POST", path, headers, None, body, redact_response)

    async def put(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        redact_response: bool = False,
    ) -> tuple[int, Any, int]:
        """PUT 请求"""
        return await self.execute("PUT", path, headers, None, body, redact_response)

    async def delete(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        redact_response: bool = False,
    ) -> tuple[int, Any, int]:
        """DELETE 请求"""
        return await self.execute("DELETE", path, headers, None, None, redact_response)

    def get_execution_log(self) -> list[dict[str, Any]]:
        """获取执行日志"""
        return self.execution_log

    def clear_execution_log(self):
        """清空执行日志"""
        self.execution_log.clear()


# 便捷函数
async def http_get(
    path: str,
    base_url: str | None = None,
    trace_id: str | None = None,
    **kwargs,
) -> tuple[int, Any, int]:
    """快捷 GET 请求"""
    executor = HTTPExecutor(base_url=base_url, trace_id=trace_id)
    return await executor.get(path, **kwargs)


async def http_post(
    path: str,
    body: dict[str, Any] | None = None,
    base_url: str | None = None,
    trace_id: str | None = None,
    **kwargs,
) -> tuple[int, Any, int]:
    """快捷 POST 请求"""
    executor = HTTPExecutor(base_url=base_url, trace_id=trace_id)
    return await executor.post(path, body, **kwargs)
