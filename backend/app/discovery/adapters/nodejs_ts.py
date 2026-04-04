"""
Node.js / TypeScript 适配器
============================

支持主流 Node.js 后端框架：

    ✅ NestJS    (装饰器风格：@Get、@Post、@Controller 等)
    ✅ Express   (函数式风格：router.get('/path', handler))
    ✅ Fastify   (函数式风格：fastify.get('/path', handler))
    🔲 Koa      (router.get - 语法类似 Express，可扩展)
    🔲 Hono     (app.get - 语法类似 Express，可扩展)
    🔲 原生 HTTP (http.createServer + switch/if 路由判断)

文件后缀支持：.ts 和 .js
"""

import json
import re
from pathlib import Path

from app.discovery.adapters.base import (
    FrameAdapter,
    RouteSnippet,
    iter_source_files,
    path_matches,
)


# ────────────────────────────────────────────────────────────────
# 正则：NestJS 装饰器风格
# ────────────────────────────────────────────────────────────────

# 匹配 @Get('/path') / @Post(':id') / @Delete() 等方法装饰器
_NESTJS_DECORATOR_RE = re.compile(
    r"""^\s*@(Get|Post|Put|Delete|Patch|Options|Head|All)\s*\(\s*(?:['"](.*?)['"])?\s*\)""",
    re.IGNORECASE,
)

# 匹配 @Controller('prefix') 类装饰器（用于拼合完整路径）
_NESTJS_CONTROLLER_RE = re.compile(
    r"""@Controller\s*\(\s*['"](.*?)['"]\s*\)""",
    re.IGNORECASE,
)

# ────────────────────────────────────────────────────────────────
# 正则：Express / Fastify / Koa 函数式风格
# ────────────────────────────────────────────────────────────────

