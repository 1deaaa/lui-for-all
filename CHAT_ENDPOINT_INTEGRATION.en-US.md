# Chat Endpoint Integration Protocol (Custom GUI Ready)

> This document defines the unified chat protocol for LUI-for-All. Third-party developers can directly integrate with endpoints under the `/api/chat/*` namespace to build custom GUIs, without depending on the repository's built-in frontend.

> ⚠️ **Namespace Notice**: This document only covers `/api/chat/*` endpoints. These are the **sole recommended integration interface** for custom GUIs. The `/api/sessions/*` namespace used by the internal frontend is a legacy internal interface; its unique features (such as legacy approval handling) will be migrated to `/api/chat/*` in future releases. Administrative endpoints (project management, authentication, settings, LLM configuration, audit queries, etc.) are out of scope of this protocol.

---

## 1. Design Goals

| Goal | Description |
|---|---|
| **Unified Entry** | The main chat flow goes through the `/api/chat/*` namespace; the frontend does not need to know about internal graph orchestration details |
| **Minimal Frontend** | The frontend only needs to implement "SSE event dispatch + UI Block rendering" to reuse the full AI capability |
| **Data Alignment** | Maintain data expressions consistent with the built-in frontend: AI progress, HTTP calls, approval flow, thinking stream, UI Blocks |
| **Dual-Channel Authentication** | Supports both Admin JWT (administrator) and User JWT (end user), suitable for multi-tenant scenarios |

---

## 2. Endpoint Overview

| Method | Path | Auth | Transport | Description |
|---|---|---|---|---|
| `POST` | `/api/chat/stream` | Admin / User JWT | SSE | Start a new conversation and execute in streaming mode |
| `POST` | `/api/chat/resume` | Admin / User JWT | SSE | Resume execution after approval |
| `POST` | `/api/chat/task-runs/{task_run_id}/stop` | Admin JWT | JSON | Stop a running task |
| `GET` | `/api/chat/projects/{project_id}/sessions` | Admin / User JWT | JSON | Get historical session list for a project |
| `GET` | `/api/chat/sessions/{session_id}` | Admin / User JWT | JSON | Get session details |
| `GET` | `/api/chat/sessions/{session_id}/messages` | Admin / User JWT | JSON | Get session message snapshot |
| `GET` | `/api/chat/sessions/{session_id}/messages/{message_id}` | Admin / User JWT | JSON | Get single message details |
| `GET` | `/api/chat/task-runs/{task_run_id}` | Admin JWT | JSON | Get task snapshot |
| `GET` | `/api/chat/task-runs/{task_run_id}/events` | Admin JWT | JSON | Get task event replay (Event Sourcing) |
| `GET` | `/api/chat/task-runs/{task_run_id}/approvals` | Admin JWT | JSON | Get approval records |
| `GET` | `/api/chat/task-runs/{task_run_id}/http-executions` | Admin JWT | JSON | Get HTTP execution records |

---

## 3. Endpoint Details

### 3.1 Start New Conversation (SSE Stream)

- **Method + Path**: `POST /api/chat/stream`
- **Auth**: Admin JWT or User JWT
- **Transport**: SSE (`text/event-stream`)

**Request Body**

| Field | Type | Required | Description |
|---|---|---|---|
| `project_id` | `string` | ✅ | Target project ID |
| `content` | `string` | ✅ | User message text |
| `session_id` | `string` | ❌ | Optional; pass an existing session ID to reuse a session; omit to create a new one |
| `locale` | `string` | ❌ | Response language code, e.g. `zh-CN`, `en-US`, `ja-JP`; defaults to `zh-CN` |

**Response**

