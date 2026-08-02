<div align="center">

# LUI-for-All

**用自然语言，操作你的任何系统。**

*Language User Interface · 零更改接入/移除 · 企业级安全 · 全接口类型覆盖*
</div>

---

> 文档语言：**简体中文** | [English](README.en-US.md) | [日本語](README.ja-JP.md)

> 开发者协议文档：[API 参考](API_REFERENCE.md)（聊天端点 `/api/chat/*` + 管理端点，英文版单一文档）

## 它解决什么问题？

许多后端系统，尤其是**企业系统、办事系统、专业工作系统**往往功能强大，却极难使用——用户必须深入多级菜单、记住筛选项组合、反复填写表单，才能完成一件本可以用一句话描述的事。

**LUI-for-All** 在你现有系统旁边放一个**独立文件夹，不碰你的一行代码**，就能让用户改用自然语言来操作它：

```
用户：「把上周所有待审批的采购单，按金额从高到低给我列出来，超过五万的高亮标出。」

LUI：[自动识别意图 → 调用现有接口 → 渲染数据表 + 高亮标注]
     ✓ 全程不修改你一行已有代码
```

> 它是一层可控、安全、零侵入的 **自然语言操作层**，架在你现有系统之上。

---

### LUI-for-All 在 Claw 生态中的位置

2026 年初，开源 AI Agent **OpenClaw** 以现象级速度席卷全球——GitHub 星标超 30 万登顶榜首，国内外掀起"养虾热"。OpenClaw 让 AI 从"问答机器人"进化为"24 小时数字工人"：它通过 WhatsApp、Telegram 等消息平台接收指令，自主操作你的电脑——执行 Shell 命令、控制浏览器、管理文件、发送邮件，真正实现了**自然语言驱动的本地自动化**。

随后，Claw 生态迅速衍生出 ClawMobile（移动端）、企业级 WorkBuddy、AutoClaw 等众多变体，腾讯云和阿里云提供一键部署，国产模型厂商（Kimi、MiniMax、阶跃星辰）争相适配——一个全新的 Agent 生态已然成形。

**但 Claw 们有一个共同的盲区：它们的手脚伸不到你的业务系统里。**

Claw 擅长的是通用桌面操作——打开浏览器、点击按钮、填写表单。但企业核心系统的操作对象是 **API 接口和数据库**，不是 GUI 元素。对于 ERP 里的采购审批流、CRM 里的客户订单管理、OA 里的多级审批链——Claw 只能退化为"模拟点击"，既不可靠，也无安全保障。

**LUI-for-All 正是为 Claw 生态补上这最后一环：**

| | Claw 系列 | LUI-for-All |
|---|---|---|
| 操作对象 | 本地设备、浏览器、文件系统 | 企业业务系统 API |
| 交互方式 | GUI 自动化（点击/截图） | 原生 API 调用（结构化、可审计） |
| 安全模型 | OS 级权限 | 5 级安全分级 + 人工审批门控 |
| 适用场景 | 个人效率、通用自动化 | 企业业务操作、多系统协同 |

当 Claw 通过 MCP 协议接入 LUI-for-All，它就获得了一双**能伸进企业系统的手**——不是模拟点击，而是通过能力图谱理解接口语义、通过安全策略矩阵管控风险、通过人工审批流保障关键操作。Claw 负责"什么时候做"，LUI 负责"怎么安全地做"。

这意味着：你在 Telegram 里对 Claw 说"把上周所有待审批的采购单按金额排序"，Claw 将这条指令通过 MCP 传给 LUI-for-All，LUI 自动识别意图、调用 ERP 接口、返回结构化数据表——全程可审计、可回溯、写操作需你确认。

---

## 核心亮点与创新

### 1. 零侵入接入，无痛移出

整个 LUI 以 **独立文件夹** 形式挂靠在目标项目旁，对已有代码保有严格的 **只读权限**，所有运行时写操作隔离在 `workspace/` 目录内。**想要移除，只需删除这个文件夹**，原系统完全不受影响，零负担尝试接入。

