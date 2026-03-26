"""
路由函数精准提取器
设计目标：给定目标项目源码路径 + 路由列表(method, path)，
精准提取每个路由对应的函数体，不多取、不漏取。
"""

import ast
import os
import re
import sys
from pathlib import Path
from typing import Iterator


# ────────────────────────────────────────────────────────────────
# 核心数据结构
# ────────────────────────────────────────────────────────────────

class RouteSnippet:
    """从源码中提取出的路由函数片段"""
    def __init__(self, route_id: str, file_path: str, start_line: int, end_line: int, code: str):
        self.route_id = route_id
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.code = code

    def __repr__(self):
        return f"<RouteSnippet {self.route_id} @ {self.file_path}:{self.start_line}-{self.end_line} ({len(self.code)} chars)>"


# ────────────────────────────────────────────────────────────────
# 路径模式匹配工具
# ────────────────────────────────────────────────────────────────

def _path_to_regex(openapi_path: str) -> re.Pattern:
    """
    将 OpenAPI path 转为可以匹配源码中路由路径的正则。
    例: /api/users/{user_id} → 匹配 "/api/users/{user_id}", "/users/{user_id}"
    (因为源码里的 router 可能不含前缀 /api)
    """
    # 转义特殊字符
    escaped = re.escape(openapi_path)
    # 把 \{xxx\} 替换为匹配任意路径参数占位符
    param_pattern = escaped.replace(r"\{", r"\{").replace(r"\}", r"\}")
    param_pattern = re.sub(r'\\{[^}]+\\}', r'\\{[^}]+\\}', param_pattern)
    # 允许匹配路径的任意后缀部分（省略前缀）
    # 例如 /api/admin/users 也能匹配源码里的 /admin/users
    segments = openapi_path.strip("/").split("/")
    # 构造"从任意段开始"的可选前缀模式
    alternatives = []
    for i in range(len(segments)):
        sub = "/" + "/".join(segments[i:])
        esc = re.escape(sub)
        esc = re.sub(r'\\{[^}]+\\}', r'\\{[^}]+\\}', esc)
        alternatives.append(esc)
    pattern_str = "(" + "|".join(alternatives) + ")"
    return re.compile(pattern_str)


