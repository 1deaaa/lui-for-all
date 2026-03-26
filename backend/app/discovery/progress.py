"""
发现进度定义
"""

from typing import Awaitable, Callable

ProgressCallback = Callable[[int, str], Awaitable[None]]

__all__ = ["ProgressCallback"]