虽然 LUI 停靠在目标项目文件夹旁时是为单一项目服务（这也是它的特色），但 LUI 同时支持 **多项目同时管理**——你可以一次性无侵入地管理你的所有指定项目，每个项目拥有独立的能力地图、会话记录和权限隔离。

### 2. 双通道认证：管理员 + 项目终端用户

LUI 实现了 **双通道 JWT 认证**，让系统真正对项目管理员和项目所有用户都可用：

- **管理员通道**（`sub=lui-admin`）：项目管理员通过 LUI 独立密码登录，拥有全局管理权限——创建项目、配置能力、管理角色画像、查看审计日志等。
- **用户通道**（`sub=lui-user`）：项目终端用户通过 **目标系统自身的登录接口** 验证凭据，LUI 代理登录并签发受限 JWT。用户只能访问所属项目内其角色画像允许的接口，实现真正的项目级权限隔离。

**角色画像机制**：管理员可为不同角色（如「普通用户」「部门主管」）创建角色画像，系统会以该角色凭据自动探测每条路由的可达性（`RouteAccessibility`），生成精确的接口白名单。未匹配画像的用户将使用默认角色画像。

这意味着：
- 一台设备上的所有后端，都可以作为独立项目接入 LUI
- 每个项目的普通用户，通过项目内建的鉴权系统登录后，即可使用自然语言操作 **自己权限范围内** 的接口
- LUI 成为真正通用、安全的语言接口（Language User Interface）

### 3. OpenAPI + Tree-sitter 双轨发现，适配主流后端框架

系统采用“双层发现管线”：

- 第一层：优先摄取目标项目暴露的 `OpenAPI / Swagger` 文档，快速建立标准路由视图
- 第二层：统一 `Tree-sitter AST` 引擎，从源码中定位路由对应的完整 Handler/函数实现

关键能力包括：

- 统一 `FrameAdapter + get_tree_sitter_query()` 协议，适配器可扩展、可插拔
- 内置主流后端适配：Python（FastAPI/Flask/Sanic）、Node.js（NestJS/Express/Fastify）、Java（Spring Boot）、C#（ASP.NET Core）、Go（Gin/Echo/Fiber/chi）
- 当 OpenAPI 不可达或未暴露时，自动降级为 AST 语义路由发现（通过 `source_path`）
- 自动归一化路径参数风格（如 `:id -> {id}`），降低跨框架匹配误差

最终将路由与源码逻辑共同交给 LLM，生成更可靠的能力地图：

- 每条路由自动归属 `domain`（如：财务、用户管理、审批流）
- 每个能力标记最适合的展现组件（`best_modalities`）
- 每个操作预标注安全等级与是否需要人工确认
- 自动打上「是否被前端真实调用」标签，过滤僵尸接口

无需手动维护映射表，**上游接口或源码一旦变化，重新发现即可同步**。

#### 3.1 7 个代表样例的语法派系覆盖

当前仓库已增加 7 个代表测试样例，并通过两级提取测试（路由发现 + 函数实现提取）。

| 代表样例 | 路由风格派系 | 当前适配器覆盖目标（同派系） | 理论可迁移（需新增适配器） |
|---|---|---|---|
| `fastapi_sample` | Python 装饰器路由（`@router.get` / `@app.post`） | FastAPI、Flask、Sanic、Starlette、Litestar、aiohttp、Bottle、Quart | Ruby Sinatra/Grape、PHP Slim |
| `node_sample` | Node 路由调用链（`app.get()` / `router.post()`） | Express、Fastify、Koa Router、Hono、Elysia、Restify | PHP Laravel/Lumen/Slim、Ruby Hanami |
| `django_sample` | URLConf 集中声明（`path/re_path/include`） | Django、Django REST Framework | Ruby on Rails (`routes.rb`)、PHP Laravel (`routes/web.php`) |
| `springboot_sample` | 控制器注解路由（类前缀 + 方法注解） | Java Spring Boot、Spring MVC | C# ASP.NET Core Attribute Controller、PHP Symfony Attribute Route |
| `aspnetcore_sample` | Minimal API 映射（`MapGet/MapPost/MapMethods`） | ASP.NET Core Minimal API | Java Javalin/Spark、Go net/http + mux |
| `go_gin_sample` | 分组链式注册（`Group + METHOD(path, handler)`） | Gin、Echo、Fiber、Chi | Rust Actix/Axum、PHP Slim |
| `node_native_sample` | 无框架命令式分发（`if (method && path)`） | Node.js built-in http | Python wsgiref/werkzeug 命令式分发、Ruby Rack、PHP Swoole 原生分发 |

