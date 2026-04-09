from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.discovery.route_extractor import RouteExtractor


def test_node_adapter_resolves_member_handler_to_full_implementation(tmp_path) -> None:
    (tmp_path / "package.json").write_text(
        '{"name":"sample","dependencies":{"express":"^4.19.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "server.js").write_text(
        "const express = require('express');\n"
        "const app = express();\n"
        "\n"
        "class ProjectController {\n"
        "  create(req, res) {\n"
        "    const projectName = req.body.projectName;\n"
        "    return res.json({ ok: true, projectName });\n"
        "  }\n"
        "}\n"
        "\n"
        "const controller = new ProjectController();\n"
        "app.post('/api/projects', controller.create);\n",
        encoding="utf-8",
    )

    extractor = RouteExtractor(str(tmp_path))
    assert extractor.adapter_name == "nodejs_typescript"

    batch = extractor.extract_batch([("POST", "/api/projects")])
    snippet = batch.get("POST:/api/projects")

    assert snippet is not None
    assert "create(req, res)" in snippet.code
    assert "projectName" in snippet.code


def test_aspnet_adapter_resolves_map_method_group_to_local_function(tmp_path) -> None:
    (tmp_path / "Sample.csproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk.Web\"></Project>",
        encoding="utf-8",
    )
    (tmp_path / "Program.cs").write_text(
        "var builder = WebApplication.CreateBuilder(args);\n"
        "var app = builder.Build();\n"
        "\n"
        "app.MapPost(\"/api/projects\", CreateProject);\n"
        "\n"
        "IResult CreateProject(CreateProjectRequest request)\n"
        "{\n"
        "    return Results.Ok(request.ProjectName);\n"
        "}\n"
        "\n"
        "record CreateProjectRequest(string ProjectName);\n",
        encoding="utf-8",
    )

    extractor = RouteExtractor(str(tmp_path))
    assert extractor.adapter_name == "aspnet_core"

    batch = extractor.extract_batch([("POST", "/api/projects")])
    snippet = batch.get("POST:/api/projects")

    assert snippet is not None
    assert "CreateProject(CreateProjectRequest request)" in snippet.code
    assert "request.ProjectName" in snippet.code


def test_go_adapter_resolves_receiver_handler_to_method_implementation(tmp_path) -> None:
    (tmp_path / "go.mod").write_text(
        "module sample\n\n"
        "go 1.22\n\n"
        "require github.com/gin-gonic/gin v1.10.0\n",
        encoding="utf-8",
    )
    (tmp_path / "main.go").write_text(
        "package main\n"
        "\n"
        "import \"github.com/gin-gonic/gin\"\n"
        "\n"
        "type Handler struct{}\n"
        "\n"
        "func (h *Handler) CreateProject(c *gin.Context) {\n"
        "    var req struct {\n"
        "        ProjectName string `json:\"projectName\"`\n"
        "    }\n"
        "    _ = c.BindJSON(&req)\n"
        "    c.JSON(200, gin.H{\"projectName\": req.ProjectName})\n"
        "}\n"
        "\n"
        "func main() {\n"
        "    r := gin.Default()\n"
        "    h := &Handler{}\n"
        "    r.POST(\"/api/projects\", h.CreateProject)\n"
        "}\n",
        encoding="utf-8",
    )

    extractor = RouteExtractor(str(tmp_path))
    assert extractor.adapter_name == "go_web"

    batch = extractor.extract_batch([("POST", "/api/projects")])
    snippet = batch.get("POST:/api/projects")

    assert snippet is not None
    assert "func (h *Handler) CreateProject" in snippet.code
    assert "req.ProjectName" in snippet.code
