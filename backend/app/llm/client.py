"""
LLM 客户端
基于 Matchbox 体系封装结构化调用
"""

import json
import re
from typing import Any

from pydantic import BaseModel

from app.llm.agent_matchbox import matchbox
from app.llm.agent_matchbox.reasoning_compat import extract_reasoning_text_from_message


class LLMClient:
    """LLM 客户端"""

    def __init__(self, provider=None):
        self.provider = provider

    def _get_llm(self, usage_key="main"):
        # 由于网关可以处理系统配置，传入 user_id="-1" 获取内置默认模型
        # 若需要支持多路大模型，可扩展传入不同的 usage_key，此处业务逻辑统一为 main 通道
        return matchbox().get_user_llm(user_id="-1", usage_key=usage_key)

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, dict[str, int], int]:
        llm = self._get_llm(usage_key="main")
        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if response_format:
            kwargs["model_kwargs"] = {"response_format": response_format}

        response = await llm.ainvoke(messages, **kwargs)

        content = response.content if isinstance(response.content, str) else str(response.content)
        token_usage = {}
        if hasattr(response, "response_metadata") and "token_usage" in response.response_metadata:
            token_usage = response.response_metadata["token_usage"]

        return content, token_usage, 200

    async def stream_chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        """
        流式对话补全。
        Yields: tuple[str, str]
            ("reasoning", token) - 推理内容（来自 reasoning_content / <think> 标签）
            ("token", token)     - 正文内容
        """
        llm = self._get_llm(usage_key="main")
        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        async for chunk in llm.astream(messages, **kwargs):
            reasoning_text = extract_reasoning_text_from_message(chunk)
            if reasoning_text:
                yield "reasoning", reasoning_text

            content = chunk.content
            if isinstance(content, str) and content:
                yield "token", content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        yield "token", block.get("text", "")

    @staticmethod
    def _try_repair_json(content: str) -> dict | list | None:
        """
        多策略 JSON 修复：
        1. 剥离 markdown 代码块包装
        2. 尝试直接解析
        3. 截断至最后一个完整对象
        4. 提取第一个完整的 {...} 块
        """
        stripped = re.sub(r"^```(?:json)?\s*", "", content.strip())
        stripped = re.sub(r"\s*```$", "", stripped)

        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        for end_char in ['}', ']']:
            last_pos = stripped.rfind(end_char)
            while last_pos > 0:
                try:
                    return json.loads(stripped[:last_pos + 1])
                except json.JSONDecodeError:
                    last_pos = stripped.rfind(end_char, 0, last_pos)

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

        repaired = self._try_repair_json(content)
        if repaired is not None:
            try:
                return schema.model_validate(repaired)
            except Exception as e:
                raise ValueError(f"解析 LLM 响应失败: {e}\n修复后内容: {repaired}")

        raise ValueError(f"LLM 响应无法修复为有效 JSON\n响应内容(前500字): {content[:500]}")

    async def stream_parse_json_response(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        on_token: Any = None,  # 回调函数: (token: str) -> None
        on_reasoning: Any = None,  # 回调函数: (token: str) -> None
        temperature: float | None = None,
    ) -> BaseModel:
        """
        流式解析 JSON 响应。
        on_token: 正文 token 回调
        on_reasoning: 推理内容 token 回调（可选）
        """
        system_prompt = """你是一个结构化数据提取助手。
请严格按照指定的 JSON Schema 格式输出，不要添加任何额外的文本或解释。
输出必须是有效的 JSON 格式，不要包含 markdown 代码块标记。"""

        full_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        full_content = ""
        async for chunk_type, token in self.stream_chat_completion(
            full_messages,
            temperature=temperature,
        ):
            if chunk_type == "reasoning":
                if on_reasoning:
                    await on_reasoning(token)
            else:
                full_content += token
                if on_token:
                    await on_token(token)

        repaired = self._try_repair_json(full_content)
        if repaired is not None:
            try:
                return schema.model_validate(repaired)
            except Exception as e:
                raise ValueError(f"流式解析失败: {e}\n修复后内容: {repaired}")

        raise ValueError(f"流式响应无法解析为 JSON: {full_content[:500]}")

    async def simple_completion(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
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

    async def stream_simple_completion(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        """
        流式简单完成。
        Yields: tuple[str, str] - ("reasoning"|"token", text)
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        async for chunk in self.stream_chat_completion(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk


llm_client = LLMClient()