SSE stream; event protocol is described in [Section 4 SSE Event Protocol](#4-sse-event-protocol).

**Request Example**

```http
POST /api/chat/stream
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "project_id": "project-123",
  "content": "把今天待审批订单按金额排序",
  "session_id": null,
  "locale": "zh-CN"
}
```

---

### 3.2 Resume After Approval (SSE Stream)

- **Method + Path**: `POST /api/chat/resume`
- **Auth**: Admin JWT or User JWT
- **Transport**: SSE (`text/event-stream`)

**Request Body**

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | `string` | ✅ | Session ID |
| `task_run_id` | `string` | ✅ | Task run ID |
| `action` | `string` | ✅ | Approval action: `approve` or `reject` |
| `write_id` | `string` | ❌ | Single approval write_id (backward compatibility) |
| `approved_ids` | `string[]` | ❌ | List of write_ids approved for execution in this batch |
| `decided_ids` | `string[]` | ❌ | All write_ids involved in the current approval panel, used for recording complete audit results |
| `batch_id` | `string` | ❌ | Approval batch ID |
| `locale` | `string` | ❌ | Response language code |

**Response**

SSE stream; shares the same event protocol as the `stream` endpoint.

**Request Example**

```http
POST /api/chat/resume
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "session_id": "session-123",
  "task_run_id": "task-123",
  "action": "approve",
  "batch_id": "batch-001",
  "approved_ids": ["write-1", "write-2"],
  "decided_ids": ["write-1", "write-2", "write-3"],
  "write_id": "write-1",
  "locale": "zh-CN"
}
```

---

### 3.3 Stop Running Task

- **Method + Path**: `POST /api/chat/task-runs/{task_run_id}/stop`
- **Auth**: Admin JWT
- **Transport**: JSON

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `task_run_id` | `string` | Task run ID |

**Request Body**

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | `string` | ❌ | Session ID (optional, for consistency check) |
| `reason` | `string` | ❌ | Reason for stopping |

**Response**

| Field | Type | Description |
|---|---|---|
| `status` | `string` | Final task status, e.g. `cancelled`, `completed` |
| `task_run_id` | `string` | Task run ID |
| `stream_cancelled` | `boolean` | Whether the running SSE stream was successfully cancelled |
| `message` | `string` | Operation result description |

**Request Example**

```http
POST /api/chat/task-runs/task-123/stop
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "session_id": "session-123",
  "reason": "用户手动停止"
}
```

---

### 3.4 Get Project Historical Session List

- **Method + Path**: `GET /api/chat/projects/{project_id}/sessions`
- **Auth**: Admin JWT or User JWT
- **Transport**: JSON

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `limit` | `int` | ❌ | `50` | Items per page (1-200) |
| `offset` | `int` | ❌ | `0` | Offset |

**Response**

| Field | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |
| `sessions` | `Session[]` | Session list |
| `total` | `int` | Total count |
| `limit` | `int` | Items per page |
| `offset` | `int` | Offset |

**Session Object**

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Session ID |
| `project_id` | `string` | Parent project ID |
| `title` | `string` | Session title |
| `status` | `string` | Session status |
| `thread_id` | `string` | LangGraph thread ID |
| `context` | `object` | Session context |
| `created_at` | `string` | Creation time (ISO 8601) |
| `updated_at` | `string` | Last updated time (ISO 8601) |
| `ended_at` | `string \| null` | End time (ISO 8601) |

**Request Example**

```http
GET /api/chat/projects/project-123/sessions?limit=50&offset=0
Authorization: Bearer <jwt>
```

---

### 3.5 Get Session Details

- **Method + Path**: `GET /api/chat/sessions/{session_id}`
- **Auth**: Admin JWT or User JWT
- **Transport**: JSON

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |

**Response**

Returns a single [Session Object](#session-object).

**Request Example**

```http
GET /api/chat/sessions/session-123
Authorization: Bearer <jwt>
```

---

### 3.6 Get Session Message Snapshot

- **Method + Path**: `GET /api/chat/sessions/{session_id}/messages`
- **Auth**: Admin JWT or User JWT
- **Transport**: JSON

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `limit` | `int` | ❌ | `50` | Maximum number of messages (1-200) |

**Response**

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `messages` | `Message[]` | Message list |
| `total` | `int` | Total message count |

**Message Object**

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Message ID |
| `role` | `string` | Role: `user`, `assistant`, `system` |
| `content` | `string` | Message content |
| `task_run_id` | `string` | Associated task run ID |
| `created_at` | `string` | Creation time (ISO 8601) |
| `metadata` | `object` | Metadata, including `http_calls`, `thought`, `approval_block`, etc. |

**Request Example**

```http
GET /api/chat/sessions/session-123/messages?limit=50
Authorization: Bearer <jwt>
```

---

### 3.7 Get Single Message Details

- **Method + Path**: `GET /api/chat/sessions/{session_id}/messages/{message_id}`
- **Auth**: Admin JWT or User JWT
- **Transport**: JSON

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `message_id` | `string` | Message ID |

**Response**

Returns a single [Message Object](#message-object).

**Request Example**

```http
GET /api/chat/sessions/session-123/messages/msg-123
Authorization: Bearer <jwt>
```

---

### 3.8 Get Task Snapshot

- **Method + Path**: `GET /api/chat/task-runs/{task_run_id}`
- **Auth**: Admin JWT
- **Transport**: JSON

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `task_run_id` | `string` | Task run ID |

**Response**

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Task run ID |
| `session_id` | `string` | Parent session ID |
| `project_id` | `string` | Parent project ID |
| `user_message` | `string` | Original user message |
| `normalized_intent` | `string` | Normalized intent |
| `status` | `string` | Status: `pending`, `running`, `waiting_approval`, `completed`, `failed`, `cancelled` |
| `plan` | `object` | Task plan |
| `execution_artifacts` | `object[]` | Execution artifacts (HTTP call records, etc.) |
| `summary_text` | `string` | Task summary |
| `ui_blocks` | `object[]` | UI Block list |
| `error` | `string` | Error message (if any) |
| `trace_id` | `string` | OpenTelemetry trace ID |
| `thread_id` | `string` | LangGraph thread ID |
| `checkpoint_id` | `string` | LangGraph checkpoint ID |
| `created_at` | `string` | Creation time (ISO 8601) |
| `updated_at` | `string` | Last updated time (ISO 8601) |
| `completed_at` | `string \| null` | Completion time (ISO 8601) |

**Request Example**

```http
GET /api/chat/task-runs/task-123
Authorization: Bearer <jwt>
```

---

### 3.9 Get Task Event Replay

- **Method + Path**: `GET /api/chat/task-runs/{task_run_id}/events`
- **Auth**: Admin JWT
- **Transport**: JSON

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `task_run_id` | `string` | Task run ID |

**Response**

| Field | Type | Description |
|---|---|---|
| `task_run_id` | `string` | Task run ID |
| `events` | `Event[]` | Event list (sorted by time) |
| `total` | `int` | Total event count |

**Event Object**

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Event ID |
| `task_run_id` | `string` | Parent task run ID |
| `event_type` | `string` | Event type |
| `payload` | `object` | Event payload |
| `actor_type` | `string` | Actor type |
| `actor_id` | `string` | Actor ID |
| `trace_id` | `string` | Trace ID |
| `evidence_refs` | `object` | Evidence references |
| `ts` | `string` | Timestamp (ISO 8601) |

**Request Example**

```http
GET /api/chat/task-runs/task-123/events
Authorization: Bearer <jwt>
```

---

### 3.10 Get Approval Records

- **Method + Path**: `GET /api/chat/task-runs/{task_run_id}/approvals`
- **Auth**: Admin JWT
- **Transport**: JSON

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `task_run_id` | `string` | Task run ID |

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `limit` | `int` | ❌ | `50` | Items per page (1-200) |
| `offset` | `int` | ❌ | `0` | Offset |

**Response**

| Field | Type | Description |
|---|---|---|
| `task_run_id` | `string` | Task run ID |
| `approvals` | `Approval[]` | Approval record list |
| `total` | `int` | Total count |

**Approval Object**

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Approval ID (i.e. write_id) |
| `session_id` | `string` | Parent session ID |
| `title` | `string` | Approval title |
| `description` | `string` | Approval description |
| `action_summary` | `string` | Action summary |
| `risk_level` | `string` | Risk level |
| `details` | `object` | Detailed information |
| `status` | `string` | Status: `pending`, `approved`, `rejected` |
| `timeout_seconds` | `int` | Timeout in seconds |
| `expires_at` | `string` | Expiration time (ISO 8601) |
| `decided_at` | `string \| null` | Decision time (ISO 8601) |
| `decided_by` | `string` | Decision maker |
| `decision_reason` | `string` | Decision reason |
| `created_at` | `string` | Creation time (ISO 8601) |

**Request Example**

```http
GET /api/chat/task-runs/task-123/approvals?limit=50&offset=0
Authorization: Bearer <jwt>
```

---

### 3.11 Get HTTP Execution Records

- **Method + Path**: `GET /api/chat/task-runs/{task_run_id}/http-executions`
- **Auth**: Admin JWT
- **Transport**: JSON

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `task_run_id` | `string` | Task run ID |

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `limit` | `int` | ❌ | `50` | Items per page (1-200) |
| `offset` | `int` | ❌ | `0` | Offset |

**Response**

| Field | Type | Description |
|---|---|---|
| `task_run_id` | `string` | Task run ID |
| `executions` | `Execution[]` | HTTP execution record list |
| `total` | `int` | Total count |

**Execution Object**

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Record ID |
| `request_id` | `string` | Request ID |
| `session_id` | `string` | Parent session ID |
| `capability_id` | `string` | Capability ID |
| `method` | `string` | HTTP method |
| `url_redacted` | `string` | Redacted URL |
| `status_code` | `int` | HTTP status code |
| `duration_ms` | `int` | Duration (milliseconds) |
| `retry_count` | `int` | Retry count |
| `headers_redacted` | `object` | Redacted request headers |
| `request_body_redacted` | `object` | Redacted request body |
| `response_body_redacted` | `object` | Redacted response body |
| `trace_id` | `string` | Trace ID |
| `policy_snapshot` | `object` | Policy snapshot |
| `error` | `string` | Error message (if any) |
| `created_at` | `string` | Creation time (ISO 8601) |

**Request Example**

```http
GET /api/chat/task-runs/task-123/http-executions?limit=50&offset=0
Authorization: Bearer <jwt>
```

---

## 4. SSE Event Protocol

### 4.1 Frame Format

Each SSE event consists of an `event:` line and a `data:` line, terminated by an empty line. The JSON in `data` does **not** contain an `event` field (it has been extracted to the `event:` line).

```text
event: <event_type>
data: <json_payload>

```

### 4.2 Event Type Overview

| event | Core data fields | Frontend usage |
|---|---|---|
| `session_started` | `session_id`, `project_id`, `trace_id` | Initialize session context |
| `task_started` | `session_id`, `task_run_id`, `user_message` | Mark task start |
| `task_progress` | `session_id`, `task_run_id`, `node_name`, `progress`, `message` | Progress bar, stage description |
| `node_completed` | `session_id`, `task_run_id`, `node_name`, `progress` | Node completion trace |
| `tool_started` | `session_id`, `task_run_id`, `tool_name`, `title`, `detail`, `step_id`, `route_id` | Runtime event panel (tool started) |
| `tool_completed` | `session_id`, `task_run_id`, `tool_name`, `title`, `detail`, `step_id`, `route_id`, `status_code` | Runtime event panel (tool completed) |
| `token_emitted` | `session_id`, `task_run_id`, `token` | AI body streaming output |
| `thought_emitted` | `session_id`, `task_run_id`, `token` | AI thinking process streaming output |
| `agentic_iteration` | `session_id`, `task_run_id`, `iteration`, `think` | Multi-turn reasoning progress |
| `write_approval_required` | `session_id`, `task_run_id`, `batch_id`, `items[]`, `write_id`, `route_id`, `method`, `path`, `parameters`, `reasoning`, `safety_level` | Render approval panel |
| `approval_pending` | `session_id`, `task_run_id` | Graph execution paused, awaiting user decision |
| `ui_block_emitted` | `session_id`, `task_run_id`, `block_index`, `block_type`, `block_data` | Render whitelisted UI Block |
| `task_completed` | `session_id`, `task_run_id`, `summary` | End state and summary |
| `error` | `session_id`, `task_run_id`, `error_code`, `error_message`, `details` | Error prompt and recovery |

### 4.3 Event Detailed Schema

#### `session_started`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `project_id` | `string` | Project ID |
| `trace_id` | `string` | Trace ID |

#### `task_started`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `task_run_id` | `string` | Task run ID |
| `user_message` | `string` | Original user message |

#### `task_progress`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `task_run_id` | `string` | Task run ID |
| `node_name` | `string` | Current node name |
| `progress` | `float` | Progress value (0.0-1.0) |
| `message` | `string \| null` | Progress message |

#### `node_completed`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `task_run_id` | `string` | Task run ID |
| `node_name` | `string` | Node name |
| `progress` | `float` | Progress value |

#### `tool_started`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `task_run_id` | `string` | Task run ID |
| `tool_name` | `string` | Tool name |
| `title` | `string` | Event title |
| `detail` | `string \| null` | Detailed information |
| `step_id` | `string \| null` | Step ID |
| `route_id` | `string \| null` | Route ID |

#### `tool_completed`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `task_run_id` | `string` | Task run ID |
| `tool_name` | `string` | Tool name |
| `title` | `string` | Event title |
| `detail` | `string \| null` | Detailed information |
| `step_id` | `string \| null` | Step ID |
| `route_id` | `string \| null` | Route ID |
| `status_code` | `int \| null` | HTTP status code |

#### `token_emitted`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `task_run_id` | `string` | Task run ID |
| `token` | `string` | Token content (frontend must concatenate) |

#### `thought_emitted`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `task_run_id` | `string` | Task run ID |
| `token` | `string` | Thinking token content (frontend must concatenate) |

#### `agentic_iteration`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `task_run_id` | `string` | Task run ID |
| `iteration` | `int` | Current iteration (starts from 1) |
| `think` | `string \| null` | AI reasoning summary for this iteration |

#### `write_approval_required`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `task_run_id` | `string` | Task run ID |
| `batch_id` | `string \| null` | Batch approval task ID |
| `items` | `object[]` | Operation item list (each contains `write_id`, `method`, `path`, `parameters`, `reasoning`, `safety_level`) |
| `write_id` | `string \| null` | Single operation ID (backward compatibility) |
| `route_id` | `string \| null` | API route (backward compatibility) |
| `method` | `string \| null` | HTTP method (backward compatibility) |
| `path` | `string \| null` | API path (backward compatibility) |
| `parameters` | `object` | Request parameters (backward compatibility) |
| `reasoning` | `string` | Why the AI wants to perform this write (backward compatibility) |
| `safety_level` | `string` | Safety level (backward compatibility): `soft_write`, `hard_write`, `critical` |

#### `approval_pending`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `task_run_id` | `string` | Task run ID |

#### `ui_block_emitted`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `task_run_id` | `string` | Task run ID |
| `block_index` | `int` | Block index (starts from 0) |
| `block_type` | `string` | Block type; see [Section 5 UI Block Whitelist](#5-ui-block-whitelist) |
| `block_data` | `object` | Block data (structure varies by block_type) |

#### `task_completed`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Session ID |
| `task_run_id` | `string` | Task run ID |
| `summary` | `string \| null` | Task summary |

#### `error`

| Field | Type | Description |
|---|---|---|
| `session_id` | `string \| null` | Session ID |
| `task_run_id` | `string \| null` | Task run ID |
| `error_code` | `string` | Error code, e.g. `TASK_FAILED`, `TASK_CANCELLED`, `STREAM_ERROR` |
| `error_message` | `string` | Error message |
| `details` | `object \| null` | Detailed information |

---

## 5. UI Block Whitelist

Custom GUIs only need to implement renderers for the following 8 `block_type` values:

| block_type | Description | Core fields |
|---|---|---|
| `text_block` | Text response | `content` (text content), `format` (`plain` / `markdown`) |
| `metric_card` | Metric card | `title`, `metrics[]` (each contains `label`, `value`, `unit`, `trend`, `trend_value`) |
| `data_table` | Paginated data table | `title`, `columns[]` (contains `key`, `label`, `type`), `rows[]`, `total`, `page`, `page_size` |
| `echart_card` | ECharts chart | `title`, `chart_type` (`bar`/`line`/`pie`/`scatter`/`radar`/`gauge`), `option` (ECharts config), `height` |
| `confirm_panel` | Approval panel | `approval_id`, `title`, `description`, `action_summary`, `risk_level`, `details[]`, `timeout_seconds` |
| `filter_form` | Parameter form | `title`, `description`, `fields[]` (contains `key`, `label`, `type`, `required`, `options`), `session_id`, `request_id` |
| `timeline_card` | Timeline | `title`, `events[]` (contains `timestamp`, `title`, `description`, `status`) |
| `diff_card` | Diff comparison | `title`, `description`, `items[]` (contains `key`, `old_value`, `new_value`, `change_type`) |

---

## 6. SSE Raw Frame Examples

### 6.1 `token_emitted` Event

```text
event: token_emitted
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","token":"根据"}

event: token_emitted
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","token":"您提供的条件"}

event: token_emitted
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","token":"，已为您筛选出 5 条记录。"}
```

### 6.2 `task_progress` Event

```text
event: task_progress
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","node_name":"agentic_loop","progress":0.35,"message":"正在调用订单查询接口"}
```

### 6.3 `write_approval_required` Event

```text
event: write_approval_required
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","batch_id":"batch-001","items":[{"write_id":"w-001","method":"POST","path":"/api/orders/approve","parameters":{"order_id":"ORD-2024"},"reasoning":"批量审批待处理订单","safety_level":"hard_write"},{"write_id":"w-002","method":"POST","path":"/api/orders/approve","parameters":{"order_id":"ORD-2025"},"reasoning":"批量审批待处理订单","safety_level":"hard_write"}],"write_id":null,"route_id":null,"method":null,"path":null,"parameters":{},"reasoning":"","safety_level":"soft_write"}
```

### 6.4 `ui_block_emitted` Event (data_table type)

```text
event: ui_block_emitted
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","block_index":0,"block_type":"data_table","block_data":{"block_type":"data_table","title":"待审批订单","columns":[{"key":"order_id","label":"订单号","type":"text"},{"key":"amount","label":"金额","type":"number","sortable":true},{"key":"status","label":"状态","type":"tag"}],"rows":[{"order_id":"ORD-2024","amount":1500.00,"status":"pending"},{"order_id":"ORD-2025","amount":2300.50,"status":"pending"}],"total":2,"page":1,"page_size":10}}
```

### 6.5 `task_completed` Event

```text
event: task_completed
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","summary":"已完成订单查询和排序，共筛选出 5 条待审批订单，按金额从高到低排列。2 条订单已提交审批请求，等待确认。"}
```

---

## 7. Minimal Integration Flow

```
┌────────────┐    POST /stream     ┌────────────┐
│  Custom GUI │ ──────────────────→ │  LUI Server │
│            │ ←── SSE event stream │            │
│            │    (token/progress/  │            │
│            │     block/approval)  │            │
└─────┬──────┘                     └────────────┘
      │
      │ Received write_approval_required
      │ + approval_pending
      ▼
┌────────────┐    POST /resume     ┌────────────┐
│ Approval UI│ ──────────────────→ │  LUI Server │
│            │ ←── SSE event stream │            │
└────────────┘                     └────────────┘
```

**Steps**

1. **Start a conversation** — `POST /api/chat/stream` with `project_id + content` (optional `session_id`, `locale`).
2. **Consume the SSE stream** — Dispatch by `event` type:
   - `token_emitted` / `thought_emitted` → Concatenate and render body / thinking area
   - `task_progress` / `tool_*` / `node_completed` → Render execution progress and call trace
   - `ui_block_emitted` → Render corresponding component based on `block_type`
   - `error` → Display error prompt
3. **Handle approvals** — Upon receiving `write_approval_required` + `approval_pending`:
   - Render the approval UI, displaying operation items
   - After user decision, call `POST /api/chat/resume` (`action` + `approved_ids` + `decided_ids`)
   - Receive new SSE stream and continue rendering
4. **Task completion** — Upon receiving `task_completed`, the SSE stream closes automatically.
5. **History replay** — Call message/task/approval/HTTP snapshot endpoints to read complete history.

---

## 8. Authentication

### 8.1 Dual-Channel JWT Authentication

LUI-for-All supports two JWT identities, suitable for multi-project end-user isolation scenarios on the same server.

| JWT Subject | Identity | Accessible scope | Issuing endpoint |
|---|---|---|---|
| `lui-admin` | Administrator | All `/api/*` endpoints | `POST /api/auth/setup` or `POST /api/auth/login` |
| `lui-user` | End user | `/api/chat/*`, `/api/sessions/*`, `/api/projects/resolve-slug/*`, `/api/auth/me` | `POST /api/auth/user-login` |

### 8.2 JWT Delivery Methods

| Method | Format | Applicable scenario |
|---|---|---|
| **Authorization Header** | `Authorization: Bearer <jwt>` | All endpoints (recommended) |
| **Query Parameter** | `?token=<jwt>` | SSE endpoints (some SSE client libraries do not support custom headers) |

### 8.3 End User Login Flow

1. The frontend retrieves project info via `GET /api/projects/resolve-slug/{slug}` (no authentication required).
2. The user submits credentials to `POST /api/auth/user-login`.
3. The backend validates credentials and issues a User JWT.

**Login Request Example**

```http
POST /api/auth/user-login
Content-Type: application/json

{
  "project_slug": "my-project",
  "username": "zhangsan",
  "password": "secret123"
}
```

**Login Response**

| Field | Type | Description |
|---|---|---|
| `token` | `string` | User JWT |
| `project_id` | `string` | Project ID |
| `project_name` | `string` | Project name |
| `project_slug` | `string` | Project slug |
| `role_profile_id` | `string` | Role profile ID |

### 8.4 User JWT Payload Structure

```json
{
  "sub": "lui-user",
  "project_id": "uuid",
  "project_slug": "my-project",
  "role_profile_id": "uuid",
  "username": "zhangsan",
  "iat": 1234567890,
  "exp": 1234567890
}
```

### 8.5 User JWT Permission Boundary

- User JWT can only access data for **its own project** (backend validates via `project_id`)
- When calling `POST /api/chat/stream`, the `project_id` must match the one in the JWT
- The backend automatically injects `user_context`; the Agentic Loop prioritizes the user's target system token for operations
- Audit endpoints (GET endpoints under `task-runs/*`) are restricted to Admin JWT only

### 8.6 Endpoints Requiring No Authentication

The following endpoints are in the JWT whitelist and do not require a token:

- `GET /health`
- `GET /docs`, `GET /redoc`, `GET /openapi.json`
- `GET /api/auth/status`
- `POST /api/auth/setup`
- `POST /api/auth/login`
- `POST /api/auth/user-login`
- `POST /api/auth/forgot-password-hint`

---

## 9. Custom GUI Adaptation Recommendations

| Layer | Implementation Notes |
|---|---|
| **Event Layer** | Implement a unified SSE dispatcher that routes by `event` field to each rendering module. Support token delivery via query parameter (`?token=<jwt>`) for compatibility with all SSE client libraries. |
| **Component Layer** | Implement renderers for the 8 `block_type` values (see Section 5). `text_block` and `data_table` are the two most commonly used; prioritize these. |
| **Approval Layer** | Listen for the `write_approval_required` + `approval_pending` event pair, render the approval UI; after user decision, call `POST /api/chat/resume`. Pass `decided_ids` to ensure complete audit records are persisted. |
| **Replay Layer** | Integrate the 4 snapshot endpoints (`messages`, `task-runs`, `approvals`, `http-executions`) to implement session history replay and audit tracing. |
| **Error Handling** | Listen for `error` events and determine recovery strategy by `error_code`: `TASK_CANCELLED` can be ignored; `TASK_FAILED` / `STREAM_ERROR` require prompting the user to retry. |
| **Multi-language** | Control AI response language via the `locale` parameter. Supports `zh-CN`, `en-US`, `ja-JP`. |
