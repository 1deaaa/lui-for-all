"""
Python 装饰器风格适配器
=======================

支持所有使用「路由装饰器」风格的 Python 后端框架：

    ✅ FastAPI   (@app.get / @router.post 等)
    ✅ Flask     (@app.route / @bp.get 等)
    ✅ Sanic     (@app.route / @bp.get 等)
    ✅ Starlette (装饰器路由)
    ✅ Litestar  (@get / @post 等)

若使用的是 Django（urls.py 集中配置式路由），请参考
adapters/CONTRIBUTING.md 中的 Django 适配器贡献指南。
"""

import re
from pathlib import Path

from app.discovery.adapters.base import (
    FrameAdapter,
    RouteSnippet,
    iter_source_files,
    path_matches,
)


# ────────────────────────────────────────────────────────────────
# 正则：装饰器识别
# ────────────────────────────────────────────────────────────────

# 匹配 @xxx.get("/path") / @xxx.post("/path") / @xxx.api_route("/path") 等
_DECORATOR_RE = re.compile(
    r'^\s*@\w[\w.]*\.(get|post|put|delete|patch|options|head|api_route)\s*\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# 匹配 methods=["GET", "POST"] 参数（Flask @app.route 风格）
_METHODS_RE = re.compile(r'methods\s*=\s*\[([^\]]+)\]', re.IGNORECASE)

# 用于 can_handle() 快速探针
_DECORATOR_PROBE_RE = re.compile(
    r'@\w[\w.]*\.(get|post|put|delete|patch|options|head|route|api_route)\s*\(',
    re.IGNORECASE,
)

# 主流 Python Web 框架关键词（用于依赖文件检测）
_KNOWN_FRAMEWORKS = frozenset([
    "fastapi", "flask", "sanic", "starlette", "litestar",
    "falcon", "aiohttp", "tornado", "bottle", "quart",
])


# ────────────────────────────────────────────────────────────────
# 内部工具函数
# ────────────────────────────────────────────────────────────────

def _decorator_matches(line: str, method: str, path: str) -> bool:
    """判断单行装饰器是否与 (method, path) 匹配"""
    m = _DECORATOR_RE.match(line)
    if not m:
        return False

    dec_verb = m.group(1).lower()
    dec_path = m.group(2)

    # Flask 的 @app.route() 使用 methods=[...] 参数
    if dec_verb == "api_route" or dec_verb == "route":
        mm = _METHODS_RE.search(line)
        if mm:
            methods = [x.strip().strip("'\"").upper() for x in mm.group(1).split(",")]
            if method.upper() not in methods:
                return False
        # route() 不指定 methods 时默认 GET
        elif method.upper() != "GET":
            return False
    else:
        if dec_verb.upper() != method.upper():
            return False

    return path_matches(dec_path, path)


def _extract_function_body(lines: list[str], decorator_line_idx: int) -> tuple[int, int]:
    """
    从命中的装饰器行开始，提取完整函数体（含上方连续所有装饰器）。
    返回 (start_idx, end_idx)，均 0-based，end 包含。

    算法：基于 Python 缩进规则，当缩进层级回到 def 行或更浅时停止。
    """
    n = len(lines)

    # 1. 向上找到最早的连续装饰器行
    start = decorator_line_idx
    while start > 0:
        prev = lines[start - 1].strip()
        if prev.startswith("@"):
            start -= 1
        else:
            break

    # 2. 向下找到 def / async def 行
    def_idx = None
    for i in range(decorator_line_idx, min(decorator_line_idx + 15, n)):
        if re.match(r"\s*(async\s+)?def\s+\w+", lines[i]):
            def_idx = i
            break

    if def_idx is None:
        return start, decorator_line_idx

    # 3. 计算函数基准缩进
    base_indent = len(lines[def_idx]) - len(lines[def_idx].lstrip())

    # 4. 从 def 行之后扫描，找到函数体结束
    end = def_idx
    i = def_idx + 1
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 空行 / 纯注释不终止
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        curr_indent = len(line) - len(line.lstrip())
        if curr_indent <= base_indent:
            break  # 回到函数定义层或更浅 → 函数结束

        end = i
        i += 1

    return start, end


# ────────────────────────────────────────────────────────────────
# 适配器实现
# ────────────────────────────────────────────────────────────────

class PythonDecoratorAdapter(FrameAdapter):
    """
    Python 装饰器风格路由适配器。

    覆盖：FastAPI、Flask、Sanic、Starlette、Litestar 等。
    不覆盖：Django（其路由定义在 urls.py，与视图分离，需独立适配器）。
    """

    NAME = "python_decorator"
    LANGUAGES = [".py"]

    EXCLUDE_DIRS = {
        "__pycache__", ".git", "venv", ".venv",
        "test", "tests", "alembic", "migrations",
        ".backup_migrations", ".pytest_cache", "node_modules",
    }

    # ── 探针 ──────────────────────────────────────────────────

    @classmethod
    def can_handle(cls, source_path: Path) -> bool:
        """
        检测目标目录是否是 Python 装饰器风格的后端项目。

        检测顺序：
          1. 依赖文件中包含已知 Python Web 框架名称
          2. 任意 .py 文件中包含装饰器路由模式
        """
        # 信号1：依赖文件扫描（快速）
        for dep_name in ("requirements.txt", "requirements-base.txt",
                          "pyproject.toml", "Pipfile", "setup.py"):
            dep_path = source_path / dep_name
            if dep_path.exists():
                try:
                    content = dep_path.read_text(encoding="utf-8", errors="ignore").lower()
                    if any(fw in content for fw in _KNOWN_FRAMEWORKS):
                        return True
                except Exception:
                    pass

        # 信号2：源码文件快速探针（扫描前 30 个 .py 文件）
        count = 0
        for py_file in source_path.rglob("*.py"):
            if count >= 30:
                break
            count += 1
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                if _DECORATOR_PROBE_RE.search(content):
                    return True
            except Exception:
                continue

        return False

    # ── 提取 ─────────────────────────────────────────────────

    def extract_route(self, method: str, path: str) -> RouteSnippet | None:
        """提取单条路由的完整函数体（找到第一个匹配即返回）"""
        for py_file in iter_source_files(self.source_path, {".py"}, self.EXCLUDE_DIRS):
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = content.splitlines()

            for i, line in enumerate(lines):
                if not line.strip().startswith("@"):
                    continue
                if not _decorator_matches(line, method, path):
                    continue

                # 命中！提取函数体
                s_idx, e_idx = _extract_function_body(lines, i)
                code = "\n".join(lines[s_idx: e_idx + 1])

                try:
                    rel_path = str(py_file.relative_to(self.source_path))
                except ValueError:
                    rel_path = str(py_file)

                return RouteSnippet(
                    route_id=f"{method.upper()}:{path}",
                    file_path=rel_path,
                    start_line=s_idx + 1,
                    end_line=e_idx + 1,
                    code=code,
                    adapter_name=self.NAME,
                )

        return None
