"""
LLM Provider 抽象基类
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """LLM Provider 抽象基类"""

    @abstractmethod
    async def chat_completion(
        self,
        response_format: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, dict[str, int], int]:
        """执行对话补全"""
