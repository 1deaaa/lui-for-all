"""
运行时事件发射器
统一封装 LangGraph 自定义流事件写入
"""

import logging
from typing import Any

from langgraph.config import get_stream_writer

logger = logging.getLogger(__name__)


class RuntimeEventEmitter:
    """运行时事件发射器"""

    def emit(self, event: str, **payload: Any):
        """发射运行时事件"""
        try:
            writer = get_stream_writer()
            writer({"event": event, **payload})
        except Exception:
            logger.debug("当前上下文不支持自定义流事件: %s", event)

    def progress(self, node_name: str, progress: float, message: str):
        """发射任务进度事件"""
        self.emit(
            "task_progress",
            node_name=node_name,
            progress=progress,
            message=message,
        )

    def tool_started(
        self,
        tool_name: str,
        title: str,
        detail: str | None = None,
        step_id: str | None = None,
        route_id: str | None = None,
    ):
        """发射工具开始事件"""
        self.emit(
            "tool_started",
            tool_name=tool_name,
            title=title,
            detail=detail,
            step_id=step_id,
            route_id=route_id,
        )

    def tool_completed(
        self,
        tool_name: str,
        title: str,
        detail: str | None = None,
        step_id: str | None = None,
        route_id: str | None = None,
        status_code: int | None = None,
    ):
        """发射工具完成事件"""
        self.emit(
            "tool_completed",
            tool_name=tool_name,
            title=title,
            detail=detail,
            step_id=step_id,
            route_id=route_id,
            status_code=status_code,
        )


runtime_emitter = RuntimeEventEmitter()


def get_runtime_emitter() -> RuntimeEventEmitter:
    """获取运行时事件发射器"""
    return runtime_emitter
