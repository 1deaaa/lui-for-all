from __future__ import annotations

import asyncio

import pytest

from app.discovery.adapters.base import RouteSnippet
from app.discovery.semantic_ingestor import SemanticRouteIngestor
from app.schemas.route_map import ParameterLocation


def _ingest_single_snippet(monkeypatch, snippet: RouteSnippet):
    class FakeExtractor:
        def __init__(self, source_path: str):
            self.source_path = source_path

        def extract_all_routes(self):
            return [snippet]

    monkeypatch.setattr("app.discovery.semantic_ingestor.RouteExtractor", FakeExtractor)

    result = asyncio.run(
        SemanticRouteIngestor(source_path="/tmp/fake", base_url="http://localhost").ingest_with_snippets()
    )
    return result.route_map.routes[0]


def test_semantic_ingestor_extracts_path_and_body_fields_from_python_ast(monkeypatch) -> None:
    snippet = RouteSnippet(
        route_id="POST:/api/projects/{project_name}",
        file_path="server/story/routes_project.py",
        start_line=1,
        end_line=12,
        adapter_name="python_decorator",
        method="POST",
        path="/api/projects/{project_name}",
        code=(
            "@router.post('/api/projects/{project_name}')\n"
            "async def create_project(project_name: str, data: ProjectCreate, user: dict = Depends(get_current_user)):\n"
            "    normalized = normalize_project_name(data.projectName)\n"
            "    title = data.title\n"
            "    return {'ok': True}\n"
        ),
    )

    route = _ingest_single_snippet(monkeypatch, snippet)

    path_names = [p.name for p in route.parameters if p.location == ParameterLocation.PATH]
    body_names = [p.name for p in route.request_body_fields if p.location == ParameterLocation.BODY]

    assert path_names == ["project_name"]
    assert "projectName" in body_names
    assert "title" in body_names


def test_semantic_ingestor_dedupes_path_parameters(monkeypatch) -> None:
    snippet = RouteSnippet(
        route_id="GET:/api/demo/{item_id}/{item_id}",
        file_path="demo.py",
        start_line=1,
        end_line=3,
        adapter_name="python_decorator",
        method="GET",
        path="/api/demo/{item_id}/{item_id}",
        code=(
            "@router.get('/api/demo/{item_id}/{item_id}')\n"
            "async def get_demo(item_id: str):\n"
            "    return {'id': item_id}\n"
        ),
    )

    route = _ingest_single_snippet(monkeypatch, snippet)
    path_names = [p.name for p in route.parameters if p.location == ParameterLocation.PATH]

    assert path_names == ["item_id"]


@pytest.mark.parametrize(
    "snippet, expected_body_fields",
    [
        (
            RouteSnippet(
                route_id="POST:/api/projects/{project_id}",
                file_path="server.js",
                start_line=1,
                end_line=8,
                adapter_name="nodejs_typescript",
                method="POST",
                path="/api/projects/{project_id}",
                code=(
                    "app.post('/api/projects/{project_id}', (req, res) => {\n"
                    "  const { projectName, title } = req.body;\n"
                    "  const payload = req.body;\n"
                    "  return res.json({ name: payload.projectName, desc: payload.description });\n"
                    "});\n"
                ),
            ),
            {"projectName", "title", "description"},
        ),
        (
            RouteSnippet(
                route_id="POST:/api/projects/{project_id}",
                file_path="Program.cs",
                start_line=1,
                end_line=8,
                adapter_name="aspnet_core",
                method="POST",
                path="/api/projects/{project_id}",
                code=(
                    "app.MapPost(\"/api/projects/{project_id}\", (CreateProjectRequest request, string project_id) =>\n"
                    "{\n"
                    "    return Results.Ok(request.ProjectName);\n"
                    "});\n"
                ),
            ),
            {"ProjectName", "projectName"},
        ),
        (
            RouteSnippet(
                route_id="POST:/api/projects",
                file_path="SampleController.java",
                start_line=1,
                end_line=7,
                adapter_name="java_spring",
                method="POST",
                path="/api/projects",
                code=(
                    "@PostMapping(\"/api/projects\")\n"
                    "public String create(@RequestBody ProjectCreateRequest request) {\n"
                    "    return request.getProjectName();\n"
                    "}\n"
                ),
            ),
            {"projectName"},
        ),
        (
            RouteSnippet(
                route_id="POST:/api/projects/{project_id}",
                file_path="main.go",
                start_line=1,
                end_line=9,
                adapter_name="go_web",
                method="POST",
                path="/api/projects/{project_id}",
                code=(
                    "func CreateProject(c *gin.Context) {\n"
                    "    var req CreateProjectRequest\n"
                    "    _ = c.BindJSON(&req)\n"
                    "    _ = req.ProjectName\n"
                    "}\n"
                ),
            ),
            {"ProjectName", "projectName"},
        ),
        (
            RouteSnippet(
                route_id="POST:/api/projects",
                file_path="views.py",
                start_line=1,
                end_line=6,
                adapter_name="django_urlconf",
                method="POST",
                path="/api/projects",
                code=(
                    "def create_project(request):\n"
                    "    project_name = request.data.get('project_name')\n"
                    "    title = request.POST['title']\n"
                    "    return JsonResponse({'ok': True})\n"
                ),
            ),
            {"project_name", "title"},
        ),
    ],
)
def test_semantic_ingestor_extracts_body_fields_for_supported_adapters(
    monkeypatch,
    snippet: RouteSnippet,
    expected_body_fields: set[str],
) -> None:
    route = _ingest_single_snippet(monkeypatch, snippet)
    body_names = {p.name for p in route.request_body_fields if p.location == ParameterLocation.BODY}
    assert expected_body_fields.issubset(body_names)
