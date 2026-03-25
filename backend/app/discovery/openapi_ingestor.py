"""
OpenAPI 摄取器
从 /openapi.json 解析路由信息
"""

import json
import uuid
from datetime import datetime
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

        # 解析类型
        schema = param.get("schema", {})
        type_hint = schema.get("type", "string")
        if type_hint == "integer":
            type_hint = "int"
        elif type_hint == "number":
            type_hint = "float"
        elif type_hint == "boolean":
            type_hint = "bool"
        elif type_hint == "array":
            type_hint = "list"
        elif type_hint == "object":
            type_hint = "dict"

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

    def parse_request_body(
        self, request_body: dict[str, Any], schemas: dict[str, Any]
    ) -> str | None:
        """解析请求体引用"""
        content = request_body.get("content", {})
        for content_type, content_schema in content.items():
            if content_type.startswith("application/json"):
                ref = content_schema.get("schema", {}).get("$ref", "")
                if ref:
                    return ref.split("/")[-1]
        return None

    def parse_responses(self, responses: dict[str, Any]) -> list[ResponseSchema]:
        """解析响应定义"""
        result = []
        for status_code, response in responses.items():
            try:
                code = int(status_code)
            except ValueError:
                continue

            content_type = "application/json"
            schema_ref = None

            content = response.get("content", {})
            for ct, cs in content.items():
                content_type = ct
                if ct.startswith("application/json"):
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
                )
            )
        return result

    def parse_route(
        self,
        path: str,
        method: str,
        operation: dict[str, Any],
        path_params: list[dict[str, Any]],
    ) -> RouteInfo:
        """解析单个路由"""
        # 合并路径参数和操作参数
        all_params = path_params + operation.get("parameters", [])

        # 解析参数
        parameters = [self.parse_parameter(p) for p in all_params]

        # 解析请求体
        request_body_ref = None
        if "requestBody" in operation:
            request_body_ref = self.parse_request_body(
                operation["requestBody"], {}
            )

        # 解析响应
        responses = self.parse_responses(operation.get("responses", {}))

        # 解析安全要求
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
            responses=responses,
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
                        path, method, path_item[method], path_params
                    )
                    routes.append(route)

        # 生成版本号
        version = openapi_doc.get("info", {}).get("version", "1.0.0")

        return RouteMap(
            project_id=str(uuid.uuid4()),  # 临时 ID，调用方会覆盖
            version=version,
            base_url=self.base_url,
            routes=routes,
            schemas=schemas,
            discovered_at=datetime.utcnow().isoformat(),
            source="openapi",
        )


async def ingest_openapi(base_url: str, openapi_path: str = "/openapi.json") -> RouteMap:
    """便捷函数：摄取 OpenAPI 文档"""
    ingestor = OpenAPIIngestor(base_url, openapi_path)
    return await ingestor.ingest()
