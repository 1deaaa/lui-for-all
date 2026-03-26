"""
编排运行时事件兼容层
"""

from app.runtime.emitter import RuntimeEventEmitter, get_runtime_emitter

__all__ = ["RuntimeEventEmitter", "get_runtime_emitter"]
