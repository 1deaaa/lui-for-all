<div align="center">

# LUI-for-All

**Operate any system with natural language.**

*Language User Interface · Zero-Intrusion Integration · Enterprise-Grade Safety · Full Interface Type Coverage*
</div>

---

> Languages: [简体中文](README.md) | **English** | [日本語](README.ja-JP.md)

> Developer Protocol: [Chat Endpoint Integration](CHAT_ENDPOINT_INTEGRATION.en-US.md) (Custom GUI) | [Management API Reference](MANAGEMENT_API.en-US.md) (Projects, Auth, Settings)

## What Problem Does It Solve?

Many backend systems, especially enterprise and internal-operation systems, are powerful but hard to use. Users must navigate complex menus, remember filter combinations, and fill repetitive forms to finish tasks that can be described in one sentence.

**LUI-for-All** adds a natural-language operation layer next to your existing system in an isolated folder, without touching your current codebase.

```text
User: "List all purchase requests pending approval from last week,
sorted by amount descending, and highlight items above 50,000."

LUI: [Understand intent -> call existing APIs -> render table + highlights]
     ✓ No modifications to your existing system code
```

---

### LUI-for-All's Role in the Claw Ecosystem

In early 2026, the open-source AI agent **OpenClaw** took the world by storm — surpassing 300K GitHub stars to claim the #1 spot, sparking a global "lobster-raising" craze. OpenClaw evolved AI from "Q&A chatbot" to "24/7 digital worker": it receives commands through WhatsApp, Telegram, and other messaging platforms, autonomously operating your computer — running shell commands, controlling browsers, managing files, sending emails — truly achieving **natural-language-driven local automation**.

The Claw ecosystem rapidly spawned variants like ClawMobile (mobile), enterprise WorkBuddy, AutoClaw, and more. Tencent Cloud and Alibaba Cloud offer one-click deployments. Chinese model vendors (Kimi, MiniMax, Step) race to integrate. A brand-new Agent ecosystem has taken shape.

**But all Claws share one blind spot: they can't reach into your business systems.**

Claws excel at general desktop automation — opening browsers, clicking buttons, filling forms. But enterprise core systems operate on **API endpoints and databases**, not GUI elements. For ERP purchase approvals, CRM customer order management, or multi-level OA approval chains — Claws can only degrade to "simulated clicking," which is neither reliable nor secure.

**LUI-for-All completes this final link in the Claw ecosystem:**

| | Claw Family | LUI-for-All |
|---|---|---|
| Operates on | Local devices, browsers, file systems | Enterprise business system APIs |
| Interaction | GUI automation (clicks/screenshots) | Native API calls (structured, auditable) |
| Security model | OS-level permissions | 5-tier safety classification + human approval gates |
| Use cases | Personal productivity, general automation | Enterprise business operations, multi-system orchestration |

When a Claw connects to LUI-for-All through the MCP protocol, it gains **hands that can reach into enterprise systems** — not simulated clicks, but interface-understanding through capability maps, risk management through safety policy matrices, and critical operation protection through human-in-the-loop approval flows. Claws handle "when to do it," LUI handles "how to do it safely."

This means: when you tell your Claw on Telegram "list all pending purchase orders from last week sorted by amount," the Claw relays this command to LUI-for-All via MCP. LUI automatically identifies the intent, calls the ERP API, and returns a structured data table — fully auditable, traceable, with write operations requiring your confirmation.

## Core Highlights

1. Zero-intrusion integration and easy removal
- Runs as an isolated folder beside your project
- Uses read-only access to existing code by default
- Runtime write operations are isolated in `workspace/`
- Supports **multi-project management** — each project has its own capability map, sessions, and permission isolation

2. Dual-channel authentication: Admin + End-user
LUI implements **dual-channel JWT authentication**, making the system truly usable for both project administrators and all project users:

