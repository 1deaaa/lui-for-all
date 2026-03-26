"""
OpenAI 兼容协议 Provider
"""

import time
from typing import Any

import httpx

from app.config import settings
from app.llm.base import BaseLLMProvider


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
            import json
            try:
                extra_data = json.loads(self.extra_body)
                if isinstance(extra_data, dict):
                    payload.update(extra_data)
            except Exception:
                # 若解析失败，静默忽略或记录日志。这里简单忽略，以保证主流程能够尝试发送。
                pass

        start_time = time.time()
        # 大模型长文本生成可能耗时超过一分钟，将超时时间放宽至 600s
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
