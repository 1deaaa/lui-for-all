"""
路由源码提取编排层
==================

本模块是路由提取流程的编排入口，不含任何框架相关逻辑。

具体的"如何从源码中找到路由函数"由 adapters/ 层中各框架
适配器负责实现。本模块仅负责：

    1. 根据目标项目目录自动选择合适的适配器
    2. 将提取请求委托给适配器执行
    3. 向上游（capability_builder.py）提供统一的接口

向后兼容说明：
    RouteSnippet 从原模块迁移至 adapters/base.py，
    此处保留重导出，上游调用方无需修改任何 import 路径。
"""

from pathlib import Path

from app.discovery.adapters import get_adapter
from app.discovery.adapters.base import RouteSnippet  # 重导出，保持向后兼容

__all__ = ["RouteExtractor", "RouteSnippet"]


class RouteExtractor:
    """
    路由函数提取器（编排层）。

    自动检测目标项目使用的后端框架，并将提取任务委托给
    对应的 FrameAdapter 执行。

    若无匹配适配器，extract_route() 返回 None，
    上游的 capability_builder.py 将自动降级为规则推断模式。

    支持的框架由 adapters/_REGISTRY 决定，添加新框架无需
    修改本文件，详见仓库根目录 CONTRIBUTING.md。
    """

    def __init__(self, source_path: str):
        self.source_path = Path(source_path)
        if not self.source_path.exists():
            raise ValueError(f"源码路径不存在: {source_path}")

        self._adapter = get_adapter(source_path)

        if self._adapter:
            print(
                f"[RouteExtractor] ✅ 检测到框架适配器: "
                f"{self._adapter.NAME} ({self.source_path})"
            )
        else:
            print(
                f"[RouteExtractor] ⚠️ 未找到匹配的框架适配器 "
                f"({self.source_path})，源码提取不可用，将使用规则推断"
            )

    @property
    def adapter_name(self) -> str | None:
        """返回当前使用的适配器名称，未匹配时为 None"""
        return self._adapter.NAME if self._adapter else None

    @property
    def adapter_metadata(self) -> dict | None:
        """返回当前适配器元数据，便于调试与诊断。"""
        return self._adapter.metadata() if self._adapter else None

    @property
    def adapter_ast_paradigms(self) -> list[str]:
        """返回当前适配器声明的 AST 路由范式。"""
        if not self._adapter:
            return []
        return list(self._adapter.metadata().get("ast_paradigms", []))

    def extract_route(self, method: str, path: str) -> "RouteSnippet | None":
        """
        提取单条路由的完整函数体。

        Args:
            method: HTTP 方法，大写，如 "GET"、"POST"
            path:   OpenAPI 全路径，如 "/api/v1/users/{id}"

        Returns:
            RouteSnippet（找到）或 None（未找到或无适配器）
        """
        if not self._adapter:
            return None
        return self._adapter.extract_route(method, path)

    def extract_batch(
        self, routes: list[tuple[str, str]]
    ) -> dict[str, "RouteSnippet | None"]:
        """
        批量提取多条路由。

        Args:
            routes: [(method, path), ...] 列表

        Returns:
            dict: route_id → RouteSnippet | None 映射
        """
        if not self._adapter:
            return {f"{m.upper()}:{p}": None for m, p in routes}
        return self._adapter.extract_batch(routes)

    def extract_all_routes(self) -> list["RouteSnippet"]:
        """
        提取项目中可识别的全部路由片段。

        Returns:
            list[RouteSnippet]: 适配器可解析出的全部路由
        """
        if not self._adapter:
            return []
        return self._adapter.discover_routes()
