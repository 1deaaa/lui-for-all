"""
UI Block Schema
定义 8 种白名单组件的数据结构
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class BlockType(str, Enum):
    """UI Block 类型 (8 种白名单)"""

    TEXT_BLOCK = "text_block"
    METRIC_CARD = "metric_card"
    DATA_TABLE = "data_table"
    ECHART_CARD = "echart_card"
    CONFIRM_PANEL = "confirm_panel"
    FILTER_FORM = "filter_form"
    TIMELINE_CARD = "timeline_card"
    DIFF_CARD = "diff_card"


# ==================== 各 Block 的具体定义 ====================


class TextBlock(BaseModel):
    """文本块 - 默认文本反馈"""

    block_type: BlockType = Field(default=BlockType.TEXT_BLOCK, frozen=True)
    content: str = Field(description="文本内容")
    format: str = Field(
        default="plain",
        description="格式: plain, markdown",
    )


class MetricItem(BaseModel):
    """指标项"""

    label: str = Field(description="指标标签")
    value: str | int | float = Field(description="指标值")
    unit: str | None = Field(default=None, description="单位")
    trend: str | None = Field(
        default=None,
        description="趋势: up, down, stable",
    )
    trend_value: str | None = Field(default=None, description="趋势值")


class MetricCard(BaseModel):
    """数据面板 - 少量关键指标"""

    block_type: BlockType = Field(default=BlockType.METRIC_CARD, frozen=True)
    title: str | None = Field(default=None, description="标题")
    metrics: list[MetricItem] = Field(default_factory=list, description="指标列表")


class TableColumn(BaseModel):
    """表格列定义"""

    key: str = Field(description="列键")
    label: str = Field(description="列标题")
    width: int | None = Field(default=None, description="列宽")
    sortable: bool = Field(default=False, description="是否可排序")
    type: str = Field(
        default="text",
        description="列类型: text, number, date, link, tag",
    )


class DataTable(BaseModel):
    """可分页数据表"""

    block_type: BlockType = Field(default=BlockType.DATA_TABLE, frozen=True)
    title: str | None = Field(default=None, description="标题")
    columns: list[TableColumn] = Field(default_factory=list, description="列定义")
    rows: list[dict[str, Any]] = Field(default_factory=list, description="数据行")
    total: int = Field(default=0, description="总行数")
    page: int = Field(default=1, description="当前页")
    page_size: int = Field(default=10, description="每页行数")


class EchartCard(BaseModel):
    """ECharts 图表 - 配置驱动"""

    block_type: BlockType = Field(default=BlockType.ECHART_CARD, frozen=True)
    title: str | None = Field(default=None, description="标题")
    chart_type: str = Field(
        description="图表类型: bar, line, pie, scatter, radar, gauge"
    )
    option: dict[str, Any] = Field(
        default_factory=dict,
        description="ECharts option 配置",
    )
    height: int = Field(default=300, description="图表高度 (px)")


class ConfirmPanel(BaseModel):
    """审批放流器 - 需要确认的动作"""

    block_type: BlockType = Field(default=BlockType.CONFIRM_PANEL, frozen=True)
    approval_id: str = Field(description="审批 ID")
    title: str = Field(description="审批标题")
    description: str = Field(description="审批描述")
    action_summary: str = Field(description="动作摘要")
    risk_level: str = Field(description="风险等级")
    details: list[dict[str, Any]] = Field(
        default_factory=list,
        description="详细信息列表",
    )
    timeout_seconds: int = Field(
        default=300,
        description="超时时间 (秒)",
    )


class FormField(BaseModel):
    """表单字段"""

    key: str = Field(description="字段键")
    label: str = Field(description="字段标签")
    type: str = Field(
        description="字段类型: text, number, select, date, datetime, checkbox, radio"
    )
    required: bool = Field(default=False, description="是否必需")
    default: Any | None = Field(default=None, description="默认值")
    options: list[dict[str, str]] | None = Field(
        default=None,
        description="选项列表 (select/radio 使用)",
    )
    placeholder: str | None = Field(default=None, description="占位文本")
    validation: dict[str, Any] | None = Field(default=None, description="验证规则")


class FilterForm(BaseModel):
    """补充参数搜集器"""

    block_type: BlockType = Field(default=BlockType.FILTER_FORM, frozen=True)
    title: str | None = Field(default=None, description="标题")
    description: str | None = Field(default=None, description="描述")
    fields: list[FormField] = Field(default_factory=list, description="字段列表")
    session_id: str = Field(description="会话 ID")
    request_id: str = Field(description="请求 ID")


class TimelineEvent(BaseModel):
    """时间线事件"""

    timestamp: str = Field(description="时间戳 (ISO 格式)")
    title: str = Field(description="事件标题")
    description: str | None = Field(default=None, description="事件描述")
    status: str = Field(
        default="completed",
        description="状态: pending, in_progress, completed, failed",
    )
    icon: str | None = Field(default=None, description="图标名称")


class TimelineCard(BaseModel):
    """事件节点序列与流转"""

    block_type: BlockType = Field(default=BlockType.TIMELINE_CARD, frozen=True)
    title: str | None = Field(default=None, description="标题")
    events: list[TimelineEvent] = Field(default_factory=list, description="事件列表")


class DiffItem(BaseModel):
    """差异项"""

    key: str = Field(description="键")
    old_value: Any = Field(description="旧值")
    new_value: Any = Field(description="新值")
    change_type: str = Field(
        description="变更类型: added, removed, modified",
    )


class DiffCard(BaseModel):
    """对照与变化"""

    block_type: BlockType = Field(default=BlockType.DIFF_CARD, frozen=True)
    title: str | None = Field(default=None, description="标题")
    description: str | None = Field(default=None, description="描述")
    items: list[DiffItem] = Field(default_factory=list, description="差异项列表")


# ==================== UIBlock 联合类型 ====================

UIBlock = (
    TextBlock
    | MetricCard
    | DataTable
    | EchartCard
    | ConfirmPanel
    | FilterForm
    | TimelineCard
    | DiffCard
)


def parse_ui_block(data: dict[str, Any]) -> UIBlock:
    """根据 block_type 解析对应的 UI Block"""
    block_type = data.get("block_type")
    if block_type == BlockType.TEXT_BLOCK:
        return TextBlock(**data)
    elif block_type == BlockType.METRIC_CARD:
        return MetricCard(**data)
    elif block_type == BlockType.DATA_TABLE:
        return DataTable(**data)
    elif block_type == BlockType.ECHART_CARD:
        return EchartCard(**data)
    elif block_type == BlockType.CONFIRM_PANEL:
        return ConfirmPanel(**data)
    elif block_type == BlockType.FILTER_FORM:
        return FilterForm(**data)
    elif block_type == BlockType.TIMELINE_CARD:
        return TimelineCard(**data)
    elif block_type == BlockType.DIFF_CARD:
        return DiffCard(**data)
    else:
        raise ValueError(f"未知的 block_type: {block_type}")
