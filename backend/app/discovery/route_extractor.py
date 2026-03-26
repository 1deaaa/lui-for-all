"""
路由函数精准提取器
给定目标项目源码路径 + 路由列表，精准提取每条路由的函数实现代码。
不依赖任何第三方库，仅使用标准库的 re、os、pathlib。
"""

import os
import re
from pathlib import Path
from typing import Iterator


# ────────────────────────────────────────────────────────────────
# 核心数据结构
# ────────────────────────────────────────────────────────────────

class RouteSnippet:
    """从源码中提取出的路由函数片段"""

    def __init__(
        self,
        route_id: str,
        file_path: str,
        start_line: int,
        end_line: int,
        code: str,
    ):
        self.route_id = route_id
        self.file_path = file_path
        self.start_line = start_line  # 1-based
        self.end_line = end_line      # 1-based，包含
        self.code = code

    def __repr__(self) -> str:
        return (
            f"<RouteSnippet {self.route_id} @ "
            f"{self.file_path}:{self.start_line}-{self.end_line} "
            f"({len(self.code)} chars)>"
        )

    def to_context_block(self, seq_idx: int = 1, total: int = 1) -> str:
        """格式化为注入 LLM 上下文的代码块"""
        return (
            f"####### [{seq_idx}/{total}] {self.route_id} ##############\n"
            f"# 源码位置: {self.file_path} 第 {self.start_line}-{self.end_line} 行\n"
            f"{self.code}\n"
        )


# ────────────────────────────────────────────────────────────────
# 装饰器匹配
# ────────────────────────────────────────────────────────────────

# 匹配 @xxx.get("/path") / @xxx.post("/path") 等 FastAPI/Flask 风格
_DECORATOR_RE = re.compile(
    r'^\s*@\w[\w.]*\.(get|post|put|delete|patch|options|head|api_route)\s*\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# 匹配 methods=["GET", "POST"] 参数
_METHODS_RE = re.compile(r'methods\s*=\s*\[([^\]]+)\]', re.IGNORECASE)


def _path_segments(path: str) -> list[str]:
    """提取路径的核心路径段（去掉前缀时，用末尾段做匹配锚点）"""
    segs = [s for s in path.strip("/").split("/") if s and not s.startswith("{")]
    return segs


def _path_matches(decorator_path: str, target_path: str) -> bool:
    """
    判断装饰器中的路径是否与 OpenAPI 路径一致。
    处理两种情况：
    1. 完全一致：`/api/users` == `/api/users`
    2. 前缀省略：装饰器写 `/users`，通过 include_router(prefix='/api') 挂载
    
    策略：
    - 将 target_path 的路径参数 {xxx} 替换为通配符，做正则比对
    - 支持 target_path 为 decorator_path 的后缀（前缀被 include_router 吃掉）
    """
    # 把 {param} 替换为 [^/]+ 做松散匹配
    def to_regex(p: str) -> str:
        esc = re.escape(p)
        return re.sub(r'\\{[^}]+\\}', r'[^/]+', esc)

    target_re = to_regex(target_path)

    # 匹配1：完全一致（含参数替换）
    if re.fullmatch(target_re, decorator_path):
        return True

    # 匹配2：target 是 decorator 的后缀（去掉若干前缀段）
    target_segs = target_path.strip("/").split("/")
    dec_segs = decorator_path.strip("/").split("/")

    for i in range(len(target_segs)):
        suffix_target = "/" + "/".join(target_segs[i:])
        suffix_re = to_regex(suffix_target)
        if re.fullmatch(suffix_re, decorator_path):
            return True

        # 反向：decorator 可能是 target 的后缀（target 含前缀但 decorator 只有部分）
        suffix_dec = "/" + "/".join(dec_segs[-(len(target_segs) - i):]) if len(dec_segs) >= len(target_segs) - i else ""
        if suffix_dec and re.fullmatch(suffix_re, suffix_dec):
            return True

    return False


def _decorator_matches(line: str, method: str, path: str) -> bool:
    """判断单行装饰器是否与 (method, path) 匹配"""
    m = _DECORATOR_RE.match(line)
    if not m:
        return False

    dec_verb = m.group(1).lower()
    dec_path = m.group(2)

    if dec_verb == "api_route":
        mm = _METHODS_RE.search(line)
        if mm:
            methods = [x.strip().strip("'\"").upper() for x in mm.group(1).split(",")]
            if method.upper() not in methods:
                return False
    else:
        if dec_verb.upper() != method.upper():
            return False

    return _path_matches(dec_path, path)


# ────────────────────────────────────────────────────────────────
# 函数体提取（缩进算法）
# ────────────────────────────────────────────────────────────────

def _extract_function_body(lines: list[str], decorator_line_idx: int) -> tuple[int, int]:
    """
    从命中的 decorator 行开始，提取完整函数体（含上方连续的所有装饰器）。
    返回 (start_idx, end_idx)，均为 0-based，end 包含。
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
# 主类
# ────────────────────────────────────────────────────────────────

class RouteExtractor:
    """从目标项目源码中精准提取路由函数实现代码"""

    SCAN_EXTENSIONS = {".py"}
    EXCLUDE_DIRS = {
        "__pycache__", ".git", "venv", ".venv",
        "test", "tests", "alembic", "migrations",
        ".backup_migrations", ".pytest_cache", "node_modules",
    }

    def __init__(self, source_path: str):
        self.source_path = Path(source_path)
        if not self.source_path.exists():
            raise ValueError(f"源码路径不存在: {source_path}")

    def _iter_python_files(self) -> Iterator[Path]:
        """遍历所有有效 Python 文件"""
        for root, dirs, files in os.walk(self.source_path):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if d not in self.EXCLUDE_DIRS]
            for f in sorted(files):
                fp = root_path / f
                if fp.suffix in self.SCAN_EXTENSIONS:
                    yield fp

    def extract_route(self, method: str, path: str) -> "RouteSnippet | None":
        """提取单条路由的完整函数体（找到第一个匹配即返回）"""
        for py_file in self._iter_python_files():
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
                code = "\n".join(lines[s_idx : e_idx + 1])

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
                )

        return None

    def extract_batch(
        self, routes: list[tuple[str, str]]
    ) -> dict[str, "RouteSnippet | None"]:
        """批量提取，返回 route_id → RouteSnippet | None 映射"""
        return {
            f"{m.upper()}:{p}": self.extract_route(m, p)
            for m, p in routes
        }
