"""
路由地图 Schema
定义从 OpenAPI 提取的路由物理声明
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HttpMethod(str, Enum):
    """HTTP 方法枚举"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ParameterLocation(str, Enum):
    """参数位置"""

    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"
    BODY = "body"


class ParameterSchema(BaseModel):
    """参数定义"""

    name: str = Field(description="参数名称")
    location: ParameterLocation = Field(description="参数位置")
    required: bool = Field(default=False, description="是否必需")
    type_hint: str = Field(default="str", description="类型提示")
    description: str | None = Field(default=None, description="参数描述")
    default: Any | None = Field(default=None, description="默认值")
    example: Any | None = Field(default=None, description="示例值")


class ResponseSchema(BaseModel):
    """响应定义"""

    status_code: int = Field(description="HTTP 状态码")
    content_type: str = Field(default="application/json", description="内容类型")
    schema_ref: str | None = Field(default=None, description="响应 Schema 引用")
    description: str | None = Field(default=None, description="响应描述")
    is_streaming: bool = Field(default=False, description="是否为 SSE 流式响应 (text/event-stream)")


class RouteInfo(BaseModel):
    """单个路由信息"""

    route_id: str = Field(description="路由唯一标识 (method:path)")
    path: str = Field(description="路由路径")
    method: HttpMethod = Field(description="HTTP 方法")
    operation_id: str | None = Field(default=None, description="OpenAPI operationId")
    summary: str | None = Field(default=None, description="路由摘要")
    description: str | None = Field(default=None, description="路由描述")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    parameters: list[ParameterSchema] = Field(
        default_factory=list, description="参数列表"
    )
    request_body_ref: str | None = Field(default=None, description="请求体 Schema 引用")
    request_body_fields: list[ParameterSchema] = Field(
        default_factory=list,
        description="请求体展开字段（从 Schema 解析出的具体字段列表，POST/PUT/PATCH 时有值）",
    )
    responses: list[ResponseSchema] = Field(default_factory=list, description="响应列表")
    response_is_streaming: bool = Field(
        default=False,
        description="是否包含 SSE 流式响应（任意 200 响应的 content_type 为 text/event-stream）",
    )
    deprecated: bool = Field(default=False, description="是否已废弃")
    security: list[dict[str, list[str]]] = Field(
        default_factory=list, description="安全要求"
    )


class RouteMap(BaseModel):
    """路由地图 - 项目所有路由的集合"""

    project_id: str = Field(description="项目 ID")
    version: str = Field(description="路由地图版本")
    base_url: str = Field(description="API 基础 URL")
    routes: list[RouteInfo] = Field(default_factory=list, description="路由列表")
    schemas: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="OpenAPI Schemas 定义"
    )
    discovered_at: str = Field(description="发现时间 (ISO 格式)")
    source: str = Field(default="openapi", description="发现来源")
