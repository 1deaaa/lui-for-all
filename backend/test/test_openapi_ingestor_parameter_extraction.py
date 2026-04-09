import asyncio
import importlib.util
from pathlib import Path


module_path = Path(__file__).resolve().parents[1] / "app" / "discovery" / "openapi_ingestor.py"
module_spec = importlib.util.spec_from_file_location("openapi_ingestor_module", module_path)
if not module_spec or not module_spec.loader:
    raise RuntimeError("无法加载 openapi_ingestor 模块")
openapi_ingestor_module = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(openapi_ingestor_module)
OpenAPIIngestor = openapi_ingestor_module.OpenAPIIngestor


class _StubIngestor(OpenAPIIngestor):
    def __init__(self, spec: dict):
        super().__init__(base_url="http://example.com")
        self._spec = spec

    async def fetch_openapi(self) -> dict:
        return self._spec


def test_openapi_ingestor_resolves_parameter_and_request_body_refs():
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "demo", "version": "1.0.0"},
        "components": {
            "parameters": {
                "UserIdParam": {
                    "name": "user_id",
                    "in": "path",
                    # 故意不写 required，验证 path 参数会被强制为必填
                    "schema": {"type": "string"},
                },
                "TenantHeader": {
                    "name": "tenant_id",
                    "in": "header",
                    "required": True,
                    "schema": {"type": "string"},
                },
            },
            "requestBodies": {
                "UpdateUserBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/UpdateUserRequest"}
                        }
                    },
                }
            },
            "schemas": {
                "UpdateUserRequest": {
                    "type": "object",
                    "required": ["username", "password"],
                    "properties": {
                        "username": {"type": "string"},
                        "password": {"type": "string"},
                        "age": {"type": "integer", "default": 18},
                    },
                }
            },
        },
        "paths": {
            "/api/users/{user_id}": {
                "parameters": [{"$ref": "#/components/parameters/UserIdParam"}],
                "patch": {
                    "operationId": "updateUser",
                    "parameters": [
                        {"$ref": "#/components/parameters/TenantHeader"},
                        {
                            "name": "verbose",
                            "in": "query",
                            "schema": {"type": "boolean", "default": False},
                        },
                    ],
                    "requestBody": {"$ref": "#/components/requestBodies/UpdateUserBody"},
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        }
                    },
                },
            }
        },
    }

    route_map = asyncio.run(_StubIngestor(spec).ingest())
    route = next(r for r in route_map.routes if r.route_id == "PATCH:/api/users/{user_id}")

    params = {(p.name, p.location.value): p for p in route.parameters}
    assert ("user_id", "path") in params
    assert ("tenant_id", "header") in params
    assert ("verbose", "query") in params

    assert params[("user_id", "path")].required is True
    assert params[("tenant_id", "header")].required is True
    assert params[("verbose", "query")].default is False

    body_fields = {p.name: p for p in route.request_body_fields}
    assert set(body_fields.keys()) == {"username", "password", "age"}
    assert body_fields["username"].required is True
    assert body_fields["password"].required is True
    assert body_fields["age"].required is False
    assert body_fields["age"].default == 18
