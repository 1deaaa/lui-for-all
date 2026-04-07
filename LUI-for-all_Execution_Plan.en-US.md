# Full Project Execution Plan (MVP)

> Languages: [简体中文](LUI-for-all_Execution_Plan.md) | **English** | [日本語](LUI-for-all_Execution_Plan.ja-JP.md)
>
> README: [简体中文](README.md) | [English](README.en-US.md) | [日本語](README.ja-JP.md)

## 1. Vision and Core Requirements

The goal is to provide an independent natural-language user interface (LUI) for existing systems that are currently GUI-heavy.

Instead of navigating multiple pages and filters, users describe goals in plain language. The system interprets intent, executes existing capabilities, and returns structured results.

### Ten Product Principles

1. Serve existing systems, not replace them.
2. Elevate interaction from page operations to language operations.
3. Build an explicit capability graph automatically.
4. Task-first orchestration, not naive endpoint-chat mapping.
5. Strict safety isolation by default.
6. Full event-sourced auditability.
7. Text-first responses; UI blocks only when needed.
8. Re-order interaction priorities (command-first, page-second).
9. Clear boundaries: not RPA, not low-code frontend regeneration.
10. Focus on high-friction enterprise workflows.

## 2. Locked MVP Tech Stack

### Backend

- Python (Conda + `requirements.txt`)
- FastAPI
- Pydantic v2
- LangGraph 1.x
- httpx
- SQLAlchemy 2
- SQLite + `langgraph-checkpoint-sqlite`

### Frontend

- Vue 3.5 + TypeScript
- Vite 7
- Vue Router 4 + Pinia 3
- Element Plus 2.x
- Apache ECharts
- pnpm 10

### Data and Protocol

- Pydantic/ORM model separation
- SSE for real-time events (instead of WebSocket)
- Declarative UI blocks with strict whitelist

## 3. Subsystem Design

### 3.1 Project Modeler (OpenAPI-Driven)

- Ingest target OpenAPI spec as primary deterministic source.
- Add lightweight usage signals (for example, frontend call traces).
- Enrich capability graph with:
  - `domain`
  - `best_modalities`
  - `requires_confirmation`
  - `user_intent_examples`

### 3.2 Declarative UI and Event Protocol

- Use A2UI-style declarative block outputs.
- Use AG-UI style SSE event streams.
- Keep model output strictly constrained to 8 whitelist blocks:
  - `text_block`
  - `metric_card`
  - `data_table`
  - `echart_card`
  - `confirm_panel`
  - `filter_form`
  - `timeline_card`
  - `diff_card`

### 3.3 Safety Policy Levels

- `readonly_safe`: direct execution
- `readonly_sensitive`: execute + redaction
- `soft_write`: mandatory human approval
- `hard_write` / `critical`: blocked in MVP

## 4. Repository Architecture (Target)

```text
lui-for-all/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── graph/
│   │   ├── discovery/
│   │   ├── policy/
│   │   ├── executor/
│   │   ├── schemas/
│   │   └── models/
├── frontend/
│   └── src/
│       ├── views/
│       ├── stores/
│       ├── composables/
│       └── components/
└── workspace/
```

## 5. Agent Execution Instructions (Phase-Gated)

### Phase 1: Infrastructure and Schemas

1. Create baseline project structure and telemetry wiring.
2. Implement protocol schemas (capability, UI blocks, SSE events, policy).
3. Build database models and initialize SQLite in `workspace/`.

### Phase 2: Capability Discovery Engine

1. Implement OpenAPI ingestion pipeline.
2. Add lightweight code/usage signal extraction.
3. Build AI-assisted capability enrichment and tests.

### Phase 3: LangGraph Workflow

1. Define shared graph state.
2. Enable checkpoint persistence.
3. Build node chain from intent parsing to block emission.
4. Integrate isolated HTTP executor.

### Phase 4: Vue Rendering Pipeline

1. Build SSE event consumer in frontend.
2. Render UI blocks with strict schema-to-component mapping.
3. Enforce no protocol bypass in rendering path.

### Phase 5: Human-in-the-Loop Safety

1. Implement execution matrix and policy gate.
2. For `soft_write`, trigger graph `interrupt()`.
3. Frontend raises `ConfirmPanel` and submits approval decision.
4. Graph resumes from checkpoint and writes full audit trail.

## 6. Delivery Criteria

- No write operations outside `workspace/`.
- All write-risk actions pass approval gate.
- End-to-end traceability from user request to rendered result.
- Protocol-constrained rendering only.
- Re-runnable discovery for upstream API updates.
