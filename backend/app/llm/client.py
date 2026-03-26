"""
LLM 客户端
基于 Provider 体系封装结构化调用
"""

import json
import re
from typing import Any

from pydantic import BaseModel

from app.llm.providers.openai_compatible import OpenAICompatibleProvider


class LLMClient:
    """LLM 客户端"""

    def __init__(self, provider: OpenAICompatibleProvider | None = None):
        self.provider = provider or OpenAICompatibleProvider()

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, dict[str, int], int]:
        return await self.provider.chat_completion(
            messages=messages,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    @staticmethod
    def _try_repair_json(content: str) -> dict | list | None:
        """
        多策略 JSON 修复：
        1. 剥离 markdown 代码块包装
        2. 尝试直接解析
        3. 截断至最后一个完整对象
        4. 提取第一个完整的 {...} 块
        """
        # 策略0：剥离 markdown 代码块
        stripped = re.sub(r"^```(?:json)?\s*", "", content.strip())
        stripped = re.sub(r"\s*```$", "", stripped)

        # 策略1：直接解析
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # 策略2：截断至最后一个能正常完成的 "}" 或 "]"
        # 从末尾开始向前找最后一个能解析的位置
        for end_char in ['}', ']']:
            last_pos = stripped.rfind(end_char)
            while last_pos > 0:
                try:
                    return json.loads(stripped[:last_pos + 1])
                except json.JSONDecodeError:
                    last_pos = stripped.rfind(end_char, 0, last_pos)

        # 策略3: 提取最外层的 {...} 块
        match = re.search(r'\{.*\}', stripped, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

    async def parse_json_response(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        temperature: float | None = None,
    ) -> BaseModel:
        system_prompt = """你是一个结构化数据提取助手。
请严格按照指定的 JSON Schema 格式输出，不要添加任何额外的文本或解释。
输出必须是有效的 JSON 格式，不要包含 markdown 代码块标记。"""

        full_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        content, _, _ = await self.chat_completion(
            full_messages,
            response_format={"type": "json_object"},
            temperature=temperature,
        )

        # 优先尝试修复，再抛异常
        repaired = self._try_repair_json(content)
        if repaired is not None:
            try:
                return schema.model_validate(repaired)
            except Exception as e:
                raise ValueError(f"解析 LLM 响应失败: {e}\n修复后内容: {repaired}")

        raise ValueError(f"LLM 响应无法修复为有效 JSON\n响应内容(前500字): {content[:500]}")

    async def simple_completion(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,  # 由 2000 改为不限 (None)，交由模型决定或调用处指定
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        content, _, _ = await self.chat_completion(
            messages, 
            temperature=temperature, 
            max_tokens=max_tokens
        )
        return content


llm_client = LLMClient()
