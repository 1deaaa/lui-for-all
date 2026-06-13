# Chat 端点集成协议（自定义 GUI）

> 本文档定义 LUI-for-All 的统一聊天协议。第三方开发者可直接接入 `/api/chat/*` 命名空间的端点来构建自定义 GUI，无需依赖仓库内置前端。

> ⚠️ **命名空间说明**：本文档只覆盖 `/api/chat/*` 端点。这是自定义 GUI 的**唯一推荐接入接口**。内部前端使用的 `/api/sessions/*` 是遗留内部接口，其独有功能（如旧式审批处理）将在未来版本迁移至 `/api/chat/*`。管理类端点（项目管理、认证、设置、LLM 配置、审计查询等）不属于本协议范围。

---

## 1. 设计目标

| 目标 | 说明 |
|---|---|
| **统一入口** | 聊天主链路统一走 `/api/chat/*` 命名空间，前端无需关心内部图编排细节 |
| **极简前端** | 前端只需实现「SSE 事件分发 + UI Block 渲染」即可复用完整 AI 能力 |
| **数据对齐** | 保持与内置前端一致的数据表达：AI 进度、HTTP 调用、审批流、思考流、UI Block |
| **双通道认证** | 同时支持 Admin JWT（管理员）和 User JWT（终端用户），适用多租户场景 |

---

## 2. 端点总览

| 方法 | 路径 | 认证 | 传输 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/chat/stream` | Admin / User JWT | SSE | 启动新对话并流式执行 |
| `POST` | `/api/chat/resume` | Admin / User JWT | SSE | 审批后恢复执行 |
| `POST` | `/api/chat/task-runs/{task_run_id}/stop` | Admin JWT | JSON | 停止运行中的任务 |
| `GET` | `/api/chat/projects/{project_id}/sessions` | Admin / User JWT | JSON | 获取指定项目的历史会话列表 |
| `GET` | `/api/chat/sessions/{session_id}` | Admin / User JWT | JSON | 获取会话详情 |
| `GET` | `/api/chat/sessions/{session_id}/messages` | Admin / User JWT | JSON | 获取会话消息快照 |
| `GET` | `/api/chat/sessions/{session_id}/messages/{message_id}` | Admin / User JWT | JSON | 获取单条消息详情 |
| `GET` | `/api/chat/task-runs/{task_run_id}` | Admin JWT | JSON | 获取任务快照 |
| `GET` | `/api/chat/task-runs/{task_run_id}/events` | Admin JWT | JSON | 获取任务事件回放（Event Sourcing） |
| `GET` | `/api/chat/task-runs/{task_run_id}/approvals` | Admin JWT | JSON | 获取审批记录 |
| `GET` | `/api/chat/task-runs/{task_run_id}/http-executions` | Admin JWT | JSON | 获取 HTTP 调用记录 |

---

## 3. 端点详细说明

### 3.1 启动新对话（SSE 流）

- **方法 + 路径**：`POST /api/chat/stream`
- **认证**：Admin JWT 或 User JWT
- **传输**：SSE（`text/event-stream`）

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_id` | `string` | ✅ | 目标项目 ID |
| `content` | `string` | ✅ | 用户消息文本 |
| `session_id` | `string` | ❌ | 可选，传入已有会话 ID 以复用会话；不传则自动创建新会话 |
| `locale` | `string` | ❌ | 响应语言代码，如 `zh-CN`、`en-US`、`ja-JP`；默认 `zh-CN` |

**响应**

