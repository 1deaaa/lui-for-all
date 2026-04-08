# Chat 端点集成协议（支持自定义 GUI）

本文档定义 LUI-for-All 的统一聊天协议，目标是让开发者可以直接接入 `chat` 端点构建自己的 GUI，而不依赖仓库内置前端。

## 1. 设计目标

- 聊天主链路统一走 `chat` 命名空间。
- 前端只需要实现“事件渲染 + 数据块渲染”，即可复用完整能力。
- 保持和内置前端一致的数据表达：AI 进度、HTTP 调用、审批请求、审批记录、思考流、UI Block。

## 2. 传输类型总览

| 数据 | 端点 | 传输类型 | Content-Type | 说明 |
|---|---|---|---|---|
| 启动新对话并流式执行 | `POST /api/chat/stream` | SSE | `text/event-stream` | 自动创建 task_run 并开始推流 |
| 审批后恢复执行 | `POST /api/chat/resume` | SSE | `text/event-stream` | 同一 task_run 断点续跑 |
| 项目历史会话列表 | `GET /api/chat/projects/{project_id}/sessions` | 普通 HTTP JSON | `application/json` | 指定项目的会话列表（分页） |
| 会话详情 | `GET /api/chat/sessions/{session_id}` | 普通 HTTP JSON | `application/json` | 会话状态、标题、thread 等 |
| 会话消息快照 | `GET /api/chat/sessions/{session_id}/messages` | 普通 HTTP JSON | `application/json` | 含历史文本、思考、审批块、HTTP 摘要 |
| 单条消息详情 | `GET /api/chat/sessions/{session_id}/messages/{message_id}` | 普通 HTTP JSON | `application/json` | 按消息 ID 获取具体消息 |
| 任务快照 | `GET /api/chat/task-runs/{task_run_id}` | 普通 HTTP JSON | `application/json` | 含 `ui_blocks`、`execution_artifacts` |
| 任务事件回放 | `GET /api/chat/task-runs/{task_run_id}/events` | 普通 HTTP JSON | `application/json` | Event Sourcing 回放 |
| 审批记录 | `GET /api/chat/task-runs/{task_run_id}/approvals` | 普通 HTTP JSON | `application/json` | 审批请求和审批结论 |
| HTTP 调用记录 | `GET /api/chat/task-runs/{task_run_id}/http-executions` | 普通 HTTP JSON | `application/json` | 每次工具调用对应的 HTTP 记录 |

说明：

- SSE 帧格式为标准 `event + data`。
- 普通 HTTP 数据全部为 JSON 对象，不返回二进制流。

## 3. SSE 事件协议

### 3.1 事件帧格式

```text
event: <event_name>
data: { ...json payload... }
```

### 3.2 关键事件（与内置前端一致）

| event | 类型 | 主要字段 | 前端用途 |
|---|---|---|---|
| `session_started` | SSE | `session_id`, `project_id`, `trace_id` | 初始化会话上下文 |
| `task_started` | SSE | `task_run_id`, `user_message` | 标记任务开始 |
| `task_progress` | SSE | `node_name`, `progress`, `message` | 进度条、阶段描述 |
| `node_completed` | SSE | `node_name`, `progress` | 节点完成轨迹 |
| `tool_started` | SSE | `tool_name`, `title`, `detail`, `route_id` | 运行时事件面板 |
| `tool_completed` | SSE | `tool_name`, `status_code`, `route_id` | HTTP 调用状态记录 |
| `token_emitted` | SSE | `token` | AI 正文流式输出 |
| `thought_emitted` | SSE | `token` | AI 思考过程流式输出 |
| `agentic_iteration` | SSE | `iteration`, `think` | 多轮推理进度 |
| `write_approval_required` | SSE | `batch_id`, `items[]`, `write_id`, `reasoning`, `safety_level` | 渲染审批面板 |
| `approval_pending` | SSE | `session_id`, `task_run_id` | 图执行暂停，等待用户决策 |
| `ui_block_emitted` | SSE | `block_index`, `block_type`, `block_data` | 渲染白名单 UI Block |
| `task_completed` | SSE | `summary` | 结束态与摘要 |
| `error` | SSE | `error_code`, `error_message`, `details` | 错误提示与恢复 |

## 4. UI Block 白名单（渲染协议）

自定义 GUI 只需要实现以下 `block_type` 的渲染器：

| block_type | 说明 |
|---|---|
| `text_block` | 文本回答 |
| `metric_card` | 指标卡片 |
| `data_table` | 表格 |
| `echart_card` | 图表 |
| `confirm_panel` | 审批面板 |
| `filter_form` | 参数表单 |
| `timeline_card` | 时间线 |
| `diff_card` | 差异对比 |

## 5. 最小集成流程

1. 调用 `POST /api/chat/stream`，提交 `project_id + content (+ session_id)`。
2. 持续消费 SSE：
   - `token_emitted` 渲染正文。
   - `thought_emitted` 渲染思考区。
   - `task_progress` / `tool_*` 渲染执行进度和调用轨迹。
   - `ui_block_emitted` 根据 `block_type` 渲染组件。
3. 收到 `write_approval_required` 时，渲染审批 UI。
4. 用户决策后调用 `POST /api/chat/resume`：
   - `action`: `approve` 或 `reject`
   - `approved_ids`: 允许执行的 write_id 列表
   - `decided_ids`: 当前审批面板涉及的全部 write_id（建议传，便于完整落审计结果）
5. 任务结束后，如需回放，调用消息/审计快照接口读取完整历史。

## 6. 请求示例

### 6.1 启动新任务

```http
POST /api/chat/stream
Content-Type: application/json

{
  "project_id": "project-123",
  "content": "把今天待审批订单按金额排序",
  "session_id": "optional-session-id",
  "locale": "zh-CN"
}
```

### 6.2 审批后恢复

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
  "locale": "zh-CN"
}
```

### 6.3 获取指定项目历史会话列表

```http
GET /api/chat/projects/project-123/sessions?limit=50&offset=0
```

### 6.4 获取单条消息详情

```http
GET /api/chat/sessions/session-123/messages/msg-123
```

## 7. 自定义 GUI 适配建议

- 事件层：实现统一 SSE 分发器（按 `event` 路由到各渲染模块）。
- 组件层：实现 8 种 `block_type` 渲染器。
- 回放层：接入 `messages + task-runs + approvals + http-executions` 四类快照接口。
- 审批层：收到 `write_approval_required` 后，调用 `chat/resume` 发回用户决策。

做到以上四点，即可“替换 UI 不替换能力内核”。
