# Chat Endpoint Integration Protocol (Custom GUI Ready)

This document defines the unified chat protocol for LUI-for-All so developers can build their own GUI directly on top of the `chat` endpoints without relying on the built-in frontend.

## 1. Goals

- Keep the main chat flow under the `chat` namespace.
- Let frontend teams integrate by implementing event rendering + block rendering only.
- Preserve all built-in frontend data elements: progress, HTTP call logs, approvals, reasoning stream, and UI blocks.

## 2. Transport Matrix

| Data | Endpoint | Transport | Content-Type | Notes |
|---|---|---|---|---|
| Start chat and run task | `POST /api/chat/stream` | SSE | `text/event-stream` | Creates a new task_run and starts streaming |
| Resume after approval | `POST /api/chat/resume` | SSE | `text/event-stream` | Continues the same task_run from checkpoint |
| Session messages snapshot | `GET /api/chat/sessions/{session_id}/messages` | HTTP JSON | `application/json` | Includes text/reasoning/approval block/HTTP summary metadata |
| Task snapshot | `GET /api/chat/task-runs/{task_run_id}` | HTTP JSON | `application/json` | Includes `ui_blocks` and `execution_artifacts` |
| Task event replay | `GET /api/chat/task-runs/{task_run_id}/events` | HTTP JSON | `application/json` | Event sourcing replay |
| Approval records | `GET /api/chat/task-runs/{task_run_id}/approvals` | HTTP JSON | `application/json` | Pending + decided approvals |
| HTTP execution records | `GET /api/chat/task-runs/{task_run_id}/http-executions` | HTTP JSON | `application/json` | Tool-call HTTP execution details |

## 3. SSE Protocol

### 3.1 Frame Format

```text
event: <event_name>
data: { ...json payload... }
```

### 3.2 Key Events

| event | Transport | Key fields | UI usage |
|---|---|---|---|
| `session_started` | SSE | `session_id`, `project_id`, `trace_id` | Initialize chat context |
| `task_started` | SSE | `task_run_id`, `user_message` | Mark task start |
| `task_progress` | SSE | `node_name`, `progress`, `message` | Progress bar/status |
| `node_completed` | SSE | `node_name`, `progress` | Node timeline |
| `tool_started` | SSE | `tool_name`, `title`, `detail`, `route_id` | Runtime activity log |
| `tool_completed` | SSE | `tool_name`, `status_code`, `route_id` | HTTP call status log |
| `token_emitted` | SSE | `token` | Assistant text streaming |
| `thought_emitted` | SSE | `token` | Reasoning stream |
| `agentic_iteration` | SSE | `iteration`, `think` | Multi-step reasoning status |
| `write_approval_required` | SSE | `batch_id`, `items[]`, `write_id`, `reasoning`, `safety_level` | Render approval panel |
| `approval_pending` | SSE | `session_id`, `task_run_id` | Graph paused for user decision |
| `ui_block_emitted` | SSE | `block_index`, `block_type`, `block_data` | Render whitelist block |
| `task_completed` | SSE | `summary` | Task done summary |
| `error` | SSE | `error_code`, `error_message`, `details` | Error display and recovery |

## 4. UI Block Whitelist

Custom GUIs only need renderers for these `block_type` values:

- `text_block`
- `metric_card`
- `data_table`
- `echart_card`
- `confirm_panel`
- `filter_form`
- `timeline_card`
- `diff_card`

## 5. Minimal Integration Flow

1. Call `POST /api/chat/stream` with `project_id + content (+ session_id)`.
2. Consume SSE events continuously:
   - `token_emitted` for assistant output
   - `thought_emitted` for reasoning
   - `task_progress` / `tool_*` for execution trace
   - `ui_block_emitted` for structured UI
3. On `write_approval_required`, render approval UI.
4. After user decision, call `POST /api/chat/resume` with:
   - `action`: `approve` or `reject`
   - `approved_ids`: write IDs allowed to execute
   - `decided_ids`: all write IDs in this approval panel (recommended for full audit state)
5. For replay/history, call the snapshot endpoints.

## 6. Request Examples

### 6.1 Start

```http
POST /api/chat/stream
Content-Type: application/json

{
  "project_id": "project-123",
  "content": "List today's pending approval orders sorted by amount",
  "session_id": "optional-session-id",
  "locale": "en-US"
}
```

### 6.2 Resume

```http
POST /api/chat/resume
Content-Type: application/json

{
  "session_id": "session-123",
  "task_run_id": "task-123",
  "action": "approve",
  "batch_id": "batch-001",
  "approved_ids": ["write-1", "write-2"],
  "decided_ids": ["write-1", "write-2", "write-3"],
  "write_id": "write-1",
  "locale": "en-US"
}
```

## 7. Integration Recommendation

If your custom GUI supports:

- SSE event dispatcher
- 8 whitelist block renderers
- history/audit replay APIs
- approval + resume interaction

then you can replace the frontend layer without changing the backend capability core.
