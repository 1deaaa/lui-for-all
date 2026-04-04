"""
框架适配器协议层
=================

本模块定义了 **FrameAdapter** 抽象基类及共享数据结构 **RouteSnippet**。

所有框架/语言的路由源码提取适配器均须继承 FrameAdapter。
如需新增框架支持，请阅读 CONTRIBUTING.md。

# 如何添加新框架支持（速查）：
#
#   1. 在 adapters/ 目录下新建文件，如 spring_boot.py
#   2. 继承 FrameAdapter，实现以下属性和方法：
#      - NAME        : str            适配器唯一标识
#      - LANGUAGES   : list[str]      支持的文件后缀，如 [".java"]
#      - can_handle() → bool          探针，判断该目录是否是你支持的框架
#      - extract_route() → RouteSnippet | None  提取单条路由
#   3. 在 adapters/__init__.py 的 _REGISTRY 列表末尾追加你的类
#   4. 详细指南见 adapters/CONTRIBUTING.md
"""

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator


# ────────────────────────────────────────────────────────────────
# 核心数据结构（框架无关）
# ────────────────────────────────────────────────────────────────

class RouteSnippet:
    """从源码中提取出的路由函数片段（语言/框架无关）"""

    def __init__(
        self,
        route_id: str,
        file_path: str,
        start_line: int,
        end_line: int,
        code: str,
        adapter_name: str = "unknown",
    ):
        self.route_id = route_id
        self.file_path = file_path
        self.start_line = start_line    # 1-based
        self.end_line = end_line        # 1-based，包含
        self.code = code
        self.adapter_name = adapter_name  # 产出该片段的适配器名称

    def __repr__(self) -> str:
        return (
            f"<RouteSnippet {self.route_id} @ "
            f"{self.file_path}:{self.start_line}-{self.end_line} "
            f"[{self.adapter_name}] ({len(self.code)} chars)>"
        )

    def to_context_block(self, seq_idx: int = 1, total: int = 1) -> str:
        """格式化为注入 LLM 上下文的代码块（下游格式保持不变）"""
        return (
            f"####### [{seq_idx}/{total}] {self.route_id} ##############\n"
            f"# 源码位置: {self.file_path} 第 {self.start_line}-{self.end_line} 行\n"
            f"{self.code}\n"
        )


# ────────────────────────────────────────────────────────────────
# 共享路径匹配工具（适配器可直接使用）
# ────────────────────────────────────────────────────────────────

def normalize_param_to_regex(path: str) -> str:
    """
    将 OpenAPI 路径参数 {param} 转换为正则通配符 [^/]+。
    同时兼容 Express/NestJS 的 :param 风格。

    示例：
        /api/users/{id}    → /api/users/[^/]+
        /api/users/:id     → /api/users/[^/]+
    """
    # 先统一 :param → {param}
    path = re.sub(r':(\w+)', r'{\1}', path)
    # 再转正则
    esc = re.escape(path)
    return re.sub(r'\\\{[^}]+\\\}', r'[^/]+', esc)


def path_matches(code_path: str, openapi_path: str) -> bool:
    """
    模糊路径匹配：判断代码中声明的路由路径是否对应 OpenAPI 路径。

    处理两种场景：
    1. 完全一致（含参数通配）：@get("/api/users/{id}") vs /api/users/{id}
    2. 前缀省略：代码写 /users，通过 router/controller prefix 挂载为 /api/v1/users

    同时兼容：
    - Python 装饰器 {param}
    - TypeScript/Express :param
    - 无参数的纯静态路径
    """
    code_re = normalize_param_to_regex(code_path)
    target_re = normalize_param_to_regex(openapi_path)

    # 匹配1：完全一致
    if re.fullmatch(target_re, code_path) or re.fullmatch(code_re, openapi_path):
        return True

    # 匹配2：target_path 的某个后缀与 code_path 完全吻合
    # 前提：code_path 段数 <= target_path 段数（代表框架 prefix 被吸收）
    # 关键约束：code_path 的静态段（非参数段）必须出现在 target 末尾对应位置
    code_segs = code_path.strip("/").split("/")
    target_segs = openapi_path.strip("/").split("/")
    n_code = len(code_segs)
    n_target = len(target_segs)

    if n_code > 0 and n_code <= n_target:
        # 取 target_path 末尾 n_code 段与 code_path 比较
        suffix_target_segs = target_segs[n_target - n_code:]
        suffix_target = "/" + "/".join(suffix_target_segs)
        suffix_target_re = normalize_param_to_regex(suffix_target)

        # 额外约束：code_path 中至少有一个静态段（非参数），
        # 且该静态段在 suffix_target 对应位置也是静态段（值相同）
        # 目的：防止 code="/users" 匹配 target_suffix="/{id}"
        has_static_match = False
        for ci, cs in enumerate(code_segs):
            # 跳过参数段
            code_is_param = cs.startswith("{") or cs.startswith(":")
            target_is_param = suffix_target_segs[ci].startswith("{")
            if not code_is_param and not target_is_param:
                # 两边都是静态段，值必须相同（忽略大小写）
                if cs.lower() == suffix_target_segs[ci].lower():
                    has_static_match = True
                else:
                    has_static_match = False
                    break

        if has_static_match and re.fullmatch(suffix_target_re, code_path):
            return True

    return False


