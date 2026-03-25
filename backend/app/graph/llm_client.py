"""
LLM 客户端
封装 OpenAI 兼容 API 调用
"""

import json
import time
from typing import Any

import httpx
from pydantic import BaseModel

from app.config import settings


class LLMClient:
    """LLM 客户端"""

    def __init__(
        self,
        api_base: str | None = None,
        api_key: str | None = None,
        model_id: str | None = None,
    ):
        self.api_base = (api_base or settings.llm_api_base).rstrip("/")
        self.api_key = (api_key or settings.llm_api_key).strip()
        self.model_id = (model_id or settings.llm_model_id).strip()

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> tuple[str, dict[str, int], int]:
        """
        调用 Chat Completion API

        返回: (响应文本, token 使用统计, 耗时毫秒)
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            payload["response_format"] = response_format

        url = f"{self.api_base}/chat/completions"

        start_time = time.time()

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        elapsed_ms = int((time.time() - start_time) * 1000)

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return content, usage, elapsed_ms

    async def parse_json_response(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        temperature: float = 0.3,
    ) -> BaseModel:
        """
        调用 LLM 并解析 JSON 响应为 Pydantic 模型
        """
        # 添加 JSON 格式要求
        system_prompt = f"""
你是一个结构化数据提取助手。
请严格按照指定的 JSON Schema 格式输出，不要添加任何额外的文本或解释。
输出必须是有效的 JSON 格式。
"""

        full_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        content, usage, elapsed = await self.chat_completion(
            full_messages,
            response_format={"type": "json_object"},
            temperature=temperature,
        )

        # 解析 JSON
        try:
            data = json.loads(content)
            return schema.model_validate(data)
        except json.JSONDecodeError as e:
            # 尝试简单修复：如果是因为被截断而缺失括号
            try:
                fixed_content = content.strip()
                if not fixed_content.endswith("}") and not fixed_content.endswith("]"):
                    fixed_content += '"}]}'
                elif fixed_content.endswith("}") and not fixed_content.endswith("]}"):
                    fixed_content += ']}'
                
                data = json.loads(fixed_content)
                return schema.model_validate(data)
            except Exception as e2:
                raise ValueError(f"LLM 响应不是有效的 JSON: {e}\n尝试修复修复失败: {e2}\n响应内容: {content}")
        except Exception as e:
            raise ValueError(f"解析 LLM 响应失败: {e}\n响应内容: {content}")

    async def simple_completion(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        """简单的单轮对话"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        content, _, _ = await self.chat_completion(messages, temperature=temperature)
        return content


# 全局客户端实例
llm_client = LLMClient()
