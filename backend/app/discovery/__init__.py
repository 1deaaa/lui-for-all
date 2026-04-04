"""
发现模块初始化
"""

from app.discovery.capability_builder import CapabilityGraphBuilder, build_capability_graph
from app.discovery.openapi_ingestor import OpenAPIIngestor, ingest_openapi
from app.discovery.service import DiscoveryService, run_discovery

# 适配器层公共接口（供外部贡献者及调试工具使用）
from app.discovery.adapters import (
    FrameAdapter,
    RouteSnippet,
    get_adapter,
    list_adapters,
    PythonDecoratorAdapter,
    NodejsTypescriptAdapter,
)

__all__ = [
    # 核心发现流程
    "OpenAPIIngestor",
    "ingest_openapi",
    "CapabilityGraphBuilder",
    "build_capability_graph",
    "DiscoveryService",
    "run_discovery",
    # 适配器层（贡献者扩展点）
    "FrameAdapter",
    "RouteSnippet",
    "get_adapter",
    "list_adapters",
    "PythonDecoratorAdapter",
    "NodejsTypescriptAdapter",
]