SSE 流，事件协议见 [第 4 节 SSE 事件协议](#4-sse-事件协议)。

**请求示例**

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

### 3.2 审批后恢复执行（SSE 流）

- **方法 + 路径**：`POST /api/chat/resume`
- **认证**：Admin JWT 或 User JWT
- **传输**：SSE（`text/event-stream`）

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | `string` | ✅ | 会话 ID |
| `task_run_id` | `string` | ✅ | 任务运行 ID |
| `action` | `string` | ✅ | 审批动作：`approve` 或 `reject` |
| `write_id` | `string` | ❌ | 单条审批 write_id（向后兼容） |
| `approved_ids` | `string[]` | ❌ | 本次批准执行的 write_id 列表 |
| `decided_ids` | `string[]` | ❌ | 当前审批面板涉及的全部 write_id，用于记录完整审计结果 |
| `batch_id` | `string` | ❌ | 审批批次 ID |
| `locale` | `string` | ❌ | 响应语言代码 |

**响应**

SSE 流，与 `stream` 端点共享相同的事件协议。

**请求示例**

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

### 3.3 停止运行中的任务

- **方法 + 路径**：`POST /api/chat/task-runs/{task_run_id}/stop`
- **认证**：Admin JWT
- **传输**：JSON

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| `task_run_id` | `string` | 任务运行 ID |

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | `string` | ❌ | 会话 ID（可选，用于一致性校验） |
| `reason` | `string` | ❌ | 停止原因 |

**响应**

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | `string` | 任务最终状态，如 `cancelled`、`completed` |
| `task_run_id` | `string` | 任务运行 ID |
| `stream_cancelled` | `boolean` | 是否成功取消了运行中的 SSE 流 |
| `message` | `string` | 操作结果描述 |

**请求示例**

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

### 3.4 获取项目历史会话列表

- **方法 + 路径**：`GET /api/chat/projects/{project_id}/sessions`
- **认证**：Admin JWT 或 User JWT
- **传输**：JSON

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |

**查询参数**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `limit` | `int` | ❌ | `50` | 每页数量（1-200） |
| `offset` | `int` | ❌ | `0` | 偏移量 |

**响应**

| 字段 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |
| `sessions` | `Session[]` | 会话列表 |
| `total` | `int` | 总数 |
| `limit` | `int` | 每页数量 |
| `offset` | `int` | 偏移量 |

**Session 对象**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `string` | 会话 ID |
| `project_id` | `string` | 所属项目 ID |
| `title` | `string` | 会话标题 |
| `status` | `string` | 会话状态 |
| `thread_id` | `string` | LangGraph 线程 ID |
| `context` | `object` | 会话上下文 |
| `created_at` | `string` | 创建时间（ISO 8601） |
| `updated_at` | `string` | 更新时间（ISO 8601） |
| `ended_at` | `string \| null` | 结束时间（ISO 8601） |

**请求示例**

```http
GET /api/chat/projects/project-123/sessions?limit=50&offset=0
Authorization: Bearer <jwt>
```

---

### 3.5 获取会话详情

- **方法 + 路径**：`GET /api/chat/sessions/{session_id}`
- **认证**：Admin JWT 或 User JWT
- **传输**：JSON

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |

**响应**

返回单个 [Session 对象](#session-对象)。

**请求示例**

```http
GET /api/chat/sessions/session-123
Authorization: Bearer <jwt>
```

---

### 3.6 获取会话消息快照

- **方法 + 路径**：`GET /api/chat/sessions/{session_id}/messages`
- **认证**：Admin JWT 或 User JWT
- **传输**：JSON

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |

**查询参数**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `limit` | `int` | ❌ | `50` | 最大消息数（1-200） |

**响应**

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `messages` | `Message[]` | 消息列表 |
| `total` | `int` | 消息总数 |

**Message 对象**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `string` | 消息 ID |
| `role` | `string` | 角色：`user`、`assistant`、`system` |
| `content` | `string` | 消息内容 |
| `task_run_id` | `string` | 关联的任务运行 ID |
| `created_at` | `string` | 创建时间（ISO 8601） |
| `metadata` | `object` | 元数据，含 `http_calls`、`thought`、`approval_block` 等 |

**请求示例**

```http
GET /api/chat/sessions/session-123/messages?limit=50
Authorization: Bearer <jwt>
```

---

### 3.7 获取单条消息详情

- **方法 + 路径**：`GET /api/chat/sessions/{session_id}/messages/{message_id}`
- **认证**：Admin JWT 或 User JWT
- **传输**：JSON

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `message_id` | `string` | 消息 ID |

**响应**

返回单个 [Message 对象](#message-对象)。

**请求示例**

```http
GET /api/chat/sessions/session-123/messages/msg-123
Authorization: Bearer <jwt>
```

---

### 3.8 获取任务快照

- **方法 + 路径**：`GET /api/chat/task-runs/{task_run_id}`
- **认证**：Admin JWT
- **传输**：JSON

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| `task_run_id` | `string` | 任务运行 ID |

**响应**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `string` | 任务运行 ID |
| `session_id` | `string` | 所属会话 ID |
| `project_id` | `string` | 所属项目 ID |
| `user_message` | `string` | 用户原始消息 |
| `normalized_intent` | `string` | 归一化意图 |
| `status` | `string` | 状态：`pending`、`running`、`waiting_approval`、`completed`、`failed`、`cancelled` |
| `plan` | `object` | 任务计划 |
| `execution_artifacts` | `object[]` | 执行产物（HTTP 调用记录等） |
| `summary_text` | `string` | 任务摘要 |
| `ui_blocks` | `object[]` | UI Block 列表 |
| `error` | `string` | 错误信息（如有） |
| `trace_id` | `string` | OpenTelemetry 追踪 ID |
| `thread_id` | `string` | LangGraph 线程 ID |
| `checkpoint_id` | `string` | LangGraph 检查点 ID |
| `created_at` | `string` | 创建时间（ISO 8601） |
| `updated_at` | `string` | 更新时间（ISO 8601） |
| `completed_at` | `string \| null` | 完成时间（ISO 8601） |

**请求示例**

```http
GET /api/chat/task-runs/task-123
Authorization: Bearer <jwt>
```

---

### 3.9 获取任务事件回放

- **方法 + 路径**：`GET /api/chat/task-runs/{task_run_id}/events`
- **认证**：Admin JWT
- **传输**：JSON

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| `task_run_id` | `string` | 任务运行 ID |

**响应**

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_run_id` | `string` | 任务运行 ID |
| `events` | `Event[]` | 事件列表（按时间排序） |
| `total` | `int` | 事件总数 |

**Event 对象**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `string` | 事件 ID |
| `task_run_id` | `string` | 所属任务运行 ID |
| `event_type` | `string` | 事件类型 |
| `payload` | `object` | 事件载荷 |
| `actor_type` | `string` | 执行者类型 |
| `actor_id` | `string` | 执行者 ID |
| `trace_id` | `string` | 追踪 ID |
| `evidence_refs` | `object` | 证据引用 |
| `ts` | `string` | 时间戳（ISO 8601） |

**请求示例**

```http
GET /api/chat/task-runs/task-123/events
Authorization: Bearer <jwt>
```

---

### 3.10 获取审批记录

- **方法 + 路径**：`GET /api/chat/task-runs/{task_run_id}/approvals`
- **认证**：Admin JWT
- **传输**：JSON

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| `task_run_id` | `string` | 任务运行 ID |

**查询参数**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `limit` | `int` | ❌ | `50` | 每页数量（1-200） |
| `offset` | `int` | ❌ | `0` | 偏移量 |

**响应**

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_run_id` | `string` | 任务运行 ID |
| `approvals` | `Approval[]` | 审批记录列表 |
| `total` | `int` | 总数 |

**Approval 对象**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `string` | 审批 ID（即 write_id） |
| `session_id` | `string` | 所属会话 ID |
| `title` | `string` | 审批标题 |
| `description` | `string` | 审批描述 |
| `action_summary` | `string` | 动作摘要 |
| `risk_level` | `string` | 风险等级 |
| `details` | `object` | 详细信息 |
| `status` | `string` | 状态：`pending`、`approved`、`rejected` |
| `timeout_seconds` | `int` | 超时时间（秒） |
| `expires_at` | `string` | 过期时间（ISO 8601） |
| `decided_at` | `string \| null` | 决策时间（ISO 8601） |
| `decided_by` | `string` | 决策者 |
| `decision_reason` | `string` | 决策原因 |
| `created_at` | `string` | 创建时间（ISO 8601） |

**请求示例**

```http
GET /api/chat/task-runs/task-123/approvals?limit=50&offset=0
Authorization: Bearer <jwt>
```

---

### 3.11 获取 HTTP 调用记录

- **方法 + 路径**：`GET /api/chat/task-runs/{task_run_id}/http-executions`
- **认证**：Admin JWT
- **传输**：JSON

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| `task_run_id` | `string` | 任务运行 ID |

**查询参数**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `limit` | `int` | ❌ | `50` | 每页数量（1-200） |
| `offset` | `int` | ❌ | `0` | 偏移量 |

**响应**

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_run_id` | `string` | 任务运行 ID |
| `executions` | `Execution[]` | HTTP 调用记录列表 |
| `total` | `int` | 总数 |

**Execution 对象**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `string` | 记录 ID |
| `request_id` | `string` | 请求 ID |
| `session_id` | `string` | 所属会话 ID |
| `capability_id` | `string` | 能力 ID |
| `method` | `string` | HTTP 方法 |
| `url_redacted` | `string` | 脱敏后的 URL |
| `status_code` | `int` | HTTP 状态码 |
| `duration_ms` | `int` | 耗时（毫秒） |
| `retry_count` | `int` | 重试次数 |
| `headers_redacted` | `object` | 脱敏后的请求头 |
| `request_body_redacted` | `object` | 脱敏后的请求体 |
| `response_body_redacted` | `object` | 脱敏后的响应体 |
| `trace_id` | `string` | 追踪 ID |
| `policy_snapshot` | `object` | 策略快照 |
| `error` | `string` | 错误信息（如有） |
| `created_at` | `string` | 创建时间（ISO 8601） |

**请求示例**

```http
GET /api/chat/task-runs/task-123/http-executions?limit=50&offset=0
Authorization: Bearer <jwt>
```

---

## 4. SSE 事件协议

### 4.1 帧格式

每条 SSE 事件由 `event:` 行和 `data:` 行组成，以空行结尾。`data` 中的 JSON **不包含** `event` 字段（该字段已被提取到 `event:` 行）。

```text
event: <event_type>
data: <json_payload>

```

### 4.2 事件类型总览

| event | data 核心字段 | 前端用途 |
|---|---|---|
| `session_started` | `session_id`, `project_id`, `trace_id` | 初始化会话上下文 |
| `task_started` | `session_id`, `task_run_id`, `user_message` | 标记任务开始 |
| `task_progress` | `session_id`, `task_run_id`, `node_name`, `progress`, `message` | 进度条、阶段描述 |
| `node_completed` | `session_id`, `task_run_id`, `node_name`, `progress` | 节点完成轨迹 |
| `tool_started` | `session_id`, `task_run_id`, `tool_name`, `title`, `detail`, `step_id`, `route_id` | 运行时事件面板（工具开始） |
| `tool_completed` | `session_id`, `task_run_id`, `tool_name`, `title`, `detail`, `step_id`, `route_id`, `status_code` | 运行时事件面板（工具完成） |
| `token_emitted` | `session_id`, `task_run_id`, `token` | AI 正文流式输出 |
| `thought_emitted` | `session_id`, `task_run_id`, `token` | AI 思考过程流式输出 |
| `agentic_iteration` | `session_id`, `task_run_id`, `iteration`, `think` | 多轮推理进度 |
| `write_approval_required` | `session_id`, `task_run_id`, `batch_id`, `items[]`, `write_id`, `route_id`, `method`, `path`, `parameters`, `reasoning`, `safety_level` | 渲染审批面板 |
| `approval_pending` | `session_id`, `task_run_id` | 图执行暂停，等待用户决策 |
| `ui_block_emitted` | `session_id`, `task_run_id`, `block_index`, `block_type`, `block_data` | 渲染白名单 UI Block |
| `task_completed` | `session_id`, `task_run_id`, `summary` | 结束态与摘要 |
| `error` | `session_id`, `task_run_id`, `error_code`, `error_message`, `details` | 错误提示与恢复 |

### 4.3 事件详细 Schema

#### `session_started`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `project_id` | `string` | 项目 ID |
| `trace_id` | `string` | 追踪 ID |

#### `task_started`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `task_run_id` | `string` | 任务运行 ID |
| `user_message` | `string` | 用户原始消息 |

#### `task_progress`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `task_run_id` | `string` | 任务运行 ID |
| `node_name` | `string` | 当前节点名称 |
| `progress` | `float` | 进度值（0.0-1.0） |
| `message` | `string \| null` | 进度消息 |

#### `node_completed`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `task_run_id` | `string` | 任务运行 ID |
| `node_name` | `string` | 节点名称 |
| `progress` | `float` | 进度值 |

#### `tool_started`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `task_run_id` | `string` | 任务运行 ID |
| `tool_name` | `string` | 工具名称 |
| `title` | `string` | 事件标题 |
| `detail` | `string \| null` | 详细信息 |
| `step_id` | `string \| null` | 步骤 ID |
| `route_id` | `string \| null` | 路由 ID |

#### `tool_completed`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `task_run_id` | `string` | 任务运行 ID |
| `tool_name` | `string` | 工具名称 |
| `title` | `string` | 事件标题 |
| `detail` | `string \| null` | 详细信息 |
| `step_id` | `string \| null` | 步骤 ID |
| `route_id` | `string \| null` | 路由 ID |
| `status_code` | `int \| null` | HTTP 状态码 |

#### `token_emitted`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `task_run_id` | `string` | 任务运行 ID |
| `token` | `string` | Token 内容（需前端拼接） |

#### `thought_emitted`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `task_run_id` | `string` | 任务运行 ID |
| `token` | `string` | 思考 Token 内容（需前端拼接） |

#### `agentic_iteration`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `task_run_id` | `string` | 任务运行 ID |
| `iteration` | `int` | 当前轮次（从 1 开始） |
| `think` | `string \| null` | 本轮 AI 推理摘要 |

#### `write_approval_required`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `task_run_id` | `string` | 任务运行 ID |
| `batch_id` | `string \| null` | 批量审批任务 ID |
| `items` | `object[]` | 操作项列表（每项含 `write_id`、`method`、`path`、`parameters`、`reasoning`、`safety_level`） |
| `write_id` | `string \| null` | 单条操作 ID（向后兼容） |
| `route_id` | `string \| null` | 接口路由（向后兼容） |
| `method` | `string \| null` | HTTP 方法（向后兼容） |
| `path` | `string \| null` | 接口路径（向后兼容） |
| `parameters` | `object` | 请求参数（向后兼容） |
| `reasoning` | `string` | AI 为什么要执行此写入（向后兼容） |
| `safety_level` | `string` | 安全等级（向后兼容）：`soft_write`、`hard_write`、`critical` |

#### `approval_pending`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `task_run_id` | `string` | 任务运行 ID |

#### `ui_block_emitted`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `task_run_id` | `string` | 任务运行 ID |
| `block_index` | `int` | Block 序号（从 0 开始） |
| `block_type` | `string` | Block 类型，见 [第 5 节 UI Block 白名单](#5-ui-block-白名单) |
| `block_data` | `object` | Block 数据（结构因 block_type 而异） |

#### `task_completed`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string` | 会话 ID |
| `task_run_id` | `string` | 任务运行 ID |
| `summary` | `string \| null` | 任务摘要 |

#### `error`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `string \| null` | 会话 ID |
| `task_run_id` | `string \| null` | 任务运行 ID |
| `error_code` | `string` | 错误代码，如 `TASK_FAILED`、`TASK_CANCELLED`、`STREAM_ERROR` |
| `error_message` | `string` | 错误消息 |
| `details` | `object \| null` | 详细信息 |

---

## 5. UI Block 白名单

自定义 GUI 只需实现以下 8 种 `block_type` 的渲染器：

| block_type | 说明 | 核心字段 |
|---|---|---|
| `text_block` | 文本回答 | `content`（文本内容）、`format`（`plain` / `markdown`） |
| `metric_card` | 指标卡片 | `title`、`metrics[]`（每项含 `label`、`value`、`unit`、`trend`、`trend_value`） |
| `data_table` | 可分页数据表 | `title`、`columns[]`（含 `key`、`label`、`type`）、`rows[]`、`total`、`page`、`page_size` |
| `echart_card` | ECharts 图表 | `title`、`chart_type`（`bar`/`line`/`pie`/`scatter`/`radar`/`gauge`）、`option`（ECharts 配置）、`height` |
| `confirm_panel` | 审批面板 | `approval_id`、`title`、`description`、`action_summary`、`risk_level`、`details[]`、`timeout_seconds` |
| `filter_form` | 参数表单 | `title`、`description`、`fields[]`（含 `key`、`label`、`type`、`required`、`options`）、`session_id`、`request_id` |
| `timeline_card` | 时间线 | `title`、`events[]`（含 `timestamp`、`title`、`description`、`status`） |
| `diff_card` | 差异对比 | `title`、`description`、`items[]`（含 `key`、`old_value`、`new_value`、`change_type`） |

---

## 6. SSE 原始帧示例

### 6.1 `token_emitted` 事件

```text
event: token_emitted
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","token":"根据"}

event: token_emitted
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","token":"您提供的条件"}

event: token_emitted
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","token":"，已为您筛选出 5 条记录。"}
```

### 6.2 `task_progress` 事件

```text
event: task_progress
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","node_name":"agentic_loop","progress":0.35,"message":"正在调用订单查询接口"}
```

### 6.3 `write_approval_required` 事件

```text
event: write_approval_required
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","batch_id":"batch-001","items":[{"write_id":"w-001","method":"POST","path":"/api/orders/approve","parameters":{"order_id":"ORD-2024"},"reasoning":"批量审批待处理订单","safety_level":"hard_write"},{"write_id":"w-002","method":"POST","path":"/api/orders/approve","parameters":{"order_id":"ORD-2025"},"reasoning":"批量审批待处理订单","safety_level":"hard_write"}],"write_id":null,"route_id":null,"method":null,"path":null,"parameters":{},"reasoning":"","safety_level":"soft_write"}
```

### 6.4 `ui_block_emitted` 事件（data_table 类型）

```text
event: ui_block_emitted
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","block_index":0,"block_type":"data_table","block_data":{"block_type":"data_table","title":"待审批订单","columns":[{"key":"order_id","label":"订单号","type":"text"},{"key":"amount","label":"金额","type":"number","sortable":true},{"key":"status","label":"状态","type":"tag"}],"rows":[{"order_id":"ORD-2024","amount":1500.00,"status":"pending"},{"order_id":"ORD-2025","amount":2300.50,"status":"pending"}],"total":2,"page":1,"page_size":10}}
```

### 6.5 `task_completed` 事件

```text
event: task_completed
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","summary":"已完成订单查询和排序，共筛选出 5 条待审批订单，按金额从高到低排列。2 条订单已提交审批请求，等待确认。"}
```

---

## 7. 最小集成流程

```
┌────────────┐    POST /stream     ┌────────────┐
│  自定义 GUI  │ ──────────────────→ │  LUI Server │
│            │ ←── SSE 事件流 ───── │            │
│            │    (token/progress/  │            │
│            │     block/approval)  │            │
└─────┬──────┘                     └────────────┘
      │
      │ 收到 write_approval_required
      │ + approval_pending
      ▼
┌────────────┐    POST /resume     ┌────────────┐
│  审批 UI    │ ──────────────────→ │  LUI Server │
│            │ ←── SSE 事件流 ───── │            │
└────────────┘                     └────────────┘
```

**步骤**

1. **发起对话** — `POST /api/chat/stream`，提交 `project_id + content`（可选 `session_id`、`locale`）。
2. **消费 SSE 流** — 按 `event` 类型分发：
   - `token_emitted` / `thought_emitted` → 拼接渲染正文/思考区
   - `task_progress` / `tool_*` / `node_completed` → 渲染执行进度和调用轨迹
   - `ui_block_emitted` → 根据 `block_type` 渲染对应组件
   - `error` → 展示错误提示
3. **处理审批** — 收到 `write_approval_required` + `approval_pending` 时：
   - 渲染审批 UI，展示操作项
   - 用户决策后调用 `POST /api/chat/resume`（`action` + `approved_ids` + `decided_ids`）
   - 收到新的 SSE 流，继续渲染
4. **任务完成** — 收到 `task_completed`，SSE 流自动关闭。
5. **历史回放** — 可调用消息/任务/审批/HTTP 快照接口读取完整历史。

---

## 8. 认证说明

### 8.1 双通道 JWT 认证

LUI-for-All 支持两种 JWT 身份，适用于同一服务器上的多项目终端用户隔离场景。

| JWT Subject | 身份 | 可访问范围 | 签发接口 |
|---|---|---|---|
| `lui-admin` | 管理员 | 全部 `/api/*` 端点 | `POST /api/auth/setup` 或 `POST /api/auth/login` |
| `lui-user` | 终端用户 | `/api/chat/*`、`/api/sessions/*`、`/api/projects/resolve-slug/*`、`/api/auth/me` | `POST /api/auth/user-login` |

### 8.2 JWT 传递方式

| 方式 | 格式 | 适用场景 |
|---|---|---|
| **Authorization Header** | `Authorization: Bearer <jwt>` | 所有端点（推荐） |
| **Query Parameter** | `?token=<jwt>` | SSE 端点（部分 SSE 客户端库不支持自定义 Header） |

### 8.3 终端用户登录流程

1. 前端通过 `GET /api/projects/resolve-slug/{slug}` 获取项目信息（无需认证）。
2. 用户提交凭据到 `POST /api/auth/user-login`。
3. 后端验证凭据并签发 User JWT。

**登录请求示例**

```http
POST /api/auth/user-login
Content-Type: application/json

{
  "project_slug": "my-project",
  "username": "zhangsan",
  "password": "secret123"
}
```

**登录响应**

| 字段 | 类型 | 说明 |
|---|---|---|
| `token` | `string` | User JWT |
| `project_id` | `string` | 项目 ID |
| `project_name` | `string` | 项目名称 |
| `project_slug` | `string` | 项目 slug |
| `role_profile_id` | `string` | 角色画像 ID |

### 8.4 User JWT Payload 结构

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

### 8.5 User JWT 权限边界

- User JWT 只能访问**自己项目**的数据（后端通过 `project_id` 校验）
- 调用 `POST /api/chat/stream` 时，`project_id` 必须与 JWT 中的 `project_id` 一致
- 后端自动注入 `user_context`，Agentic Loop 优先使用用户的目标系统 token 执行操作
- 审计类端点（`task-runs/*` 的 GET 接口）仅限 Admin JWT 访问

### 8.6 不需要认证的端点

以下端点在 JWT 白名单中，无需提供 Token：

- `GET /health`
- `GET /docs`、`GET /redoc`、`GET /openapi.json`
- `GET /api/auth/status`
- `POST /api/auth/setup`
- `POST /api/auth/login`
- `POST /api/auth/user-login`
- `POST /api/auth/forgot-password-hint`

---

## 9. 自定义 GUI 适配建议

| 层级 | 实现要点 |
|---|---|
| **事件层** | 实现统一 SSE 分发器，按 `event` 字段路由到各渲染模块。支持 Query Parameter 方式传递 Token（`?token=<jwt>`），兼容所有 SSE 客户端库。 |
| **组件层** | 实现 8 种 `block_type` 渲染器（见第 5 节）。`text_block` 和 `data_table` 是最常用的两种，优先实现。 |
| **审批层** | 监听 `write_approval_required` + `approval_pending` 事件对，渲染审批 UI；用户决策后调用 `POST /api/chat/resume`。注意传递 `decided_ids` 以确保完整审计落库。 |
| **回放层** | 接入 4 类快照接口（`messages`、`task-runs`、`approvals`、`http-executions`），实现会话历史回放和审计追踪。 |
| **错误处理** | 监听 `error` 事件，根据 `error_code` 决定恢复策略：`TASK_CANCELLED` 可忽略，`TASK_FAILED` / `STREAM_ERROR` 需提示用户重试。 |
| **多语言** | 通过 `locale` 参数控制 AI 响应语言。支持 `zh-CN`、`en-US`、`ja-JP`。 |
