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

2. Automatic capability modeling from OpenAPI
- Ingests `OpenAPI/Swagger` documents automatically
- Builds capability graph with domain, modality, and policy metadata
- Re-run discovery to sync with upstream API changes

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

## Quick Start

### Requirements

- Python 3.11+ (Conda recommended)
- Node.js 18+ and pnpm 10
- Target project exposes OpenAPI (`/openapi.json` or local file)

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

Open `http://localhost:5173`, create a project, and provide your OpenAPI URL (for example: `http://your-app/openapi.json`).

## Architecture (Summary)

- Frontend: Vue 3 + Vite + Pinia + Vue Router + Element Plus
- Protocol: AG-UI style SSE events + declarative UI blocks
- Backend: FastAPI + LangGraph + SQLAlchemy + SQLite
- Discovery: OpenAPI ingestion + capability graph building
- Runtime safety: policy matrix + human-in-the-loop approval

## Roadmap

- [x] MVP workflow (FastAPI + LangGraph)
- [x] OpenAPI-based capability discovery
- [x] 8 UI block whitelist
- [x] Real-time SSE streaming and approval interrupt
- [x] Multi-model gateway
- [ ] Git semantic parsing
- [ ] Capability graph visual management
- [ ] Multi-tenant permission system
- [ ] Private deployment guide

<div align="center">

*Let language become the interface.*

</div>
