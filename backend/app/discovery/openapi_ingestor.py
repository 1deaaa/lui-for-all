"""
OpenAPI 摄取器
从 /openapi.json 解析路由信息
"""

import json
import uuid
from datetime import datetime, UTC
from typing import Any

import httpx

from app.config import settings
from app.schemas.route_map import (
    HttpMethod,
    ParameterLocation,
    ParameterSchema,
    ResponseSchema,
    RouteInfo,
    RouteMap,
)


class OpenAPIIngestor:
    """OpenAPI 文档摄取器"""

    def __init__(self, base_url: str, openapi_path: str = "/openapi.json"):
        self.base_url = base_url.rstrip("/")
        self.openapi_url = f"{self.base_url}{openapi_path}"

    async def fetch_openapi(self) -> dict[str, Any]:
        """获取 OpenAPI 文档"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.openapi_url)
            response.raise_for_status()
            return response.json()

    def parse_parameter(self, param: dict[str, Any]) -> ParameterSchema:
        """解析参数定义"""
        location_map = {
            "path": ParameterLocation.PATH,
            "query": ParameterLocation.QUERY,
            "header": ParameterLocation.HEADER,
            "cookie": ParameterLocation.COOKIE,
        }

        schema = param.get("schema", {})
        type_hint = self._schema_type_hint(schema)

        return ParameterSchema(
            name=param.get("name", ""),
            location=location_map.get(
                param.get("in", "query"), ParameterLocation.QUERY
            ),
            required=param.get("required", False),
            type_hint=type_hint,
            description=param.get("description"),
            default=param.get("default"),
            example=param.get("example"),
        )

    def _normalize_type_hint(self, raw_type: str | None) -> str:
        """统一 OpenAPI 类型到内部 type_hint。"""
        type_map = {
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "array": "list",
            "object": "dict",
            "string": "str",
        }
        return type_map.get((raw_type or "").lower(), "str")

    def _schema_type_hint(self, schema: dict[str, Any]) -> str:
        """从 schema 结构推断类型提示。"""
        if not schema:
            return "str"

        raw_type = schema.get("type")
        if raw_type:
            return self._normalize_type_hint(raw_type)

        if "$ref" in schema:
            return "dict"

        for key in ("anyOf", "oneOf", "allOf"):
            variants = schema.get(key)
            if isinstance(variants, list):
                for item in variants:
                    hint = self._schema_type_hint(item)
                    if hint != "str":
                        return hint

        return "str"

    def _expand_schema_fields(
        self, schema_name: str, schemas: dict[str, Any]
    ) -> list[ParameterSchema]:
        """将 Schema 引用展开为具体字段列表"""
        schema_def = schemas.get(schema_name, {})
        properties = schema_def.get("properties", {})
        required_fields = set(schema_def.get("required", []))
        fields: list[ParameterSchema] = []

        for field_name, field_def in properties.items():
            type_hint = self._schema_type_hint(field_def)

            fields.append(
                ParameterSchema(
                    name=field_name,
                    location=ParameterLocation.BODY,
                    required=field_name in required_fields,
                    type_hint=type_hint,
                    description=field_def.get("description"),
                    default=field_def.get("default"),
                    example=field_def.get("example"),
                )
            )

        return fields

    def _extract_request_body_fields(
        self,
        schema_obj: dict[str, Any],
        schemas: dict[str, Any],
    ) -> list[ParameterSchema]:
        """从请求体 schema（含 inline / $ref / allOf 等）提取顶层字段。"""
        if not schema_obj:
            return []

        # 1) 直接引用组件 schema
        ref = schema_obj.get("$ref")
        if ref:
            schema_name = ref.split("/")[-1]
            return self._expand_schema_fields(schema_name, schemas)

        # 2) inline object
        if schema_obj.get("type") == "object":
            properties = schema_obj.get("properties", {})
            required_fields = set(schema_obj.get("required", []))
            fields: list[ParameterSchema] = []
            for field_name, field_def in properties.items():
                fields.append(
                    ParameterSchema(
                        name=field_name,
                        location=ParameterLocation.BODY,
                        required=field_name in required_fields,
                        type_hint=self._schema_type_hint(field_def),
                        description=field_def.get("description"),
                        default=field_def.get("default"),
                        example=field_def.get("example"),
                    )
                )
            return fields

        # 3) 组合 schema（allOf/oneOf/anyOf）
        for key in ("allOf", "oneOf", "anyOf"):
            variants = schema_obj.get(key)
            if not isinstance(variants, list):
                continue

            merged: list[ParameterSchema] = []
            seen_names: set[str] = set()
            for item in variants:
                for field in self._extract_request_body_fields(item, schemas):
                    if field.name in seen_names:
                        continue
                    seen_names.add(field.name)
                    merged.append(field)
            if merged:
                return merged

        return []

    def parse_request_body(
        self, request_body: dict[str, Any], schemas: dict[str, Any]
    ) -> tuple[str | None, list[ParameterSchema]]:
        """解析请求体：返回 (schema_ref_name, 展开字段列表)"""
        content = request_body.get("content", {})
        for content_type, content_schema in content.items():
            if not (
                content_type.startswith("application/json")
                or content_type.startswith("application/x-www-form-urlencoded")
                or content_type.startswith("multipart/form-data")
            ):
                continue

            schema_obj = content_schema.get("schema", {}) or {}
            schema_name = None
            if "$ref" in schema_obj:
                schema_name = schema_obj["$ref"].split("/")[-1]

            expanded = self._extract_request_body_fields(schema_obj, schemas)
            return schema_name, expanded
        return None, []

    def parse_responses(self, responses: dict[str, Any]) -> tuple[list[ResponseSchema], bool]:
        """解析响应定义，同时检测是否有 SSE 流式响应"""
        result = []
        has_streaming = False

        for status_code, response in responses.items():
            try:
                code = int(status_code)
            except ValueError:
                continue

            content_type = "application/json"
            schema_ref = None
            is_streaming = False

            content = response.get("content", {})
            for ct, cs in content.items():
                content_type = ct
                if ct == "text/event-stream":
                    is_streaming = True
                    has_streaming = True
                elif ct.startswith("application/json"):
                    schema_ref = cs.get("schema", {}).get("$ref", "")
                    if schema_ref:
                        schema_ref = schema_ref.split("/")[-1]
                break

            result.append(
                ResponseSchema(
                    status_code=code,
                    content_type=content_type,
                    schema_ref=schema_ref,
                    description=response.get("description"),
                    is_streaming=is_streaming,
                )
            )
        return result, has_streaming

    def parse_route(
        self,
        path: str,
        method: str,
        operation: dict[str, Any],
        path_params: list[dict[str, Any]],
        schemas: dict[str, Any],
    ) -> RouteInfo:
        """解析单个路由"""
        # 合并路径参数和操作参数
        all_params = path_params + operation.get("parameters", [])
        parameters = [self.parse_parameter(p) for p in all_params]

        # 解析请求体（含字段展开）
        request_body_ref = None
        request_body_fields: list = []
        if "requestBody" in operation:
            request_body_ref, request_body_fields = self.parse_request_body(
                operation["requestBody"], schemas
            )

        # 解析响应（含 SSE 检测）
        responses, response_is_streaming = self.parse_responses(operation.get("responses", {}))

        security = operation.get("security", [])

        return RouteInfo(
            route_id=f"{method.upper()}:{path}",
            path=path,
            method=HttpMethod(method.upper()),
            operation_id=operation.get("operationId"),
            summary=operation.get("summary"),
            description=operation.get("description"),
            tags=operation.get("tags", []),
            parameters=parameters,
            request_body_ref=request_body_ref,
            request_body_fields=request_body_fields,
            responses=responses,
            response_is_streaming=response_is_streaming,
            deprecated=operation.get("deprecated", False),
            security=security,
        )

    async def ingest(self) -> RouteMap:
        """执行 OpenAPI 摄取"""
        openapi_doc = await self.fetch_openapi()

        # 提取 schemas
        schemas = openapi_doc.get("components", {}).get("schemas", {})

        # 解析路由
        routes: list[RouteInfo] = []
        paths = openapi_doc.get("paths", {})

        for path, path_item in paths.items():
            # 提取路径级参数
            path_params = path_item.get("parameters", [])

            # 解析各 HTTP 方法
            for method in ["get", "post", "put", "delete", "patch", "head", "options"]:
                if method in path_item:
                    route = self.parse_route(
                        path, method, path_item[method], path_params, schemas
                    )
                    routes.append(route)

        # 生成版本号
        version = openapi_doc.get("info", {}).get("version", "1.0.0")

        print(f"\n[OpenAPIIngestor] 🔍 OpenAPI 解析完成，共发现 {len(routes)} 个接口端点")

        return RouteMap(
            project_id=str(uuid.uuid4()),  # 临时 ID，调用方会覆盖
            version=version,
            base_url=self.base_url,
            routes=routes,
            schemas=schemas,
            discovered_at=datetime.now(UTC).isoformat(),
            source="openapi",
        )


async def ingest_openapi(base_url: str, openapi_path: str = "/openapi.json") -> RouteMap:
    """便捷函数：摄取 OpenAPI 文档"""
    ingestor = OpenAPIIngestor(base_url, openapi_path)
    return await ingestor.ingest()
