"""
UI Block Schema
定义固定 Block 与受控 A2UI 组件的数据结构
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class BlockType(str, Enum):
    """UI Block 类型白名单。"""

    TEXT_BLOCK = "text_block"
    METRIC_CARD = "metric_card"
    DATA_TABLE = "data_table"
    ECHART_CARD = "echart_card"
    CONFIRM_PANEL = "confirm_panel"
    FILTER_FORM = "filter_form"
    TIMELINE_CARD = "timeline_card"
    DIFF_CARD = "diff_card"
    A2UI = "a2ui"


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


# ==================== 受控 A2UI / JSON UI ====================


_A2UI_COMPONENT_TYPES = frozenset({"heading", "text", "metric", "table", "status", "button"})
_A2UI_PROP_KEYS = {
    "heading": frozenset({"text", "level"}),
    "text": frozenset({"text", "tone"}),
    "metric": frozenset({"label", "value", "unit", "trend"}),
    "table": frozenset({"columns", "rows"}),
    "status": frozenset({"label", "value", "tone"}),
    "button": frozenset({"label", "variant", "disabled"}),
}
_A2UI_FORBIDDEN_KEYS = frozenset(
    {
        "html",
        "html_content",
        "script",
        "javascript",
        "onclick",
        "on_click",
        "v-html",
        "eval",
        "template",
    }
)


def _reject_executable_values(value: Any) -> None:
    """递归拒绝可能携带脚本或模板的字段。"""
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in _A2UI_FORBIDDEN_KEYS or normalized_key.startswith("on"):
                raise ValueError(f"A2UI 字段 {key} 不允许包含可执行内容")
            _reject_executable_values(item)
    elif isinstance(value, list):
        for item in value:
            _reject_executable_values(item)
    elif isinstance(value, str):
        lowered = value.lower()
        if "<script" in lowered or "javascript:" in lowered or "{{" in value or "}}" in value:
            raise ValueError("A2UI 文本不允许包含脚本或模板表达式")


class A2UIAction(BaseModel):
    """受控动作；动作类型由前端固定映射，不接受函数或 URL。"""

    action_type: Literal["submit", "copy"]
    label: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload(self):
        _reject_executable_values(self.payload)
        return self


class A2UIComponent(BaseModel):
    """A2UI 表面中的声明式组件。"""

    component_id: str = Field(min_length=1, max_length=80)
    component_type: Literal["heading", "text", "metric", "table", "status", "button"]
    props: dict[str, Any] = Field(default_factory=dict)
    actions: list[A2UIAction] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def validate_component(self):
        if self.component_type not in _A2UI_COMPONENT_TYPES:
            raise ValueError(f"不支持的 A2UI 组件类型: {self.component_type}")
        unknown_keys = set(self.props) - _A2UI_PROP_KEYS[self.component_type]
        if unknown_keys:
            raise ValueError(f"A2UI 组件包含未允许的属性: {sorted(unknown_keys)}")
        _reject_executable_values(self.props)
        return self


class A2UIBlock(BaseModel):
    """A2UI 风格的声明式界面；前端只渲染固定组件白名单。"""

    block_type: Literal[BlockType.A2UI] = BlockType.A2UI
    version: Literal["0.1"] = "0.1"
    surface_id: str = Field(min_length=1, max_length=80)
    components: list[A2UIComponent] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_component_ids(self):
        component_ids = [component.component_id for component in self.components]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("A2UI 组件 ID 必须唯一")
        return self


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
    | A2UIBlock
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
    elif block_type == BlockType.A2UI:
        return A2UIBlock(**data)
    else:
        raise ValueError(f"未知的 block_type: {block_type}")