- **Admin channel** (`sub=lui-admin`): Project administrators log in via LUI's independent password, with full management privileges — creating projects, configuring capabilities, managing role profiles, viewing audit logs, etc.
- **User channel** (`sub=lui-user`): End-users authenticate through the **target system's own login endpoint**. LUI proxies the login and issues a restricted JWT. Users can only access interfaces permitted by their role profile within their project, achieving true project-level permission isolation.

**Role Profile mechanism**: Administrators can create role profiles for different roles (e.g., "Regular User", "Department Manager"). The system automatically probes each route's accessibility (`RouteAccessibility`) using that role's credentials, generating a precise interface whitelist. Users without a matched profile fall back to the default role profile.

This means:
- All backends on a single device can be onboarded as independent projects
- Each project's regular users can log in via the project's built-in auth system and operate **interfaces within their permission scope** using natural language
- LUI becomes a truly universal and secure Language User Interface

3. Hybrid discovery: OpenAPI + Tree-sitter AST
- OpenAPI-first ingestion for fast, structured route discovery
- Unified AST extraction layer (`FrameAdapter + get_tree_sitter_query`) for full handler implementation capture
- Built-in adapters for mainstream backends: Python (FastAPI/Flask/Sanic), Node.js (NestJS/Express/Fastify), Java (Spring Boot), C# (ASP.NET Core), and Go (Gin/Echo/Fiber/chi)
- Automatic AST fallback when OpenAPI is unavailable, using `source_path`
- Route parameter normalization across frameworks (for example, `:id -> {id}`) to improve matching quality

### Representative Syntax Coverage (7 Samples)

The repository now includes 7 representative backend samples with validated two-level extraction (route discovery + handler/function implementation extraction).

| Representative sample | Route style family | Current adapter coverage target (same family) | Theoretical transfer (requires adapter extension) |
|---|---|---|---|
| `fastapi_sample` | Python decorator routes (`@router.get`, `@app.post`) | FastAPI, Flask, Sanic, Starlette, Litestar, aiohttp, Bottle, Quart | Ruby Sinatra/Grape, PHP Slim |
| `node_sample` | Node call-chain routing (`app.get()`, `router.post()`) | Express, Fastify, Koa Router, Hono, Elysia, Restify | PHP Laravel/Lumen/Slim, Ruby Hanami |
| `django_sample` | Central URLConf (`path/re_path/include`) | Django, Django REST Framework | Ruby on Rails (`routes.rb`), PHP Laravel (`routes/web.php`) |
| `springboot_sample` | Controller annotations (class prefix + method mapping) | Java Spring Boot, Spring MVC | C# ASP.NET Core attribute controllers, PHP Symfony attribute routes |
| `aspnetcore_sample` | Minimal API mapping (`MapGet/MapPost/MapMethods`) | ASP.NET Core Minimal API | Java Javalin/Spark, Go net/http + mux |
| `go_gin_sample` | Grouped chain registration (`Group + METHOD(path, handler)`) | Gin, Echo, Fiber, Chi | Rust Actix/Axum, PHP Slim |
| `node_native_sample` | No-framework imperative dispatch (`if (method && path)`) | Node.js built-in http | Python wsgiref/werkzeug imperative dispatch, Ruby Rack, PHP Swoole native dispatch |

Notes:

- "Current adapter coverage target" means frameworks that share the same AST routing pattern and are covered by the implemented extractor logic.
- The repository has direct test validation for the 7 representative samples themselves: `backend/test/test_route_extractor_representative_samples.py`.
- "Theoretical transfer" means the syntax pattern is highly similar and is expected to be extractable once a dedicated adapter is added.

### AST Four-Paradigm Normalization

Discovery is now normalized into 4 AST routing paradigms. The 7 samples are framework representatives, not new paradigm types:

- `decorator_metadata`: annotation/decorator routes (FastAPI, Spring, ASP.NET controllers)
- `call_registration`: call-based registration (Express/Fastify, Gin/Echo/Fiber/Chi, ASP.NET Minimal API)
- `route_table`: centralized route table declarations (Django URLConf)
- `imperative_dispatch`: imperative control flow dispatch (Node native `if/switch`)

