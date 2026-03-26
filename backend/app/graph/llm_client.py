"""
兼容层
保留旧路径，内部转发到新的 LLM 抽象层
"""

from app.llm.client import LLMClient, llm_client

__all__ = ["LLMClient", "llm_client"]
