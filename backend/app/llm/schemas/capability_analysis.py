"""
建图阶段结构化输出 Schema
精简版：减少字段数量，降低 LLM 输出复杂度，提高解析成功率
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class RouteAnalysis(BaseModel):
    """单条路由分析结果 - 极简平坦结构"""

    route_id: str = Field(description="路由唯一标识，必须与输入 route_id 原样一致，例如 POST:/api/login")
    summary: str = Field(description="一句话功能描述，面向最终用户，20字以内")
    domain: str = Field(
        default="unknown",
        description="业务领域，从以下选择一个: auth, customer, finance, inventory, content, analytics, operations, system, unknown",
    )
    safety_level: str = Field(
        default="readonly_safe",
        description="安全等级，从以下选择一个: readonly_safe, readonly_sensitive, soft_write, hard_write, critical",
    )
    requires_confirmation: bool = Field(
        default=False,
        description="是否必须让用户二次确认才能执行（删除/转账/核心配置修改等危险操作才需要）",
    )
    usage_note: Optional[str] = Field(
        default=None,
        description="调用约束简短说明，如果源码中有特殊校验逻辑才填写，否则留空",
    )


class BatchRouteAnalysisResult(BaseModel):
    """批量分析结果集"""

    analyses: List[RouteAnalysis] = Field(
        description="本次从代码块中分析出的路由列表，只包含在此代码块中找到实现证据的路由"
    )
