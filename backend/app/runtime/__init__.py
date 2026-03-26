"""
运行时协议层
统一封装运行时事件发射与协议常量
"""

from app.runtime.emitter import RuntimeEventEmitter, get_runtime_emitter

__all__ = ["RuntimeEventEmitter", "get_runtime_emitter"]