说明：

- “当前适配器覆盖目标”表示该适配器按 AST 语法模式可覆盖的同派系框架。
- 当前仓库已实测的是 7 个代表样例本身：`backend/test/test_route_extractor_representative_samples.py`。
- “理论可迁移”表示语法结构高度相似，原则上可提取，但需新增或扩展对应适配器后才算正式支持。

#### 3.2 AST 四范式归一

当前发现链路已统一到 4 个 AST 路由范式，7 个代表样例只是“框架语法代表”，不是新增范式：

- `decorator_metadata`: 注解/装饰器元数据路由（FastAPI、Spring、ASP.NET Controller）
- `call_registration`: 调用式注册路由（Express/Fastify、Gin/Echo/Fiber/Chi、ASP.NET Minimal API）
- `route_table`: 集中式路由表（Django URLConf）
- `imperative_dispatch`: 命令式控制流分发（Node native `if/switch`）

这 4 类最终都会统一输出同一 `RouteSnippet` 结构，再进入同一代码切片与 LLM 上下文注入流程。

#### 3.3 探索层完整流程图（含条件分支）

```mermaid
flowchart TD
    A[discover_project project_id, base_url, openapi_path, source_path] --> B{OpenAPI 摄取成功?}
    B -- 是 --> C[ingest_openapi 生成 RouteMap source=openapi]
    B -- 否 --> D{提供 source_path?}
    D -- 否 --> E[发现失败 直接返回 OpenAPI 错误]
    D -- 是 --> F[ingest_semantic_routes 走 AST 语义发现 生成 RouteMap source=ast]

    C --> G[generate_project_context]
    F --> G
    G --> H[build_capability_graph]

    H --> I{提供 source_path?}
    I -- 否 --> J[跳过源码精准提取 全量走规则兜底]
    I -- 是 --> K[RouteExtractor.extract_batch route_pairs]

    K --> L{检测到适配器?}
    L -- 否 --> M[全部路由 snippet=None]
    L -- 是 --> N[Adapter.extract_all_routes]

    N --> O{Tree-sitter 与 Query 可用?}
    O -- 否 --> P[fallback_extract_all_routes]
    O -- 是 --> Q[遍历源码 AST Query captures 转 RouteSnippet]

    P --> R[按目标路由逐条匹配]
    Q --> R

    R --> S{route_id 精确命中?}
    S -- 是 --> T[选择候选中 code 最长片段]
    S -- 否 --> U{path_matches 模糊命中?}
    U -- 是 --> T
    U -- 否 --> V[该路由 snippet=None]

    T --> W[命中片段按约 32K 分块]
    V --> W
    M --> W

    J --> X[组装能力图谱]
    W --> Y{存在可分析分块?}
    Y -- 否 --> Z[analysis_map 为空]
    Y -- 是 --> AA[并发 LLM 分析每个分块]
    AA --> AB[合并 analysis_map]
    Z --> X
    AB --> X

    X --> AC{该路由有 AI 结果?}
    AC -- 是 --> AD[使用 AI 域 安全 摘要]
    AC -- 否 --> AE[按 HTTP Method 规则兜底]

    AD --> AF[写入 RouteMap Capability 与 Project 状态]
    AE --> AF
    AF --> AG[discover 完成]
```

