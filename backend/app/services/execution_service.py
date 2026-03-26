"""
执行服务
统一收口 HTTP 执行、认证接力、运行时事件与执行产物组装
"""

import logging
import uuid
from typing import Any

from app.executor.http_executor import HTTPExecutor
from app.runtime.emitter import RuntimeEventEmitter, get_runtime_emitter
from app.schemas.policy import PolicyAction, PolicyVerdict
from app.schemas.task import ExecutionArtifact, TaskPlan
from app.services.auth_session_service import AuthSessionService

logger = logging.getLogger(__name__)


class ExecutionService:
    """统一执行服务"""

    def __init__(
        self,
        base_url: str,
        trace_id: str | None = None,
        emitter: RuntimeEventEmitter | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.trace_id = trace_id
        self.emitter = emitter or get_runtime_emitter()
        self.auth_session = AuthSessionService()
        self.http_executor = HTTPExecutor(base_url=self.base_url, trace_id=trace_id)

    @staticmethod
    def parse_route(route_id: str) -> tuple[str, str]:
        """解析 route_id 为 method 与 path"""
        route_parts = route_id.split(":", 1)
        if len(route_parts) == 2:
            return route_parts[0].strip(), route_parts[1].strip()
        return "GET", route_id

    async def execute_plan(
        self,
        plan: TaskPlan,
        verdicts: list[PolicyVerdict],
    ) -> list[ExecutionArtifact]:
        """执行整个任务计划"""
        artifacts: list[ExecutionArtifact] = []

        for index, step in enumerate(plan.steps):
            logger.info("[ExecutionService] Step %s: %s", index + 1, step.route_id)
            self.emitter.tool_started(
                tool_name="http_request",
                title=f"开始调用 {step.route_id}",
                detail=step.action,
                step_id=step.step_id,
                route_id=step.route_id,
            )
            self.emitter.progress(
                node_name="execute_requests",
                progress=min(0.86, 0.68 + ((index + 1) / max(len(plan.steps), 1)) * 0.18),
                message=f"正在执行第 {index + 1}/{len(plan.steps)} 个接口调用",
            )

            verdict = next((v for v in verdicts if v.route_id == step.route_id), None)
            if verdict and verdict.action == PolicyAction.BLOCK:
                self.emitter.tool_completed(
                    tool_name="http_request",
                    title=f"已阻断 {step.route_id}",
                    detail="该步骤被安全策略阻断",
                    step_id=step.step_id,
                    route_id=step.route_id,
                    status_code=None,
                )
                continue

            method, path = self.parse_route(step.route_id)
            headers = self.auth_session.build_headers({"Content-Type": "application/json"})

            try:
                status_code, response_body, duration_ms = await self.http_executor.execute(
                    method=method,
                    path=path if path.startswith("/") else f"/{path}",
                    headers=headers,
                    params=step.parameters if method == "GET" else None,
                    body=step.parameters if method in ["POST", "PUT", "PATCH"] else None,
                    redact_response=bool(verdict and verdict.action == PolicyAction.REDACT),
                )
                self.auth_session.capture_token(response_body)

                artifact = ExecutionArtifact(
                    artifact_id=str(uuid.uuid4()),
                    step_id=step.step_id,
                    route_id=step.route_id,
                    method=method,
                    url=f"{self.base_url}{path if path.startswith('/') else '/' + path}",
                    request_headers={"Authorization": "***REDACTED***"} if self.auth_session.token else {},
                    request_body=step.parameters,
                    status_code=status_code,
                    response_body=response_body if isinstance(response_body, dict) else {"text": str(response_body)},
                    duration_ms=duration_ms,
                    redacted=bool(verdict and verdict.action == PolicyAction.REDACT),
                    error=None,
                )
                self.emitter.tool_completed(
                    tool_name="http_request",
                    title=f"完成调用 {step.route_id}",
                    detail=f"HTTP {status_code}",
                    step_id=step.step_id,
                    route_id=step.route_id,
                    status_code=status_code,
                )
            except Exception as exc:
                artifact = ExecutionArtifact(
                    artifact_id=str(uuid.uuid4()),
                    step_id=step.step_id,
                    route_id=step.route_id,
                    method=method,
                    url=f"{self.base_url}{path if path.startswith('/') else '/' + path}",
                    request_headers={},
                    request_body=step.parameters,
                    status_code=0,
                    response_body={},
                    duration_ms=0,
                    redacted=False,
                    error=str(exc),
                )
                self.emitter.tool_completed(
                    tool_name="http_request",
                    title=f"调用失败 {step.route_id}",
                    detail=str(exc),
                    step_id=step.step_id,
                    route_id=step.route_id,
                    status_code=0,
                )

            artifacts.append(artifact)

        return artifacts