# 匹配 router.get('/path', ...) / app.post('/path', ...)
_EXPRESS_ROUTE_RE = re.compile(
    r"""^\s*[\w$][\w$.]*\.(get|post|put|delete|patch|options|head)\s*\(\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)

# ────────────────────────────────────────────────────────────────
# 已知 Node.js 框架关键词
# ────────────────────────────────────────────────────────────────

_KNOWN_FRAMEWORKS = frozenset([
    "express", "@nestjs/core", "fastify", "koa", "@koa/router",
    "hapi", "@hapi/hapi", "restify", "hono", "elysia",
    "micro", "polka", "tinyhttp",
])


# ────────────────────────────────────────────────────────────────
# TypeScript 代码块提取（大括号计数法）
# ────────────────────────────────────────────────────────────────

def _extract_block_by_braces(lines: list[str], start_idx: int) -> tuple[int, int]:
    """
    从 start_idx 行开始，向下追踪大括号嵌套深度，找到完整的函数/方法块。
    返回 (start_idx, end_idx)，0-based，end 包含。

    适用于 TypeScript / JavaScript / Java / Go / C# 等大括号语言。
    注意：简单计数法，不处理字符串/注释中的花括号，适合真实业务代码。
    """
    n = len(lines)
    depth = 0
    found_open = False

    for i in range(start_idx, n):
        line = lines[i]
        for ch in line:
            if ch == '{':
                depth += 1
                found_open = True
            elif ch == '}':
                if found_open:
                    depth -= 1
                    if depth == 0:
                        return start_idx, i

    # 若未找到完整的闭合，降级返回当前行
    return start_idx, start_idx


def _extract_nestjs_method_body(lines: list[str], decorator_line_idx: int) -> tuple[int, int]:
    """
    从 NestJS 方法装饰器行（@Get 等）开始，
    向上收集连续装饰器，向下找到方法体并提取完整块。
    """
    n = len(lines)

    # 1. 向上找到最早的连续装饰器行（类方法可能有多个装饰器叠加）
    start = decorator_line_idx
    while start > 0:
        prev = lines[start - 1].strip()
        if prev.startswith("@"):
            start -= 1
        else:
            break

    # 2. 向下找到方法签名行（含 async / public / private 等修饰符）
    method_start = None
    for i in range(decorator_line_idx, min(decorator_line_idx + 10, n)):
        stripped = lines[i].strip()
        if re.match(r'(async\s+|public\s+|private\s+|protected\s+)*\w+\s*\(', stripped):
            # 排除装饰器本身
            if not stripped.startswith("@"):
                method_start = i
                break

    if method_start is None:
        return start, decorator_line_idx

    # 3. 从方法签名行开始，提取完整大括号块
    _, end = _extract_block_by_braces(lines, method_start)
    return start, end


# ────────────────────────────────────────────────────────────────
# 路径匹配工具
# ────────────────────────────────────────────────────────────────

def _nestjs_matches(line: str, method: str, path: str) -> bool:
    """判断 NestJS 方法装饰器行是否与 (method, path) 匹配"""
    m = _NESTJS_DECORATOR_RE.match(line)
    if not m:
        return False

    dec_verb = m.group(1).upper()
    dec_path = m.group(2) or ""  # @Get() 不传参数 = 路由根

    if dec_verb == "ALL":
        pass  # ALL 匹配所有方法
    elif dec_verb != method.upper():
        return False

    return path_matches(dec_path, path)


def _express_matches(line: str, method: str, path: str) -> bool:
    """判断 Express/Fastify 函数式路由行是否与 (method, path) 匹配"""
    m = _EXPRESS_ROUTE_RE.match(line)
    if not m:
        return False

    dec_verb = m.group(1).upper()
    dec_path = m.group(2)

    if dec_verb != method.upper():
        return False

    return path_matches(dec_path, path)


# ────────────────────────────────────────────────────────────────
# 适配器实现
# ────────────────────────────────────────────────────────────────

_TS_EXTENSIONS = {".ts", ".js", ".tsx", ".mts", ".mjs"}

_EXCLUDE_DIRS = {
    ".git", "node_modules", "dist", "build", ".next", "out",
    "coverage", ".turbo", "__tests__", "test", "tests", "spec",
}


class NodejsTypescriptAdapter(FrameAdapter):
    """
    Node.js / TypeScript 路由适配器。

    覆盖：NestJS（装饰器）、Express、Fastify（函数式）及其变体。
    """

    NAME = "nodejs_typescript"
    LANGUAGES = [".ts", ".js", ".tsx", ".mts", ".mjs"]

    # ── 探针 ──────────────────────────────────────────────────

    @classmethod
    def can_handle(cls, source_path: Path) -> bool:
        """
        检测目标目录是否是 Node.js / TypeScript 后端项目。

        检测顺序：
          1. package.json 中 dependencies/devDependencies 包含已知框架
          2. 目录中存在 .ts / .js 文件（宽松兜底，避免误判纯前端项目）
        """
        # 信号1：递归查找 package.json（支持 monorepo 子包）
        for pkg_path in list(source_path.rglob("package.json"))[:5]:
            # 跳过 node_modules 中的 package.json
            if "node_modules" in pkg_path.parts:
                continue
            try:
                pkg = json.loads(pkg_path.read_text(encoding="utf-8", errors="ignore"))
                all_deps: dict = {}
                all_deps.update(pkg.get("dependencies", {}))
                all_deps.update(pkg.get("devDependencies", {}))
                if any(fw in all_deps for fw in _KNOWN_FRAMEWORKS):
                    return True
            except Exception:
                continue

        # 信号2：存在 TypeScript 文件（比纯 JS 项目更明确）
        return any(
            True
            for _ in source_path.rglob("*.ts")
            if "node_modules" not in str(_)
        )

    # ── 提取 ─────────────────────────────────────────────────

    def extract_route(self, method: str, path: str) -> RouteSnippet | None:
        """
        提取单条路由的完整函数/方法体。

        扫描顺序：
          1. NestJS 方法装饰器（@Get、@Post 等）
          2. Express/Fastify 函数式路由（router.get、fastify.post 等）
        """
        for ts_file in iter_source_files(self.source_path, _TS_EXTENSIONS, _EXCLUDE_DIRS):
            try:
                content = ts_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = content.splitlines()

            for i, line in enumerate(lines):
                stripped = line.strip()

                # 尝试 NestJS 装饰器匹配
                if stripped.startswith("@") and _nestjs_matches(line, method, path):
                    s_idx, e_idx = _extract_nestjs_method_body(lines, i)
                    return self._make_snippet(method, path, ts_file, lines, s_idx, e_idx)

                # 尝试 Express / Fastify 函数式匹配
                if not stripped.startswith("@") and _express_matches(line, method, path):
                    s_idx, e_idx = _extract_block_by_braces(lines, i)
                    return self._make_snippet(method, path, ts_file, lines, s_idx, e_idx)

        return None

    def _make_snippet(
        self,
        method: str,
        path: str,
        source_file: Path,
        lines: list[str],
        s_idx: int,
        e_idx: int,
    ) -> RouteSnippet:
        """组装 RouteSnippet 对象"""
        code = "\n".join(lines[s_idx: e_idx + 1])
        try:
            rel_path = str(source_file.relative_to(self.source_path))
        except ValueError:
            rel_path = str(source_file)

        return RouteSnippet(
            route_id=f"{method.upper()}:{path}",
            file_path=rel_path,
            start_line=s_idx + 1,
            end_line=e_idx + 1,
            code=code,
            adapter_name=self.NAME,
        )
