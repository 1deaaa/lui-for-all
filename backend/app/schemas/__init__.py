"""
Schema 模块初始化
"""

from app.schemas.capability import (
    Capability,
    CapabilityGraph,
    Domain,
    EvidenceRef,
    ModalityType,
    PermissionLevel,
    RouteRef,
    SafetyLevel,
)
from app.schemas.event import (
    ApprovalRequiredEvent,
    ErrorEvent,
    EventType,
    SSEEvent,
    SessionStartedEvent,
    TaskProgressEvent,
    UIBlockEmittedEvent,
    format_sse_event,
)
from app.schemas.policy import (
    ExecutionMatrix,
    PermissionClassifierResult,
    PolicyAction,
    PolicyVerdict,
    RedactionRule,
    SafetyClassifierResult,
)
from app.schemas.route_map import (
    HttpMethod,
    ParameterLocation,
    ParameterSchema,
    ResponseSchema,
    RouteInfo,
    RouteMap,
)
from app.schemas.task import (
    ApprovalStatus,
    ExecutionArtifact,
    TaskPlan,
    TaskRun,
    TaskStatus,
    TaskStep,
)
from app.schemas.ui_block import (
    BlockType,
    ConfirmPanel,
    DataTable,
    DiffCard,
    DiffItem,
    EchartCard,
    FilterForm,
    FormField,
    MetricCard,
    MetricItem,
    TableColumn,
    TextBlock,
    TimelineCard,
    TimelineEvent,
    UIBlock,
    parse_ui_block,
)

__all__ = [
    # Capability
    "Capability",
    "CapabilityGraph",
    "Domain",
    "EvidenceRef",
    "ModalityType",
    "PermissionLevel",
    "RouteRef",
    "SafetyLevel",
    # Event
    "ApprovalRequiredEvent",
    "ErrorEvent",
    "EventType",
    "SSEEvent",
    "SessionStartedEvent",
    "TaskProgressEvent",
    "UIBlockEmittedEvent",
    "format_sse_event",
    # Policy
    "ExecutionMatrix",
    "PermissionClassifierResult",
    "PolicyAction",
    "PolicyVerdict",
    "RedactionRule",
    "SafetyClassifierResult",
    # RouteMap
    "HttpMethod",
    "ParameterLocation",
    "ParameterSchema",
    "ResponseSchema",
    "RouteInfo",
    "RouteMap",
    # Task
    "ApprovalStatus",
    "ExecutionArtifact",
    "TaskPlan",
    "TaskRun",
    "TaskStatus",
    "TaskStep",
    # UIBlock
    "BlockType",
    "ConfirmPanel",
    "DataTable",
    "DiffCard",
    "DiffItem",
    "EchartCard",
    "FilterForm",
    "FormField",
    "MetricCard",
    "MetricItem",
    "TableColumn",
    "TextBlock",
    "TimelineCard",
    "TimelineEvent",
    "UIBlock",
    "parse_ui_block",
]