### 3. 全接口类型覆盖：即时 / 流式 / 分页，AI 自动识别并适配

系统在建图阶段自动分析每条路由的响应模式（`response_mode`），将其归入三类：

| 响应模式 | 典型场景 | AI 采集策略 |
|---|---|---|
| `instant` | 普通 CRUD、查询、写操作 | 一次请求-响应，直接返回 |
| `streaming` | SSE 实时推送（指标流、告警流、通知流） | `stream_call`：时间窗口 / 事件计数 / 快照，支持心跳过滤与 `[DONE]` 终止检测 |
| `paginated` | 游标分页（`next_cursor`）、偏移分页（`page/page_size`） | `stream_call`：自动翻页，支持游标和偏移两种分页协议，自动探测并适配 |

运行时，AI 在能力列表中看到带 `📡SSE流式` 或 `📄分页追加` 标记的接口后，会自动选择 `stream_call` 动作而非普通 `call`，按策略采集数据后返回压缩汇总结果（含采样率、统计摘要），而非将原始流直接灌给用户。

**硬限制保障**：最大采集时长 60s、最大事件数 500、单事件 4KB、总结果 32KB，超出自动均匀采样保留首尾，AI 无法覆盖。

### 4. 8 种白名单 UI 组件，从根源杜绝渲染注入

模型 **永远不允许** 输出原始 HTML / JS / CSS，从根源掐死前端注入攻击的可能性。所有界面元素均通过严格的声明式 JSON 协议下发，前端只渲染以下 8 种白名单组件：

| 组件类型 | 用途 |
|---|---|
| `text_block` | 默认自然语言回答 |
| `metric_card` | 关键指标面板 |
| `data_table` | 可分页数据表 |
| `echart_card` | 配置驱动图表（ECharts） |
| `confirm_panel` | 高危操作审批拦截器 |
| `filter_form` | 参数补充收集 |
| `timeline_card` | 事件序列与流转 |
| `diff_card` | 对照与变化展示 |

灵感源自 Google A2UI 协议，彻底关闭大模型越权渲染的攻击面。

### 5. LangGraph 多层执行内核 + 人工介入审核

核心任务流水线由 LangGraph 编排，具备完整的持久化检查点。

#### 图一：顶层节点路由

```mermaid
flowchart LR
    START(["💬 用户消息"]) --> AE["agent_entry\n加载能力地图\nLLM 判断复杂度"]

    AE -- "direct" --> D_END(["END ✓ 直接回答"])
    AE -- "error"  --> E_END1(["END ✗ 异常"])
    AE -- "agentic" --> AL["agentic_loop\n↩ ReAct 循环"]

    AL -- "error"        --> E_END2(["END ✗ 异常"])
    AL -- "done=False"   --> AL
    AL -- "done=True"    --> SUM["summarize\nLLM 汇总"]

    SUM --> EB["emit_blocks\nUI Block 装配"]
    EB  --> F_END(["END ✓ SSE 推送"])
```

#### 图二：agentic_loop 内部（ReAct + 安全裁定）

```mermaid
flowchart TD
    IN(["进入本轮 Loop"]) --> CHK{"iterations ≥ 10？"}
    CHK -- 是 --> FORCE["agentic_done=True\n强制终止"]
    CHK -- 否 --> LLM["LLM 推理\nSystem Prompt + 对话历史"]

    LLM --> ACT{"action"}
    ACT -- "finish"  --> DONE["agentic_done=True"]
    ACT -- "unknown" --> UNK["强制结束 + 告警"]
    ACT -- "call_tools" --> SEC{"安全等级"}

    SEC -- "🟢 readonly_safe\n🟡 readonly_sensitive" --> EXEC["直接 HTTP 执行"]
    SEC -- "🟠 soft_write\n🔴 hard_write\n🔐 critical" --> INT["interrupt()\n推送 ConfirmPanel"]

    INT --> APV{"用户审批"}
    APV -- "✅ 批准" --> EXEC
    APV -- "❌ 拒绝" --> SKIP["跳过 + 审计日志"]

    EXEC --> OBS["收集 ExecutionArtifact\n追加 Observation"]
    SKIP --> OBS
    OBS --> NEXT(["iterations+1\n返回上层路由"])
```

