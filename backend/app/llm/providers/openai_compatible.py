"""
OpenAI 兼容协议 Provider
- chat_completion: 非流式，仍使用 httpx 直连（简单可靠）
- stream_chat_completion: 使用 agent-matchbox ChatUniversal 流式
  yield 格式: tuple[str, str]
    ("reasoning", token) - reasoning_content 推理内容
    ("token", token)     - 正文 content 内容
"""

import json
import logging
import time
from typing import Any, AsyncGenerator

import httpx
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.config import settings
from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


def _build_langchain_messages(messages: list[dict[str, str]]):
    """将 OpenAI 格式 messages 转换为 LangChain Message 对象列表"""
    lc_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))
    return lc_messages


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI 兼容协议 Provider"""

    def __init__(
        self,
        api_base: str | None = None,
        api_key: str | None = None,
        model_id: str | None = None,
        extra_body: str | None = None,
    ):
        self.api_base = (api_base or settings.llm_api_base).rstrip("/")
        self.api_key = (api_key or settings.llm_api_key).strip()
        self.model_id = (model_id or settings.llm_model_id).strip()
        self.extra_body = extra_body if extra_body is not None else settings.llm_extra_body

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, dict[str, int], int]:
        """非流式对话补全（保留 httpx 直连实现）"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if response_format:
            payload["response_format"] = response_format

        # 解析并注入 extra_body
        if self.extra_body:
            try:
                extra_data = json.loads(self.extra_body)
                if isinstance(extra_data, dict):
                    payload.update(extra_data)
            except Exception:
                pass

        start_time = time.time()
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        elapsed_ms = int((time.time() - start_time) * 1000)
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return content, usage, elapsed_ms

    async def stream_chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        """
        流式对话补全，使用 agent-matchbox 的 ChatUniversal 以正确处理 reasoning_content。

        Yields: tuple[str, str]
            ("reasoning", token) - 推理内容（来自 reasoning_content / <think> 标签）
            ("token", token)     - 正文内容（来自 content）
        """
        try:
            from app.llm.matchbox_client import get_chat_llm, MATCHBOX_AVAILABLE
            use_matchbox = MATCHBOX_AVAILABLE
        except Exception:
            use_matchbox = False

        if use_matchbox:
            async for item in self._stream_via_matchbox(messages, temperature, max_tokens):
                yield item
        else:
            logger.warning("[stream] matchbox 不可用，回退到 httpx 原生解析")
            async for item in self._stream_via_httpx(messages, temperature, max_tokens):
                yield item

    async def _stream_via_matchbox(
        self,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
    ):
        """使用 agent-matchbox ChatUniversal 流式，分离 reasoning 和 content"""
        from app.llm.matchbox_client import get_chat_llm, MessageEventStreamReasoningAdapter

        # 解析 extra_body
        extra_body_dict: dict[str, Any] = {}
        if self.extra_body:
            try:
                extra_body_dict = json.loads(self.extra_body)
            except Exception:
                pass

        try:
            llm = get_chat_llm(
                api_base=self.api_base,
                api_key=self.api_key,
                model_name=self.model_id,
                temperature=temperature,
                extra_body=extra_body_dict or None,
            )
        except Exception as e:
            logger.error(f"[matchbox] 获取 ChatUniversal 失败: {e}，回退到 httpx")
            async for item in self._stream_via_httpx(messages, temperature, max_tokens):
                yield item
            return

        lc_messages = _build_langchain_messages(messages)
        adapter = MessageEventStreamReasoningAdapter()

        # 追加 max_tokens（如有）
        invoke_kwargs: dict[str, Any] = {}
        if max_tokens:
            invoke_kwargs["max_tokens"] = max_tokens

        try:
            async for chunk in llm.astream(lc_messages, **invoke_kwargs):
                reasoning, visible = adapter.push_message(chunk)
                if reasoning:
                    yield ("reasoning", reasoning)
                if visible:
                    yield ("token", visible)

            # flush 收尾（可能有延迟的 think 标签）
            reasoning, visible = adapter.flush()
            if reasoning:
                yield ("reasoning", reasoning)
            if visible:
                yield ("token", visible)

        except Exception as e:
            logger.error(f"[matchbox] 流式调用失败: {e}，回退到 httpx")
            async for item in self._stream_via_httpx(messages, temperature, max_tokens):
                yield item

    async def _stream_via_httpx(
        self,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
    ):
        """httpx 原生 SSE 解析（fallback），只 yield ('token', text)"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens:
            payload["max_tokens"] = max_tokens

        if self.extra_body:
            try:
                extra_data = json.loads(self.extra_body)
                if isinstance(extra_data, dict):
                    payload.update(extra_data)
            except Exception:
                pass

        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream(
                "POST",
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        continue
                    clean_line = line.strip()
                    if clean_line.startswith("data: "):
                        data_str = clean_line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            # 尝试 reasoning_content（兜底）
                            reasoning = delta.get("reasoning_content", "")
                            if reasoning:
                                yield ("reasoning", reasoning)
                            content_text = delta.get("content", "")
                            if content_text:
                                yield ("token", content_text)
                        except Exception:
                            continue
                    elif clean_line.startswith(":"):
                        continue