# 匹配 FastAPI/Flask 风格的路由装饰器
# @app.get("/path") @router.post("/path") @xxx.api_route("/path", methods=[...])
_DECORATOR_PATTERN = re.compile(
    r'^\s*@\w[\w.]*\.(get|post|put|delete|patch|options|head|api_route)\s*\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# 匹配 methods= 参数（用于 api_route）
_METHODS_PATTERN = re.compile(r'methods\s*=\s*\[([^\]]+)\]', re.IGNORECASE)


# ────────────────────────────────────────────────────────────────
# 函数体提取（基于缩进 + 行扫描）
# ────────────────────────────────────────────────────────────────

def _extract_function_body(lines: list[str], decorator_line_idx: int) -> tuple[int, int]:
    """
    从 decorator 行开始，向下找到完整的函数定义。
    返回 (start_line_idx, end_line_idx) 均为0-based，end 为最后一行（包含）。

    策略：
    1. 找到紧接 decorator 后的 def/async def 行
    2. 记录函数签名的缩进级别
    3. 扫描后续行，直到遇到同缩进或更浅缩进的非空非注释行，即视为函数结束
    """
    n = len(lines)
    start = decorator_line_idx

    # 1. 向上找到最早的 decorator 行（可能有多个 decorator 叠加）
    # 已经知道 decorator_line_idx，往上找连续的 @ 开头行
    while start > 0:
        prev = lines[start - 1].strip()
        if prev.startswith("@") or prev == "" or prev.startswith("#"):
            start -= 1
        else:
            break

    # 2. 向下找到 def/async def 行
    def_line_idx = None
    for i in range(decorator_line_idx, min(decorator_line_idx + 10, n)):
        if re.match(r'\s*(async\s+)?def\s+\w+', lines[i]):
            def_line_idx = i
            break

    if def_line_idx is None:
        # 没找到 def，只返回 decorator 本身
        return decorator_line_idx, decorator_line_idx

    # 3. 确定函数缩进级别
    def_indent = len(lines[def_line_idx]) - len(lines[def_line_idx].lstrip())

    # 4. 找到函数体的结束位置
    # 函数体是比 def 缩进更深的所有行
    end = def_line_idx
    i = def_line_idx + 1
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 跳过空行和纯注释行（不代表函数结束）
        if stripped == "" or stripped.startswith("#"):
            i += 1
            continue

        curr_indent = len(line) - len(line.lstrip())
        if curr_indent <= def_indent:
            # 回到了函数定义层级或更浅，函数结束
            break

        end = i
        i += 1

    return start, end


# ────────────────────────────────────────────────────────────────
# 主提取器
# ────────────────────────────────────────────────────────────────

class RouteExtractor:
    """从目标项目源码中精准提取特定路由的函数体"""

    SCAN_EXTENSIONS = {".py"}
    EXCLUDE_DIRS = {"__pycache__", ".git", "venv", ".venv", "test", "tests",
                    "alembic", "migrations", ".backup_migrations", ".pytest_cache"}

    def __init__(self, source_path: str):
        self.source_path = Path(source_path)
        if not self.source_path.exists():
            raise ValueError(f"源码路径不存在: {source_path}")

    def _iter_python_files(self) -> Iterator[Path]:
        for root, dirs, files in os.walk(self.source_path):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if d not in self.EXCLUDE_DIRS]
            for f in files:
                if Path(f).suffix in self.SCAN_EXTENSIONS:
                    yield root_path / f

    def _match_route_in_decorator(
        self,
        decorator_text: str,
        target_method: str,
        path_regex: re.Pattern,
    ) -> bool:
        """判断一行装饰器是否匹配目标路由"""
        m = _DECORATOR_PATTERN.match(decorator_text)
        if not m:
            return False

        dec_verb = m.group(1).lower()
        dec_path = m.group(2)

        # api_route 需要额外检查 methods=
        if dec_verb == "api_route":
            methods_m = _METHODS_PATTERN.search(decorator_text)
            if methods_m:
                methods_raw = methods_m.group(1)
                methods = [x.strip().strip("'\"").upper() for x in methods_raw.split(",")]
                if target_method.upper() not in methods:
                    return False
            # else：没指定 methods，可能默认 GET，但保守起见继续匹配路径
        else:
            if dec_verb.upper() != target_method.upper():
                return False

        return bool(path_regex.search(dec_path))

    def extract_route(self, method: str, path: str) -> RouteSnippet | None:
        """提取单条路由的函数体，找到第一个匹配即返回"""
        path_regex = _path_to_regex(path)

        for py_file in self._iter_python_files():
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = content.splitlines()

            for i, line in enumerate(lines):
                if not line.strip().startswith("@"):
                    continue
                if not self._match_route_in_decorator(line, method, path_regex):
                    continue

                # 命中！提取函数体
                start_idx, end_idx = _extract_function_body(lines, i)
                snippet_lines = lines[start_idx : end_idx + 1]
                snippet_code = "\n".join(snippet_lines)

                # 计算相对路径（可读性）
                try:
                    rel_path = str(py_file.relative_to(self.source_path))
                except ValueError:
                    rel_path = str(py_file)

                return RouteSnippet(
                    route_id=f"{method.upper()}:{path}",
                    file_path=rel_path,
                    start_line=start_idx + 1,  # 转为1-based
                    end_line=end_idx + 1,
                    code=snippet_code,
                )

        return None  # 未找到

    def extract_routes(self, routes: list[tuple[str, str]]) -> dict[str, RouteSnippet | None]:
        """批量提取路由函数体，返回 route_id → RouteSnippet 映射"""
        result = {}
        for method, path in routes:
            route_id = f"{method.upper()}:{path}"
            snippet = self.extract_route(method, path)
            result[route_id] = snippet
        return result


# ────────────────────────────────────────────────────────────────
# 测试：针对 proj_for_test
# ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, "backend")
    
    SOURCE_PATH = r"d:\Desktop\talk-to-interface\proj_for_test"
    
    # 从数据库拿几个真实的 route_id 来测试
    import sqlite3
    conn = sqlite3.connect("workspace/lui.db")
    rows = conn.execute("SELECT backed_by_routes FROM capabilities LIMIT 20").fetchall()
    conn.close()

    import json
    routes_to_test = []
    for row in rows:
        try:
            backed = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            if backed and isinstance(backed, list):
                rid = backed[0].get("route_id", "")
                if rid and ":" in rid:
                    method, path = rid.split(":", 1)
                    routes_to_test.append((method, path))
        except Exception:
            continue
    
    # 去重取前10
    seen = set()
    unique_routes = []
    for r in routes_to_test:
        if r not in seen:
            seen.add(r)
            unique_routes.append(r)
        if len(unique_routes) >= 10:
            break

    print(f"测试提取 {len(unique_routes)} 条路由...")
    print("="*60)

    extractor = RouteExtractor(SOURCE_PATH)
    found = 0
    for method, path in unique_routes:
        snippet = extractor.extract_route(method, path)
        if snippet:
            found += 1
            print(f"✅ {method} {path}")
            print(f"   文件: {snippet.file_path}:{snippet.start_line}-{snippet.end_line}")
            print(f"   代码片段 (前200字):\n   {snippet.code[:200].replace(chr(10), chr(10)+'   ')}")
        else:
            print(f"❌ {method} {path}  (未找到)")
        print()

    print(f"命中率: {found}/{len(unique_routes)}")