#### 图三：收尾链路（summarize → emit_blocks）

```mermaid
flowchart LR
    ART(["ExecutionArtifacts"]) --> SUM["summarize\nLLM 结构化总结\n→ summary_text"]

    SUM --> VIZ{"需要可视化？"}
    VIZ -- 是 --> PICK["选取白名单组件\ndata_table / echart_card\nmetric_card / timeline_card\ndiff_card / confirm_panel …"]
    VIZ -- 否 --> TXT["text_block"]

    PICK --> SER["序列化 ui_blocks JSON"]
    TXT  --> SER
    SER  --> SSE(["SSE 推送 → 前端渲染"])
```

**5 级安全**：`readonly_safe` → `readonly_sensitive` → `soft_write` → `hard_write` → `critical`，任何写操作均通过 LangGraph `interrupt()` 硬性暂停，前端唤出 `ConfirmPanel`，用户确认后 Graph 从断点恢复，拒绝则跳过并记录审计日志。

### 6. AG-UI 协议 + SSE 实时事件流

前后端通信基于 Server-Sent Events，完整实现 AG-UI 事件流协议：
- LangGraph 每个节点的进度实时推送到前端
- 思考内容（Reasoning）流式显示，可折叠
- 审批节点触发时，前端自动唤出 `ConfirmPanel`，无需轮询

### 7. 全链路 OpenTelemetry 可观测

每一次对话，从用户输入到最终渲染，全链路注入统一 `Trace ID`：
- FastAPI 请求层
- LangGraph 节点执行层
- HTTP 执行器层

不是黑盒，每一步决策均可溯源审计。

### 8. Agent Matchbox 多模型网关

内置 **Agent Matchbox** 多模型路由网关，支持多平台 LLM 统一调度、Token 配额管理与用量统计，切换模型无需改动业务代码。

### 9. Docker / 裸机双环境自动连通

- 导入示例项目时，系统会自动识别运行环境并选择可达地址：
    - Docker 内优先使用容器服务名（如 `sample-fastapi:8010`）
    - 本机运行优先使用 `localhost` 端口
- 连通性测试与路由拉取接口支持 `source_path`，在 OpenAPI 不可用时自动切换 AST 发现，导入流程不再被单点阻塞
- **Docker 环境源码路径感知**：当 LUI 运行在容器中时，系统会自动检测源码路径是否可达；若不可达，会提示用户通过 `volumes` 将目标项目源码目录挂载到 LUI 容器内，并给出具体的挂载示例
- **源码路径验证端点**：新增 `POST /api/projects/verify-source-path`，前端在导入项目时可先验证路径可达性、框架识别和权限状态，获得即时反馈后再提交导入

### 10. Chat 端点可插拔前端协议（支持自定义 GUI）

LUI-for-All 将"聊天能力内核"与"前端呈现层"解耦：

- 开发者可直接对接 `chat` 端点，替换现有前端 UI，而无需改动后端执行链路
- 协议完整覆盖当前前端元素：AI 工作进度、HTTP 调用记录、审批请求/审批记录、AI 思考流、8 类 UI Block
- 数据类型边界清晰：流式事件走 SSE，历史/审计回放走普通 JSON 接口
- `/api/chat/*` 是自定义 GUI 的**唯一推荐接入接口**；内部前端使用的 `/api/sessions/*` 为遗留内部接口