All four paradigms are emitted as the same `RouteSnippet` structure and go through the same chunking + LLM context flow .

### Discovery Layer Full Flow (with Branches)

```mermaid
flowchart TD
     A[discover_project project_id, base_url, openapi_path, source_path] --> B{OpenAPI ingestion succeeds?}
     B -- Yes --> C[ingest_openapi build RouteMap source=openapi]
     B -- No --> D{source_path provided?}
     D -- No --> E[Discovery fails return OpenAPI error]
     D -- Yes --> F[ingest_semantic_routes AST semantic discovery build RouteMap source=ast]

     C --> G[generate_project_context]
     F --> G
     G --> H[build_capability_graph]

     H --> I{source_path provided?}
     I -- No --> J[Skip precise code extraction use rule fallback for all routes]
     I -- Yes --> K[RouteExtractor.extract_batch route_pairs]

     K --> L{Adapter detected?}
     L -- No --> M[All routes snippet=None]
     L -- Yes --> N[Adapter.extract_all_routes]

     N --> O{Tree-sitter and Query available?}
     O -- No --> P[fallback_extract_all_routes]
     O -- Yes --> Q[Traverse files AST Query captures to RouteSnippet]

     P --> R[Match each target route]
     Q --> R

     R --> S{Exact route_id hit?}
     S -- Yes --> T[Pick longest candidate code]
     S -- No --> U{Fuzzy path_matches hit?}
     U -- Yes --> T
     U -- No --> V[This route snippet=None]

     T --> W[Chunk matched snippets around 32K]
     V --> W
     M --> W

     J --> X[Assemble capability graph]
     W --> Y{Any analyzable chunks?}
     Y -- No --> Z[analysis_map empty]
     Y -- Yes --> AA[Concurrent LLM analysis per chunk]
     AA --> AB[Merge analysis_map]
     Z --> X
     AB --> X

     X --> AC{Route has AI analysis?}
     AC -- Yes --> AD[Use AI domain safety summary]
     AC -- No --> AE[HTTP method based fallback]

     AD --> AF[Persist RouteMap Capability Project status]
     AE --> AF
     AF --> AG[Discovery completed]
```

4. Full interface type coverage: Instant / Streaming / Paginated — AI auto-detects and adapts

During the capability building phase, the system automatically analyzes each route's response mode (`response_mode`) and classifies it into three categories:

| Response Mode | Typical Scenarios | AI Collection Strategy |
|---|---|---|
| `instant` | Standard CRUD, queries, write operations | Single request-response, direct return |
| `streaming` | SSE real-time push (metrics stream, alerts stream, notifications) | `stream_call`: time window / event count / snapshot; supports heartbeat filtering and `[DONE]` termination detection |
| `paginated` | Cursor pagination (`next_cursor`), offset pagination (`page/page_size`) | `stream_call`: auto-pagination, supports both cursor and offset protocols with auto-detection |

At runtime, when the AI sees interfaces marked with `📡SSE Streaming` or `📄Paginated` in the capability list, it automatically selects the `stream_call` action instead of a regular `call`. It collects data according to the strategy and returns a compressed summary (with sampling ratio and statistical summary), rather than dumping the raw stream to the user.

**Hard-limit safeguards**: Max collection duration 60s, max events 500, max single event 4KB, max total result 32KB. Exceeding these triggers uniform sampling preserving head and tail — the AI cannot override these limits.

5. Strict declarative UI whitelist
- Model output is JSON blocks only, not raw HTML/JS/CSS
- Supports 8 safe block types: `text_block`, `metric_card`, `data_table`, `echart_card`, `confirm_panel`, `filter_form`, `timeline_card`, `diff_card`

6. LangGraph workflow with human approval gates
- Multi-step task orchestration with checkpoints
- `interrupt()` hard pause for write-risk operations
- Resume-after-approval flow with full audit trail

