import argparse
import os
import time
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI


@dataclass
class StreamStats:
    total_chunks: int
    content_chunks: int
    total_chars: int
    first_content_ms: Optional[int]
    last_content_ms: Optional[int]
    content_span_ms: Optional[int]
    full_text: str


def _extract_content(chunk) -> str:
    """从 OpenAI 流式 chunk 中提取可见正文。"""
    try:
        if not chunk.choices:
            return ""
        delta = chunk.choices[0].delta
        if delta is None:
            return ""
        content = getattr(delta, "content", None)
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        return str(content)
    except Exception:
        return ""


def run_once(client: OpenAI, model: str, prompt: str, temperature: float) -> StreamStats:
    """执行单次上游流式请求并输出到达时序。"""
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        stream=True,
    )

    start = time.perf_counter()
    total_chunks = 0
    content_chunks = 0
    total_chars = 0
    first_content_ms: Optional[int] = None
    last_content_ms: Optional[int] = None
    pieces: list[str] = []

    for chunk in stream:
        total_chunks += 1
        text = _extract_content(chunk)
        now_ms = int((time.perf_counter() - start) * 1000)

        if not text:
            continue

        content_chunks += 1
        total_chars += len(text)
        pieces.append(text)

        if first_content_ms is None:
            first_content_ms = now_ms
        last_content_ms = now_ms

        preview = text.replace("\r", " ").replace("\n", "⏎")
        if len(preview) > 48:
            preview = preview[:48] + "..."
        print(f"[{now_ms:6}ms] content#{content_chunks} len={len(text)} text={preview}")

    full_text = "".join(pieces)
    span = None
    if first_content_ms is not None and last_content_ms is not None:
        span = last_content_ms - first_content_ms

    return StreamStats(
        total_chunks=total_chunks,
        content_chunks=content_chunks,
        total_chars=total_chars,
        first_content_ms=first_content_ms,
        last_content_ms=last_content_ms,
        content_span_ms=span,
        full_text=full_text,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="原生 OpenAI 客户端上游流式探针")
    parser.add_argument("--base-url", required=True, help="上游 OpenAI 兼容接口地址，例如 https://host/v1")
    parser.add_argument("--model", required=True, help="模型名称")
    parser.add_argument("--prompt", default="请用不少于120字说明你正在进行流式输出测试。")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.3)
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("缺少环境变量 OPENAI_API_KEY")

    client = OpenAI(api_key=api_key, base_url=args.base_url)

    print("===== UPSTREAM STREAM PROBE =====")
    print(f"base_url={args.base_url}")
    print(f"model={args.model}")
    print(f"trials={args.trials}")

    for i in range(1, args.trials + 1):
        print(f"\n--- trial {i} ---")
        stats = run_once(client, args.model, args.prompt, args.temperature)
        print("summary:")
        print(f"  total_chunks={stats.total_chunks}")
        print(f"  content_chunks={stats.content_chunks}")
        print(f"  total_chars={stats.total_chars}")
        print(f"  first_content_ms={stats.first_content_ms}")
        print(f"  last_content_ms={stats.last_content_ms}")
        print(f"  content_span_ms={stats.content_span_ms}")
        preview = stats.full_text.replace("\r", " ").replace("\n", "⏎")
        if len(preview) > 160:
            preview = preview[:160] + "..."
        print(f"  final_preview={preview}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
