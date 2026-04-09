"""
语义路由摄取器（无 OpenAPI 兜底）
=================================

当目标系统未暴露 OpenAPI 时，使用 Tree-sitter 适配器直接从源码提取路由，
并生成 RouteMap，供后续能力建图流水线复用。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.discovery.route_extractor import RouteExtractor, RouteSnippet
from app.schemas.route_map import (
    HttpMethod,
    ParameterLocation,
    ParameterSchema,
    RouteInfo,
    RouteMap,
)


_ACTION_MAP = {
    "GET": "查询",
    "POST": "创建",
    "PUT": "更新",
    "PATCH": "修改",
    "DELETE": "删除",
    "HEAD": "读取",
    "OPTIONS": "探测",
}

_PYTHON_BODY_FIELD_BLACKLIST = {
    "dict",
    "json",
    "model_dump",
    "model_dump_json",
    "copy",
    "items",
    "keys",
    "values",
    "get",
    "setdefault",
    "pop",
    "update",
}

_COMMON_BODY_FIELD_BLACKLIST = {
    "dict",
    "json",
    "items",
    "keys",
    "values",
    "get",
    "setdefault",
    "pop",
    "update",
    "copy",
    "to_string",
    "toString",
    "hashCode",
    "equals",
    "getClass",
    "class",
    "len",
}

_JAVA_BODY_METHOD_BLACKLIST = {
    "toString",
    "hashCode",
    "equals",
    "getClass",
    "wait",
    "notify",
    "notifyAll",
}

_CSHARP_SERVICE_TYPE_TOKENS = {
    "string",
    "char",
    "bool",
    "byte",
    "short",
    "int",
    "long",
    "float",
    "double",
    "decimal",
    "guid",
    "datetime",
    "datetimeoffset",
    "timespan",
    "cancellationtoken",
    "httpcontext",
    "httprequest",
    "httpresponse",
    "claimsprincipal",
    "iresult",
    "results",
}

_TYPE_WRAPPER_TOKENS = {
    "annotated",
    "optional",
    "union",
    "literal",
    "list",
    "dict",
    "tuple",
    "set",
    "sequence",
    "mapping",
    "any",
    "object",
    "str",
    "int",
    "float",
    "bool",
    "bytes",
    "none",
}


def _summary_from_method_path(method: str, path: str) -> str:
    action = _ACTION_MAP.get(method.upper(), "操作")
    tail = path.strip("/").split("/")[-1] if path and path != "/" else "根路由"
    return f"{action}{tail}"


def _extract_path_parameters(path: str) -> list[ParameterSchema]:
    """从路由模板中提取 path 参数。"""
    names = re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", path or "")
    deduped: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        deduped.append(name)

    return [
        ParameterSchema(
            name=name,
            location=ParameterLocation.PATH,
            required=True,
            type_hint="str",
            description=f"AST 推断的路径参数: {name}",
        )
        for name in deduped
    ]


def _to_body_parameter_schemas(
    field_names: set[str],
    path_param_names: set[str],
) -> list[ParameterSchema]:
    """将推断出的字段名转换为标准请求体参数结构。"""
    filtered: list[str] = []
    for field in sorted(field_names):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field):
            continue
        if field in path_param_names:
            continue
        if field in _COMMON_BODY_FIELD_BLACKLIST:
            continue
        filtered.append(field)

    return [
        ParameterSchema(
            name=field,
            location=ParameterLocation.BODY,
            required=True,
            type_hint="str",
            description=f"AST 推断的请求体字段: {field}",
        )
        for field in filtered
    ]


def _split_signature_parameters(signature: str) -> list[str]:
    """按顶层逗号切分函数签名参数，规避泛型/调用中的逗号干扰。"""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in signature:
        if ch in "([{" :
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)

        if ch == "," and depth == 0:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            continue

        buf.append(ch)

    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _looks_like_model_annotation(annotation: str) -> bool:
    """判断注解是否可能是请求体模型类型。"""
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", annotation or "")
    if not tokens:
        return False

    for token in tokens:
        lower = token.lower()
        if lower in _TYPE_WRAPPER_TOKENS:
            continue
        if token[:1].isupper():
            return True
    return False


def _extract_python_body_fields(
    snippet: RouteSnippet,
    path_param_names: set[str],
) -> list[ParameterSchema]:
    """从 Python 装饰器路由函数体中推断请求体字段。"""
    code = snippet.code or ""
    signature_match = re.search(r"(?:async\s+)?def\s+\w+\s*\((.*?)\)\s*:", code, re.DOTALL)
    if not signature_match:
        return []

    signature = signature_match.group(1)
    model_vars: list[str] = []

    for raw_param in _split_signature_parameters(signature):
        param = raw_param.strip()
        if not param or param.startswith("*"):
            continue

        name_match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", param)
        if not name_match:
            continue
        name = name_match.group(1)

        if "Depends(" in param:
            continue

        if "Body(" in param:
            model_vars.append(name)
            continue

        annotation_match = re.search(r":\s*([^=]+)", param)
        if not annotation_match:
            continue

        annotation = annotation_match.group(1).strip()
        if _looks_like_model_annotation(annotation):
            model_vars.append(name)

    if not model_vars:
        return []

    fields: set[str] = set()
    for var in model_vars:
        pattern = re.compile(rf"\b{re.escape(var)}\.([A-Za-z_][A-Za-z0-9_]*)\b")
        for field in pattern.findall(code):
            if field in _PYTHON_BODY_FIELD_BLACKLIST:
                continue
            fields.add(field)

    return _to_body_parameter_schemas(fields, path_param_names)


def _extract_nodejs_body_fields(
    snippet: RouteSnippet,
    path_param_names: set[str],
) -> list[ParameterSchema]:
    """从 Node.js/TypeScript 路由函数体中推断请求体字段。"""
    code = snippet.code or ""
    fields: set[str] = set()

    for field in re.findall(r"\b(?:req|request)\.body\.([A-Za-z_][A-Za-z0-9_]*)\b", code):
        fields.add(field)

    for raw_block in re.findall(
        r"(?:const|let|var)\s*\{([^}]+)\}\s*=\s*(?:req|request)\.body\b",
        code,
    ):
        for raw_name in raw_block.split(","):
            name = raw_name.strip().split(":", 1)[0].split("=", 1)[0].strip()
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                fields.add(name)

    body_vars: set[str] = set(
        re.findall(r"(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:req|request)\.body\b", code)
    )
    body_vars.update(re.findall(r"@Body\s*\([^)]*\)\s*([A-Za-z_][A-Za-z0-9_]*)", code))

    for var in body_vars:
        pattern = re.compile(rf"\b{re.escape(var)}\.([A-Za-z_][A-Za-z0-9_]*)\b")
        for field in pattern.findall(code):
            fields.add(field)

    return _to_body_parameter_schemas(fields, path_param_names)


def _java_getter_to_field(raw: str) -> str:
    if not raw:
        return raw
    return raw[0].lower() + raw[1:]


def _extract_java_body_fields(
    snippet: RouteSnippet,
    path_param_names: set[str],
) -> list[ParameterSchema]:
    """从 Java Spring 路由函数体中推断请求体字段。"""
    code = snippet.code or ""
    fields: set[str] = set()

    body_vars = set(
        re.findall(
            r"@RequestBody\s+[A-Za-z_][A-Za-z0-9_<>\[\],.?]*\s+([A-Za-z_][A-Za-z0-9_]*)",
            code,
        )
    )
    if not body_vars:
        return []

    for var in body_vars:
        for getter in re.findall(rf"\b{re.escape(var)}\.get([A-Z][A-Za-z0-9_]*)\s*\(", code):
            fields.add(_java_getter_to_field(getter))

        for getter in re.findall(rf"\b{re.escape(var)}\.is([A-Z][A-Za-z0-9_]*)\s*\(", code):
            fields.add(_java_getter_to_field(getter))

        for method_name in re.findall(rf"\b{re.escape(var)}\.([a-z][A-Za-z0-9_]*)\s*\(", code):
            if method_name in _JAVA_BODY_METHOD_BLACKLIST:
                continue
            fields.add(method_name)

    return _to_body_parameter_schemas(fields, path_param_names)


def _looks_like_csharp_complex_type(type_part: str) -> bool:
    token = (type_part or "").strip()
    if not token:
        return False

    token = token.replace("?", "")
    token = token.split("<", 1)[0]
    token = token.split(".")[-1]
    if not token:
        return False

    if token.lower() in _CSHARP_SERVICE_TYPE_TOKENS:
        return False
    return token[:1].isupper()


def _extract_csharp_body_fields(
    snippet: RouteSnippet,
    path_param_names: set[str],
) -> list[ParameterSchema]:
    """从 ASP.NET Core 路由函数体中推断请求体字段。"""
    code = snippet.code or ""
    fields: set[str] = set()

    body_vars = set(
        re.findall(
            r"\[FromBody\]\s*[A-Za-z_][A-Za-z0-9_<>\[\],.?\s]*\s+([A-Za-z_][A-Za-z0-9_]*)",
            code,
        )
    )

    lambda_signatures = re.findall(r"\(([^()]+)\)\s*=>", code, re.DOTALL)
    if lambda_signatures:
        signature = lambda_signatures[-1]
        for raw_param in _split_signature_parameters(signature):
            param = re.sub(r"\[[^\]]+\]", "", raw_param).strip()
            if not param:
                continue

            name_match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*$", param)
            if not name_match:
                continue

            name = name_match.group(1)
            if name in path_param_names:
                continue

            type_part = param[: name_match.start()].strip()
            if _looks_like_csharp_complex_type(type_part):
                body_vars.add(name)

    for var in body_vars:
        for field in re.findall(rf"\b{re.escape(var)}\.([A-Za-z_][A-Za-z0-9_]*)\b", code):
            if field in {"ToString", "GetType", "Equals", "GetHashCode"}:
                continue
            fields.add(field)
            if field[:1].isupper() and len(field) > 1:
                fields.add(field[0].lower() + field[1:])

    return _to_body_parameter_schemas(fields, path_param_names)


def _extract_go_body_fields(
    snippet: RouteSnippet,
    path_param_names: set[str],
) -> list[ParameterSchema]:
    """从 Go 路由函数体中推断请求体字段。"""
    code = snippet.code or ""
    fields: set[str] = set()

    body_vars = set(
        re.findall(
            r"(?:BindJSON|ShouldBindJSON|Decode|BodyParser)\s*\(\s*&([A-Za-z_][A-Za-z0-9_]*)\s*\)",
            code,
        )
    )

    for var in body_vars:
        for field in re.findall(rf"\b{re.escape(var)}\.([A-Za-z_][A-Za-z0-9_]*)\b", code):
            fields.add(field)
            if field[:1].isupper() and len(field) > 1:
                fields.add(field[0].lower() + field[1:])

    return _to_body_parameter_schemas(fields, path_param_names)


def _extract_django_body_fields(
    snippet: RouteSnippet,
    path_param_names: set[str],
) -> list[ParameterSchema]:
    """从 Django 视图函数体中推断请求体字段。"""
    code = snippet.code or ""
    fields: set[str] = set()

    patterns = [
        r"request\.data\.get\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",
        r"request\.POST\.get\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",
        r"request\.data\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]",
        r"request\.POST\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]",
    ]

    for pattern in patterns:
        fields.update(re.findall(pattern, code))

    return _to_body_parameter_schemas(fields, path_param_names)


def _extract_request_body_fields(
    snippet: RouteSnippet,
    path_param_names: set[str],
) -> list[ParameterSchema]:
    adapter = (snippet.adapter_name or "").lower()
    if adapter.startswith("python"):
        return _extract_python_body_fields(snippet, path_param_names)
    if adapter == "nodejs_typescript":
        return _extract_nodejs_body_fields(snippet, path_param_names)
    if adapter == "java_spring":
        return _extract_java_body_fields(snippet, path_param_names)
    if adapter == "aspnet_core":
        return _extract_csharp_body_fields(snippet, path_param_names)
    if adapter == "go_web":
        return _extract_go_body_fields(snippet, path_param_names)
    if adapter == "django_urlconf":
        return _extract_django_body_fields(snippet, path_param_names)
    return []


@dataclass
class SemanticIngestResult:
    """AST 语义摄取结果：路由地图 + 可复用源码片段。"""

    route_map: RouteMap
    route_snippets_by_route_id: dict[str, RouteSnippet]


class SemanticRouteIngestor:
    """基于 AST 的路由摄取器。"""

    def __init__(self, source_path: str, base_url: str = ""):
        self.source_path = source_path
        self.base_url = (base_url or "").rstrip("/")

    async def ingest(self) -> RouteMap:
        result = await self.ingest_with_snippets()
        return result.route_map

    async def ingest_with_snippets(self) -> SemanticIngestResult:
        extractor = RouteExtractor(self.source_path)
        snippets = extractor.extract_all_routes()

        if not snippets:
            raise ValueError(
                "未能从源码中提取任何路由，请检查 source_path 是否正确或补充适配器。"
            )

        routes: list[RouteInfo] = []
        seen_route_ids: set[str] = set()
        snippet_index: dict[str, RouteSnippet] = {}

        for snippet in snippets:
            method = snippet.method.upper()
            try:
                http_method = HttpMethod(method)
            except ValueError:
                continue

            route_id = f"{method}:{snippet.path}"

            best_snippet = snippet_index.get(route_id)
            if best_snippet is None or len(snippet.code) > len(best_snippet.code):
                snippet_index[route_id] = snippet

            if route_id in seen_route_ids:
                continue
            seen_route_ids.add(route_id)

            path_parameters = _extract_path_parameters(snippet.path)
            path_param_names = {param.name for param in path_parameters}
            request_body_fields = _extract_request_body_fields(
                snippet,
                path_param_names,
            )

            routes.append(
                RouteInfo(
                    route_id=route_id,
                    path=snippet.path,
                    method=http_method,
                    operation_id=None,
                    summary=_summary_from_method_path(method, snippet.path),
                    description=(
                        f"由 {snippet.adapter_name} 从源码 {snippet.file_path}:"
                        f"{snippet.start_line}-{snippet.end_line} 提取"
                    ),
                    tags=["ast"],
                    parameters=path_parameters,
                    request_body_ref=None,
                    request_body_fields=request_body_fields,
                    responses=[],
                    response_is_streaming=False,
                    deprecated=False,
                    security=[],
                )
            )

        version = f"ast-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        route_map = RouteMap(
            project_id=str(uuid.uuid4()),
            version=version,
            base_url=self.base_url,
            routes=routes,
            schemas={},
            discovered_at=datetime.now(UTC).isoformat(),
            source="ast",
        )
        return SemanticIngestResult(
            route_map=route_map,
            route_snippets_by_route_id=snippet_index,
        )


async def ingest_semantic_routes(source_path: str, base_url: str = "") -> RouteMap:
    """便捷函数：执行 AST 语义路由摄取。"""
    ingestor = SemanticRouteIngestor(source_path=source_path, base_url=base_url)
    return await ingestor.ingest()


async def ingest_semantic_routes_with_snippets(
    source_path: str,
    base_url: str = "",
) -> SemanticIngestResult:
    """便捷函数：执行 AST 语义路由摄取并返回可复用片段缓存。"""
    ingestor = SemanticRouteIngestor(source_path=source_path, base_url=base_url)
    return await ingestor.ingest_with_snippets()