详细字段与事件清单见：[API 参考 — 聊天端点 Part A](API_REFERENCE.md#part-a--chat-endpoints)

管理类接口（项目管理、认证、设置、LLM 配置、审计查询等）见：[API 参考 — 管理端点 Part B](API_REFERENCE.md#part-b--management-endpoints)

### 11. 通过 MCP 与 OpenClaw 联动（跨渠道执行入口）

> Claw 生态定位详见上方 [LUI-for-All 在 Claw 生态中的位置](#lui-for-all-在-claw-生态中的位置)。

OpenClaw 的最大价值，是把自然语言直接变成可持续执行的自动化，不需要人盯着它一步一步点。你只要下指令，它就能在自己的电脑、账号和渠道里持续跑下去，做真正的无人值守任务。

和 LUI-for-All 联动后，价值会更直接：

- OpenClaw 负责无人值守的自然语言自动化，LUI-for-All 负责把动作落到具体专属项目里
- 用户可以直接在 OpenClaw 里下自然语言任务，再通过 LUI 的 MCP 接口深入项目内部的页面、接口和工作流
- 我们保留安全分级、人工确认、SSE 进度和 HTTP 调用记录，既能放手自动跑，也能追踪每一步

接入步骤很简单：

1. 启动 OpenClaw，让它先作为自然语言自动化入口跑起来
2. 在 OpenClaw 侧把 LUI-for-All 配成 MCP 工具，或者把 OpenClaw 会话桥接到 MCP 客户端
3. 在 LUI-for-All 里配置 MCP 访问令牌和网关地址，让 OpenClaw 能碰到你的专属项目
4. 先用一个只读能力做联调，再逐步接入有审批的业务操作

---

## 快速开始

### 环境要求

- Python 3.13（推荐 Conda 管理）
- Node.js 18+ + pnpm 10
- 推荐目标项目暴露 OpenAPI 文档（`/openapi.json` 或文件路径）
- 若未暴露 OpenAPI，需提供可访问源码路径（`source_path`）以启用 AST 路由发现

### 1. 克隆项目

```bash
git clone https://github.com/your-org/lui-for-all.git
cd lui-for-all
```

### 2. 后端安装与配置

```bash
# 创建并激活 Conda 环境
conda create -n lui python=3.11 -y
conda activate lui

# 安装依赖
pip install -r backend/requirements.txt

# 复制配置文件（macOS/Linux）
cp backend/.env.example backend/.env

# Windows PowerShell 可用：
# Copy-Item backend/.env.example backend/.env
```

配置说明（重要）：

- `backend/.env`：用于 LUI 全局配置（`LUI_*`），例如 `LUI_DB_PATH`、`LUI_MCP_API_TOKEN`。
- Matchbox 主密钥 `LLM_KEY` 不在 `backend/.env` 中读取。
- 首次启动后，系统会自动在 `workspace/agent_matchbox/.env` 生成并读取 `LLM_KEY`。
- 如需自定义 Matchbox 目录，请在系统环境变量中设置 `AGENT_MATCHBOX_HOME`。

### 3. 前端安装

```bash
cd frontend
pnpm install
```

### 4. 启动服务

```bash
# 终端 1：启动后端
cd backend
conda run -n lui uvicorn app.main:app --reload --port 6689

# 终端 2：启动前端
cd frontend
pnpm dev
```

启动后可先做健康检查：

```bash
# macOS/Linux
curl http://localhost:6689/health

# Windows PowerShell
Invoke-RestMethod http://localhost:6689/health
```

### 5. 接入你的第一个项目

打开 `http://localhost:5173`，点击「新建项目」，优先填写 OpenAPI 地址（如 `http://your-app/openapi.json`）。

如果目标系统没有暴露 OpenAPI，也可以仅提供源码路径 `source_path`，系统会自动切换为 AST 语义发现并继续建图。

**Docker 部署时**：若 LUI 运行在容器中，而目标项目源码位于宿主机或其他容器，需要在 `docker-compose.yml` 中通过 `volumes` 将源码目录挂载到 LUI 容器内，例如：

```yaml
services:
  lui-backend:
    volumes:
      - lui_workspace:/app/workspace
      # 挂载目标项目源码（只读即可）
      - /path/on/host/my-project:/app/projects/my-project:ro
```

然后在 `source_path` 中填写容器内挂载路径 `/app/projects/my-project`。系统会在验证路径时自动检测容器环境并给出卷挂载提示。

系统将自动完成能力发现与建模，通常耗时 10-30 秒。

完成后，在对话框中直接用自然语言向你的系统提问。

> **提示**：LUI 支持同时管理多个项目。你可以重复「新建项目」流程接入任意数量的后端系统，每个项目拥有独立的能力地图、会话和权限配置。

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                    前端 (Vue 3 + Vite)                       │
│  ChatPage  ProjectsPage  SettingsPage                       │
│  SSE 事件流 ──── AG-UI 协议 ──── UI Block 渲染器              │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────────────┐
│                  后端 (FastAPI)                               │
│  /api/chat  /api/sessions  /api/projects  /api/settings     │
│       │                │                                     │
│  LangGraph 编排器    Project Modeler                         │
│  ┌────────────┐      ┌──────────────────────────┐           │
│  │ 意图解析节点│      │ OpenAPI + AST 路由发现     │           │
│  │ 能力路由节点│      │ 能力建模与语义聚类         │           │
│  │ 规划节点   │      │ 能力地图持久化             │           │
│  │ 安全裁定节点│      └──────────────────────────┘           │
│  │ HTTP执行节点│                                              │
│  │ 汇总渲染节点│  ←── Agent Matchbox (多模型网关)             │
│  └────────────┘                                              │
│       │                                                      │
│  SQLite (lui.db + checkpoints.db)                           │
└─────────────────────────────────────────────────────────────┘
```

### 关键目录结构

```
lui-for-all/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI 路由层 (chat, projects, sessions, settings)
│   │   ├── graph/         # LangGraph 状态机定义
│   │   ├── orchestrator/  # 任务编排状态与节点
│   │   ├── discovery/     # OpenAPI 摄取与能力建模
│   │   ├── runtime/       # SSE 事件发射器
│   │   ├── llm/           # Agent Matchbox 网关 + 提示词
│   │   ├── models/        # SQLAlchemy ORM 模型
│   │   └── schemas/       # Pydantic 数据契约
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/         # ChatPage, ProjectsPage
│   │   ├── stores/        # Pinia 状态 (session, project)
│   │   ├── components/    # UI Block 渲染组件
│   │   └── api/           # HTTP / SSE 客户端
│   └── package.json
├── workspace/             # 运行时隔离沙箱（自动生成）
│   ├── lui.db
│   └── checkpoints.db
└── LUI-for-all_Execution_Plan.md
```

---

## 设计边界

| LUI-for-All 是什么 | LUI-for-All 不是什么 |
|---|---|
| ✅ 自然语言操作层 | ❌ 简易API to MCP |
| ✅ 接口能力编排器 | ❌ RPA / GUI 点选自动化 |
| ✅ 只读安全默认，写操作需审批 | ❌ 无安全界限 CRUD 的系统 |
| ✅ 声明式 UI Block 增强回答 | ❌ 前端重写器 / 低代码生成器 |
| ✅ 零侵入挂靠在已有系统旁 | ❌ 替换、侵入已有系统 |

---

## 路线图

- [x] MVP：FastAPI + LangGraph 核心流水线
- [x] OpenAPI 能力自动发现与建模
- [x] 8 种 UI Block 白名单组件
- [x] AG-UI SSE 协议 + 实时流
- [x] 人工确认（Human-in-the-loop）拦截器
- [x] Agent Matchbox 多模型网关
- [x] Tree-sitter AST 语义路由解析（支持无 OpenAPI）
- [x] 流式接口全类型覆盖（SSE / 游标分页 / 偏移分页 / 长轮询）
- [ ] 能力地图可视化管理界面
- [x] 多项目隔离 + 终端用户 JWT 双通道认证（管理员 + 项目用户）
- [ ] 私有化部署文档

---

## 开源许可

本项目采用 Apache License 2.0，详见 `LICENSE`。

Copyright (c) 2026 Mournight (AIdeaStudio)

---

<div align="center">

*让语言成为界面。*

</div>