7. AG-UI + SSE real-time event stream
- Node-level progress events
- Streamed reasoning and output
- Approval-triggered UI interruption without polling

8. End-to-end observability
- Unified Trace ID across API layer, graph execution, and HTTP executor
- Full-step auditable event trail

9. Multi-model gateway support
- Built-in Agent Matchbox routing
- Model switching without business code changes

10. Docker-aware connectivity for project import
- Auto-resolves sample backend addresses by runtime environment
- Uses container DNS names in Docker and `localhost` on local host
- `test-connection` and `fetch-routes` can fall back to AST discovery with `source_path`, preventing import flow from being blocked by OpenAPI reachability

11. Pluggable chat protocol for custom GUIs
- Developers can directly integrate with `chat` endpoints and replace the built-in frontend without changing backend execution logic
- Fully covers current frontend elements: AI progress, HTTP call logs, approval requests/records, reasoning stream, and 8 UI block types
- Transport boundary is explicit: streaming data over SSE, replay/audit snapshots over standard JSON APIs
- `/api/chat/*` is the **only recommended interface** for custom GUIs; the built-in frontend's `/api/sessions/*` is an internal legacy interface

Detailed protocol: [Chat Endpoint Integration](CHAT_ENDPOINT_INTEGRATION.en-US.md)

Management APIs (projects, auth, settings, LLM config, audit): [Management API Reference](MANAGEMENT_API.en-US.md)

12. MCP integration with OpenClaw (multi-channel execution gateway)

> See [LUI-for-All's Role in the Claw Ecosystem](#lui-for-alls-role-in-the-claw-ecosystem) above for product positioning.

OpenClaw's biggest value is fully automated, unattended execution from natural language. You give it a task, and it keeps working across its own computer, accounts, and channels without needing a human to click through every step.

The combined value with LUI-for-All is more practical:

- OpenClaw handles unattended natural-language automation, while LUI-for-All pushes actions into a specific private project
- Users can send tasks inside OpenClaw and use LUI's MCP interface to reach deep into project pages, APIs, and workflows
- We keep safety levels, human confirmation, SSE progress, and HTTP call logs, so the flow stays hands-off but still traceable

Quick integration steps:

1. Start OpenClaw and let it run as the natural-language automation entry point
2. Register LUI-for-All as an MCP tool on the OpenClaw side, or bridge OpenClaw sessions to MCP clients
3. Configure the LUI-for-All MCP token and gateway URL so OpenClaw can reach your private project
4. Start with one read-only capability, then add approval-based business actions gradually

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

### 2. Backend setup and config

```bash
conda create -n lui python=3.11 -y
conda activate lui
pip install -r backend/requirements.txt

# macOS/Linux
cp backend/.env.example backend/.env

# Windows PowerShell
# Copy-Item backend/.env.example backend/.env
```

Important config notes:

- `backend/.env` is for global LUI settings (`LUI_*`) such as `LUI_DB_PATH` and `LUI_MCP_API_TOKEN`.
- Matchbox master key `LLM_KEY` is not read from `backend/.env`.
- On first startup, the system creates and reads `workspace/agent_matchbox/.env` for `LLM_KEY`.
- If you need a custom Matchbox home, set system env var `AGENT_MATCHBOX_HOME`.

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

Optional health check after startup:

```bash
# macOS/Linux
curl http://localhost:6689/health

# Windows PowerShell
Invoke-RestMethod http://localhost:6689/health
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
- [x] Full streaming interface type coverage (SSE / cursor pagination / offset pagination / long polling)
- [x] Dual-channel JWT auth (admin + project end-user) with role profiles
- [ ] Capability graph visual management
- [ ] Private deployment guide

## License

Licensed under the Apache License 2.0. See `LICENSE`.

Copyright (c) 2026 Mournight (AIdeaStudio)

<div align="center">

*Let language become the interface.*

</div>
