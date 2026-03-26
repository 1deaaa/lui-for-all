"""
策略服务
统一收口计划级安全判定逻辑
"""

import uuid

from app.policy.execution_matrix import get_action
from app.schemas.policy import PolicyVerdict
from app.schemas.task import TaskPlan


class PolicyService:
    """策略判定服务"""

    def evaluate_plan(self, plan: TaskPlan) -> list[PolicyVerdict]:
        """对整个计划生成策略判定"""
        verdicts: list[PolicyVerdict] = []

        for step in plan.steps:
            safety_level = step.safety_level
            action = get_action(safety_level)
            verdicts.append(
                PolicyVerdict(
                    verdict_id=str(uuid.uuid4()),
                    route_id=step.route_id,
                    capability_id=step.capability_id,
                    action=action,
                    safety_level=safety_level,
                    permission_level="authenticated",
                    reasons=[f"安全等级为 {safety_level}"],
                    evidence={},
                    redaction_fields=[],
                    approval_timeout_seconds=300,
                    approval_message=f"此操作需要确认: {step.action}",
                    block_reason=None if action != "block" else "操作被安全策略阻断",
                )
            )

        return verdicts
