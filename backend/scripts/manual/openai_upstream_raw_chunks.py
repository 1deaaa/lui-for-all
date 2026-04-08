import argparse
import os
from typing import Any

from openai import OpenAI


def _compact(obj: Any, limit: int = 220) -> str:
    text = str(obj).replace("\n", "\\n")
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="查看上游流式 raw chunk 结构")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", default="请说明你正在流式输出测试。")
    parser.add_argument("--max-print", type=int, default=25)
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("缺少 OPENAI_API_KEY")

    client = OpenAI(api_key=api_key, base_url=args.base_url)

    stream = client.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": args.prompt}],
        stream=True,
        temperature=0.3,
    )

    printed = 0
    total = 0
    content_non_empty = 0

    for chunk in stream:
        total += 1
        data = chunk.model_dump(mode="json")
        choices = data.get("choices") or []
        delta = choices[0].get("delta") if choices else {}
        finish_reason = choices[0].get("finish_reason") if choices else None

        content = ""
        if isinstance(delta, dict):
            content = str(delta.get("content") or "")
            if content:
                content_non_empty += 1

        if printed < args.max_print:
            keys = list(delta.keys()) if isinstance(delta, dict) else []
            print(f"chunk#{total} keys={keys} finish_reason={finish_reason}")
            if isinstance(delta, dict):
                for k, v in delta.items():
                    print(f"  {k}: {_compact(v)}")
            printed += 1

    print("---")
    print(f"total_chunks={total}")
    print(f"content_non_empty_chunks={content_non_empty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
