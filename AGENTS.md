# AGENTS.md — AI 协作规范

本文件为所有 AI（含 Kilo 及其他编码 Agent）在本仓库工作时的强制规范。除本文件外，请同时遵守全局 `~/.config/kilo/AGENTS.md`。

---

## 1. API 端点文档同步（强制 · 最高优先级）

### 1.1 唯一事实来源

`API_REFERENCE.md` 是本项目**所有 HTTP 端点的唯一事实来源（Single Source of Truth）**，英文版单一文档，内部用醒目注释 banner 分为两部分：

- **Part A — Chat Endpoints**（`/api/chat/*`）：自定义 GUI 接入接口。
- **Part B — Management Endpoints**（`/api/*` 中除 `/api/chat` 外的全部、`/mcp`、`/health`）：项目管理、认证、角色画像、审计、审批、设置、LLM 模型管理、MCP 协议。

### 1.2 强制同步规则

> 🔴 **任何 AI 或开发者只要对任意端点进行了新增、删除或修改，就必须在同一次变更中同步更新 `API_REFERENCE.md`。没有例外。**

"端点增删改"包括但不限于：

- 新增或删除一个 HTTP 路由（含聊天端点与管理端点，含 MCP tool）；
- 修改端点的 **路径 / HTTP 方法 / 认证方式 / 传输方式（JSON / SSE）**；
- 修改 **请求体字段、查询参数、路径参数**（新增、删除、改名、改类型、改必填、改默认值）；
- 修改 **响应字段、状态码、错误码、响应模型**；
- 新增、删除或修改 **SSE 事件类型**（Part A 第 4 节）或其 payload schema；
- 新增、删除或修改 **UI Block 类型**（Part A 第 5 节白名单）；
- 修改端点所属源码文件路径（文档中 `Source:` 标注）。

### 1.3 执行清单（改完代码后逐项确认）

1. 定位变更涉及的端点属于 **Part A** 还是 **Part B**（按命名空间判断）。
2. 更新对应章节的「Endpoint Overview」总览表。
3. 更新对应「Detailed Endpoint Description」小节（请求/响应/参数/错误码/示例）。
4. 若涉及请求或响应模型，同步更新「Request/Response Models」表。
5. 若涉及 SSE 事件或 UI Block，同步更新 Part A 第 4 / 第 5 节。
6. 自检：文档描述与 `backend/app/api/*.py`、`backend/app/mcp/server.py` 中的实际路由定义是否完全一致。

### 1.4 禁止行为

- ❌ 禁止只改代码不改文档。
- ❌ 禁止新建其他 API 文档文件来替代 `API_REFERENCE.md`（保持单一文档）。
- ❌ 禁止把 `API_REFERENCE.md` 拆分回多个语言版本或多份文件。
- ❌ 禁止删除或弱化 Part A / Part B 之间的 banner 注释分隔。
