<div align="center">

# LUI-for-All

**Operate any system with natural language.**

*Language User Interface · Zero-Intrusion Integration · Enterprise-Grade Safety*
</div>

---

> Languages: [简体中文](README.md) | **English** | [日本語](README.ja-JP.md)

## What Problem Does It Solve?

Many backend systems, especially enterprise and internal-operation systems, are powerful but hard to use. Users must navigate complex menus, remember filter combinations, and fill repetitive forms to finish tasks that can be described in one sentence.

**LUI-for-All** adds a natural-language operation layer next to your existing system in an isolated folder, without touching your current codebase.

```text
User: "List all purchase requests pending approval from last week,
sorted by amount descending, and highlight items above 50,000."

LUI: [Understand intent -> call existing APIs -> render table + highlights]
     ✓ No modifications to your existing system code
```

## Core Highlights

1. Zero-intrusion integration and easy removal
- Runs as an isolated folder beside your project
- Uses read-only access to existing code by default
- Runtime write operations are isolated in `workspace/`

2. Hybrid discovery: OpenAPI + Tree-sitter AST
- OpenAPI-first ingestion for fast, structured route discovery
- Unified AST extraction layer (`FrameAdapter + get_tree_sitter_query`) for full handler implementation capture
- Built-in adapters for mainstream backends: Python (FastAPI/Flask/Sanic), Node.js (NestJS/Express/Fastify), Java (Spring Boot), C# (ASP.NET Core), and Go (Gin/Echo/Fiber/chi)
- Automatic AST fallback when OpenAPI is unavailable, using `source_path`
- Route parameter normalization across frameworks (for example, `:id -> {id}`) to improve matching quality

### Representative Syntax Coverage (7 Samples)

The repository now includes 7 representative backend samples with validated two-level extraction (route discovery + handler/function implementation extraction).

| Representative sample | Route style family | Verified coverage (current adapters) | Theoretical transfer (requires adapter extension) |
|---|---|---|---|
| `fastapi_sample` | Python decorator routes (`@router.get`, `@app.post`) | FastAPI, Flask, Sanic, Starlette, Litestar, Falcon, aiohttp, Tornado, Bottle, Quart | Ruby Sinatra/Grape, PHP Slim |
| `node_sample` | Node call-chain routing (`app.get()`, `router.post()`) | Express, Fastify, Koa Router, Hono, Elysia, Restify, hapi | PHP Laravel/Lumen/Slim, Ruby Hanami |
| `django_sample` | Central URLConf (`path/re_path/include`) | Django, Django REST Framework | Ruby on Rails (`routes.rb`), PHP Laravel (`routes/web.php`) |
| `springboot_sample` | Controller annotations (class prefix + method mapping) | Java Spring Boot, Spring MVC | C# ASP.NET Core attribute controllers, PHP Symfony attribute routes |
| `aspnetcore_sample` | Minimal API mapping (`MapGet/MapPost/MapMethods`) | ASP.NET Core Minimal API | Java Javalin/Spark, Go net/http + mux |
| `go_gin_sample` | Grouped chain registration (`Group + METHOD(path, handler)`) | Gin, Echo, Fiber, Chi | Rust Actix/Axum, PHP Slim |
| `node_native_sample` | No-framework manual routing table (method/path -> handler) | Node.js built-in http | Python wsgiref/werkzeug manual routing, Ruby Rack, PHP Swoole native dispatch |

Notes:

- "Verified coverage" corresponds to repository tests in `backend/test/test_route_extractor_representative_samples.py`.
- "Theoretical transfer" means the syntax pattern is highly similar and is expected to be extractable once a dedicated adapter is added.

3. Strict declarative UI whitelist
- Model output is JSON blocks only, not raw HTML/JS/CSS
- Supports 8 safe block types: `text_block`, `metric_card`, `data_table`, `echart_card`, `confirm_panel`, `filter_form`, `timeline_card`, `diff_card`

4. LangGraph workflow with human approval gates
- Multi-step task orchestration with checkpoints
- `interrupt()` hard pause for write-risk operations
- Resume-after-approval flow with full audit trail

5. AG-UI + SSE real-time event stream
- Node-level progress events
- Streamed reasoning and output
- Approval-triggered UI interruption without polling

6. End-to-end observability
- Unified Trace ID across API layer, graph execution, and HTTP executor
- Full-step auditable event trail

7. Multi-model gateway support
- Built-in Agent Matchbox routing
- Model switching without business code changes

8. Docker-aware connectivity for project import
- Auto-resolves sample backend addresses by runtime environment
- Uses container DNS names in Docker and `localhost` on local host
- `test-connection` and `fetch-routes` can fall back to AST discovery with `source_path`, preventing import flow from being blocked by OpenAPI reachability

## Quick Start

### Requirements

- Python 3.11+ (Conda recommended)
- Node.js 18+ and pnpm 10
- OpenAPI is recommended (`/openapi.json` or local file)
- If OpenAPI is unavailable, provide a reachable source path (`source_path`) for AST-based discovery

### 1. Clone

```bash
git clone https://github.com/your-org/lui-for-all.git
cd lui-for-all
```

### 2. Backend setup

```bash
conda create -n lui python=3.11 -y
conda activate lui
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

### 3. Frontend setup

```bash
cd frontend
pnpm install
```

### 4. Run

```bash
# Terminal 1
cd backend
conda run -n lui uvicorn app.main:app --reload --port 6689

# Terminal 2
cd frontend
pnpm dev
```

### 5. Import your first project

Open `http://localhost:5173`, create a project, and provide your OpenAPI URL first (for example: `http://your-app/openapi.json`).

If your target system does not expose OpenAPI, you can still onboard by providing `source_path`; discovery will automatically switch to AST mode.

## Architecture (Summary)

- Frontend: Vue 3 + Vite + Pinia + Vue Router + Element Plus
- Protocol: AG-UI style SSE events + declarative UI blocks
- Backend: FastAPI + LangGraph + SQLAlchemy + SQLite
- Discovery: OpenAPI ingestion + Tree-sitter AST fallback + capability graph building
- Runtime safety: policy matrix + human-in-the-loop approval

## Roadmap

- [x] MVP workflow (FastAPI + LangGraph)
- [x] OpenAPI-based capability discovery
- [x] 8 UI block whitelist
- [x] Real-time SSE streaming and approval interrupt
- [x] Multi-model gateway
- [x] Tree-sitter AST semantic route discovery (OpenAPI-optional onboarding)
- [ ] Capability graph visual management
- [ ] Multi-tenant permission system
- [ ] Private deployment guide

<div align="center">

*Let language become the interface.*

</div>
