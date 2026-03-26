"""
审计服务
统一写入模型调用、HTTP 执行与策略判定记录
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import HttpExecution, ModelCall, PolicyVerdictRecord
from app.schemas.policy import PolicyVerdict


class AuditService:
    """统一审计服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_policy_verdicts(
        self,
        task_run_id: str,
        session_id: str,
        verdicts: list[PolicyVerdict],
    ):
        for verdict in verdicts:
            self.db.add(
                PolicyVerdictRecord(
                    id=str(uuid.uuid4()),
                    task_run_id=task_run_id,
                    session_id=session_id,
                    route_id=verdict.route_id,
                    capability_id=verdict.capability_id,
                    action=verdict.action.value,
                    safety_level=verdict.safety_level.value,
                    permission_level=verdict.permission_level.value,
                    reasons=verdict.reasons,
                    evidence=verdict.evidence,
                    redaction_fields=verdict.redaction_fields,
                )
            )

    async def record_http_execution(
        self,
        session_id: str,
        task_run_id: str,
        trace_id: str,
        payload: dict[str, Any],
    ):
        self.db.add(
            HttpExecution(
                id=str(uuid.uuid4()),
                request_id=str(uuid.uuid4()),
                session_id=session_id,
                task_run_id=task_run_id,
                capability_id=payload.get("capability_id"),
                method=payload.get("method", "GET"),
                url_redacted=payload.get("url", ""),
                headers_redacted=payload.get("request_headers", {}),
                request_body_redacted=payload.get("request_body"),
                status_code=payload.get("status_code"),
                response_body_redacted=payload.get("response_body"),
                duration_ms=payload.get("duration_ms"),
                trace_id=trace_id,
                policy_snapshot=payload.get("policy_snapshot", {}),
                error=payload.get("error"),
            )
        )

    async def record_model_call(
        self,
        task_run_id: str,
        trace_id: str,
        provider: str,
        model_name: str,
        latency_ms: int,
        token_usage: dict[str, int] | None = None,
        prompt_template_name: str | None = None,
    ):
        self.db.add(
            ModelCall(
                id=str(uuid.uuid4()),
                task_run_id=task_run_id,
                trace_id=trace_id,
                provider=provider,
                model_name=model_name,
                prompt_template_name=prompt_template_name,
                latency_ms=latency_ms,
                token_usage=token_usage or {},
            )
        )