def iter_source_files(
    source_path: Path,
    extensions: set[str],
    exclude_dirs: set[str] | None = None,
) -> Iterator[Path]:
    """
    通用源码文件遍历工具，适配器可直接调用。

    - extensions: 需要扫描的文件后缀集合，如 {".py"} 或 {".ts", ".js"}
    - exclude_dirs: 需要跳过的目录名称集合（默认包含常见噪音目录）
    """
    if exclude_dirs is None:
        exclude_dirs = {
            "__pycache__", ".git", "venv", ".venv", "node_modules",
            "dist", "build", ".next", "out",
            "test", "tests", "spec", "__tests__",
            "alembic", "migrations", ".backup_migrations",
            ".pytest_cache", ".mypy_cache",
        }
    import os
    for root, dirs, files in os.walk(source_path):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for f in sorted(files):
            fp = root_path / f
            if fp.suffix in extensions:
                yield fp


# ────────────────────────────────────────────────────────────────
# FrameAdapter 协议（抽象基类）
# ────────────────────────────────────────────────────────────────

class FrameAdapter(ABC):
    """
    框架适配器抽象基类。

    每个适配器代表一种"如何从一类后端框架的源码中定位路由实现"的能力。
    既可以对应某个具体框架（如 FastAPI、NestJS、Spring Boot），
    也可以对应一种原生 HTTP 开发风格（如 raw Node.js http.createServer）。

    类属性（子类必须定义）：

        NAME     : str        适配器唯一标识，全小写，如 "fastapi", "nestjs"
        LANGUAGES: list[str]  支持的文件后缀，如 [".py"] 或 [".ts", ".js"]

    必须实现的方法：

        can_handle(source_path) → bool
            探针：扫描目标目录，判断是否是本适配器能处理的项目。
            注册表会按优先级逐个调用，第一个返回 True 的适配器生效。

        extract_route(method, path) → RouteSnippet | None
            精准提取单条路由的函数/方法体。
            method 是大写 HTTP 方法（"GET", "POST" 等），path 是 OpenAPI 全路径。

    可选重写的方法：

        extract_batch(routes) → dict[str, RouteSnippet | None]
            批量提取。默认实现是逐条调用 extract_route，子类可覆盖以提升性能。
    """

    NAME: str = "base"
    LANGUAGES: list[str] = []

    def __init__(self, source_path: str):
        self.source_path = Path(source_path)

    @classmethod
    @abstractmethod
    def can_handle(cls, source_path: Path) -> bool:
        """
        探针：判断目标目录是否属于此适配器支持的框架/语言。

        建议检测优先级（从强到弱）：
          1. 检查特征文件是否存在（如 manage.py、nest-cli.json）
          2. 检查依赖文件中是否包含框架名称（requirements.txt、package.json）
          3. 扫描少量源码文件中的关键语法模式
        """
        ...

    @abstractmethod
    def extract_route(self, method: str, path: str) -> "RouteSnippet | None":
        """
        提取单条路由的完整函数/方法体。

        Args:
            method: HTTP 方法，大写，如 "GET"、"POST"
            path: OpenAPI 全路径，如 "/api/v1/users/{id}"

        Returns:
            RouteSnippet（找到）或 None（未找到）
        """
        ...

    def extract_batch(
        self, routes: list[tuple[str, str]]
    ) -> dict[str, "RouteSnippet | None"]:
        """
        批量提取多条路由。返回 route_id → RouteSnippet | None 映射。

        默认实现：逐条调用 extract_route。
        子类可覆盖此方法，通过一次性文件扫描提升批量性能。
        """
        return {
            f"{m.upper()}:{p}": self.extract_route(m, p)
            for m, p in routes
        }

    def __repr__(self) -> str:
        return f"<FrameAdapter:{self.NAME} @ {self.source_path}>"
