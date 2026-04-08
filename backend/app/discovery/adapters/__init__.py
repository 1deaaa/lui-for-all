"""
框架适配器注册表
================

本模块维护所有已注册的 FrameAdapter，并提供 get_adapter() 自动检测入口。

贡献者添加新适配器只需：

    1. 在 adapters/ 目录下新建文件，继承 FrameAdapter
    2. 在下方 _REGISTRY 列表末尾追加你的类
    3. 详细步骤见仓库根目录 CONTRIBUTING.md

已注册适配器（按检测优先级排序）：

    1. DjangoUrlconfAdapter   — Django urls.py 集中路由风格
    2. PythonDecoratorAdapter — FastAPI / Flask / Sanic 等 Python 装饰器风格
    3. NodejsTypescriptAdapter — NestJS / Express / Fastify 等 Node.js 框架
    4. JavaSpringAdapter      — Spring Boot / Spring MVC
    5. AspNetCoreAdapter      — ASP.NET Core Controller / Minimal API
    6. GoWebAdapter           — Gin / Echo / Fiber / Chi

待贡献：

    - Ruby on Rails (routes.rb 约定式路由)
    - PHP (Laravel routes/api.php)
    - 原生 HTTP 端点（不使用任何框架）
"""

from pathlib import Path

from app.discovery.adapters.base import FrameAdapter, RouteSnippet, path_matches
from app.discovery.adapters.django_urlconf import DjangoUrlconfAdapter
from app.discovery.adapters.python_decorator import PythonDecoratorAdapter
from app.discovery.adapters.nodejs_ts import NodejsTypescriptAdapter
from app.discovery.adapters.java_spring import JavaSpringAdapter
from app.discovery.adapters.aspnet_core import AspNetCoreAdapter
from app.discovery.adapters.go_web import GoWebAdapter
from app.discovery.adapters.paradigms import AST_PARADIGM_DESCRIPTIONS


# ────────────────────────────────────────────────────────────────
# 注册表（按检测优先级从高到低排列）
#
# 规则：
#   - 越具体的适配器（如 DjangoAdapter）应排在越通用的适配器前面
#   - get_adapter() 返回第一个 can_handle() 返回 True 的适配器
#   - 若所有适配器均返回 False，返回 None（调用方降级为规则推断）
# ────────────────────────────────────────────────────────────────

_REGISTRY: list[type[FrameAdapter]] = [
    DjangoUrlconfAdapter,
    PythonDecoratorAdapter,
    NodejsTypescriptAdapter,
    JavaSpringAdapter,
    AspNetCoreAdapter,
    GoWebAdapter,
    # ── 未来贡献者在此追加 ──────────────────────────────────────
    # DjangoAdapter,          # 参见 adapters/django_urlconf.py（待贡献）
    # SpringBootAdapter,      # 参见 adapters/spring_boot.py（待贡献）
    # AspNetCoreAdapter,      # 参见 adapters/aspnet_core.py（待贡献）
    # GinAdapter,             # 参见 adapters/go_gin.py（待贡献）
    # RailsAdapter,           # 参见 adapters/rails_route.py（待贡献）
    # LaravelAdapter,         # 参见 adapters/laravel.py（待贡献）
]


def get_adapter(source_path: str) -> FrameAdapter | None:
    """
    自动检测并返回最匹配目标项目的适配器实例。

    遍历注册表，按优先级调用每个适配器的 can_handle()。
    返回第一个可处理该目录的适配器实例；若均不匹配则返回 None。

    Args:
        source_path: 目标项目本地源码根目录路径

    Returns:
        FrameAdapter 实例，或 None（无匹配时）

    Example:
        adapter = get_adapter("/path/to/my/fastapi-project")
        # → <FrameAdapter:python_decorator @ /path/to/my/fastapi-project>
    """
    path = Path(source_path)
    if not path.exists() or not path.is_dir():
        return None

    for adapter_cls in _REGISTRY:
        try:
            if adapter_cls.can_handle(path):
                return adapter_cls(source_path)
        except Exception as e:
            print(f"[AdapterRegistry] ⚠️ 适配器 {adapter_cls.NAME} 探针异常: {e}")
            continue

    return None


def list_adapters() -> list[dict]:
    """返回所有已注册适配器的基本信息（调试/诊断用）"""
    return [cls.metadata() for cls in _REGISTRY]


def list_ast_paradigms() -> dict[str, str]:
    """Return normalized AST routing paradigms used by all adapters."""
    return dict(AST_PARADIGM_DESCRIPTIONS)


__all__ = [
    "FrameAdapter",
    "RouteSnippet",
    "path_matches",
    "DjangoUrlconfAdapter",
    "PythonDecoratorAdapter",
    "NodejsTypescriptAdapter",
    "JavaSpringAdapter",
    "AspNetCoreAdapter",
    "GoWebAdapter",
    "get_adapter",
    "list_adapters",
    "list_ast_paradigms",
]
