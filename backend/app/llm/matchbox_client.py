"""
agent-matchbox LLM 网关客户端（轻量集成版）

策略：仅复用 agent-matchbox 中的两个自包含模块：
  1. reasoning_compat.py  - reasoning_content / <think> 标签流式适配器
  2. builder.py 中的 ChatUniversal - 保留 reasoning_content 的 ChatOpenAI 子类

不初始化 AIManager（避免引入其 SQLite/用户管理体系），
直接用项目现有配置（settings.llm_api_base / api_key / model_id）
构建 ChatUniversal 实例，作为流式 LLM 调用入口。
"""

import logging
import os
import sys
import types

logger = logging.getLogger(__name__)

# agent-matchbox 目录（含 reasoning_compat.py、builder.py 等）
_MATCHBOX_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "agent-matchbox")
)

MATCHBOX_AVAILABLE = False
ChatUniversal = None
MessageEventStreamReasoningAdapter = None

try:
    # 将 agent-matchbox 目录加入 sys.path，让其内部文件可以作为顶层模块 import
    if _MATCHBOX_DIR not in sys.path:
        sys.path.insert(0, _MATCHBOX_DIR)

    # reasoning_compat.py 是完全自包含的（无任何相对 import），可直接导入
    import reasoning_compat as _rc  # type: ignore
    MessageEventStreamReasoningAdapter = _rc.MessageEventStreamReasoningAdapter

    # ChatUniversal 在 builder.py 中，builder.py 有相对导入（from .models 等），
    # 无法直接 import。因此我们在这里手动实现一个等价的轻量版：
    # 继承 ChatOpenAI，在 _convert_chunk_to_generation_chunk 中提取 reasoning_content。
    from langchain_openai import ChatOpenAI
    from langchain_core.outputs import ChatGenerationChunk

    def _extract_reasoning_from_delta(delta: dict) -> str:
        """从流式 delta 中提取非标准 reasoning 字段"""
        return _rc.extract_reasoning_text_from_chat_delta(delta)

    class ChatUniversal(ChatOpenAI):  # type: ignore
        """
        ChatOpenAI 子类：保留 OpenAI 兼容网关返回的 reasoning_content。
        与 agent-matchbox/builder.py 中的 ChatUniversal 行为一致。
        """

        def _convert_chunk_to_generation_chunk(
            self,
            chunk: dict,
            default_chunk_class: type,
            base_generation_info: dict | None,
        ) -> ChatGenerationChunk | None:
            result = super()._convert_chunk_to_generation_chunk(
                chunk, default_chunk_class, base_generation_info
            )
            if result is None:
                return None

            choices = chunk.get("choices") or chunk.get("chunk", {}).get("choices") or []
            if choices:
                delta = choices[0].get("delta") or {}
                reasoning = _extract_reasoning_from_delta(delta)
                if reasoning and isinstance(reasoning, str):
                    msg = result.message
                    if hasattr(msg, "additional_kwargs"):
                        msg.additional_kwargs["reasoning_content"] = reasoning

            return result

    MATCHBOX_AVAILABLE = True
    logger.info(f"✅ agent-matchbox 轻量层已从 {_MATCHBOX_DIR} 加载")

except Exception as e:
    import traceback
    logger.error(
        f"❌ agent-matchbox 轻量层加载失败: {e}\n{traceback.format_exc()}"
        "\n将回退到原始 httpx Provider。"
    )


def get_chat_llm(
    api_base: str,
    api_key: str,
    model_name: str,
    temperature: float | None = None,
    extra_body: dict | None = None,
):
    """
    构建 ChatUniversal 实例，直接用项目已有配置。
    返回值可直接用于 LangChain astream() / ainvoke()。
    """
    if not MATCHBOX_AVAILABLE or ChatUniversal is None:
        raise RuntimeError("agent-matchbox 轻量层不可用")

    kwargs = {
        "base_url": api_base.rstrip("/"),
        "api_key": api_key,
        "model_name": model_name,
        "default_headers": {"User-Agent": "TalkToInterface/1.0"},
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if extra_body:
        kwargs["model_kwargs"] = {"extra_body": extra_body}

    return ChatUniversal(**kwargs)
