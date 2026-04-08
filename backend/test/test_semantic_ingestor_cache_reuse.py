from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.discovery.capability_builder import CapabilityGraphBuilder
from app.discovery.semantic_ingestor import ingest_semantic_routes_with_snippets


def test_ast_semantic_cache_avoids_second_extract_scan() -> None:
    sample_path = REPO_ROOT / "backend_for_test" / "node_sample"
    assert sample_path.exists(), f"Sample path missing: {sample_path}"

    semantic_result = asyncio.run(
        ingest_semantic_routes_with_snippets(
            source_path=str(sample_path),
            base_url="http://localhost:8020",
        )
    )

    builder = CapabilityGraphBuilder(
        route_map=semantic_result.route_map,
        source_path=str(sample_path),
        pre_extracted_snippets=semantic_result.route_snippets_by_route_id,
    )

    async def _fake_chunk_analyze(*args, **kwargs):
        return {}

    # 避免触发真实 LLM 请求，只验证提取阶段是否复用缓存。
    builder._analyze_route_chunk = _fake_chunk_analyze

    with patch(
        "app.discovery.capability_builder.RouteExtractor",
        side_effect=AssertionError("RouteExtractor should not be called when snippet cache fully matches."),
    ):
        analyses = asyncio.run(builder._analyze_routes_with_ai(str(sample_path)))

    assert analyses == {}
