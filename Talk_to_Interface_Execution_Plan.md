# Talk-to-Interface 项目完整执行计划 (MVP版)

## 一、 项目愿景与核心需求

“Talk-to-Interface”的目标是将现有的前后端项目，从以 GUI 为主的交互方式，提供一套独立的以 LUI（自然语言用户界面）为主的交互方式。
过去用户需进入复杂的图形界面，点菜单、找页面、填表单、看表格、切筛选、点按钮，才能完成任务。
而这个产品希望让用户优先通过自然语言表达目标，由系统去理解任务、调用现有系统能⼒、整理结果，并用自然语言回复用户。
只有在“纯文字不足以表达”时，系统才按需临时生成小型界面组件作为补充表达手段。

### 十大核心产品原则：
1. **服务“已有系统”**：不是从零开发新应用，而是作为一个文件夹**无痛接入、无痛移出**已有的项目（尤其是操作繁琐的管理、运营或内部业务系统）。
2. **把任务从页面操作提升为语言操作**：用户直接描述目标，系统负责把话语翻译成对现有系统接口能力的调用组合。
3. **真正理解项目能力**：系统不能盲读，要全自动为项目进行路由与接口建模，生成系统的“能力地图”。
4. **任务优先 (Task-First)**：关注“用户要解决的问题”，而不是将话语生硬地一比一映射成接口 API 调用。
5. **默认绝对安全隔离**：对已有项目代码**仅有绝密只读权限**；只能在自己的 `workspace/` 目录写文件；默认仅处理只读低危请求，其余写操作、破坏性操作必须走审批确认流阻断。
6. **提供完整日志和审计轨迹**：每一步动作（如何理解指令、选择了什么能力栈、发去了什么请求、为何渲染图表、审批轨迹）必须事件溯源式完整落库存证，非黑盒。
7. **“文本为主，组件为辅”的 UI 观**：文本是永远的主回答。只有文本效率底下时，才去渲染小块声明式组件（如表单/数据榜/折线图），它们是短命且服从当前任务的。
8. **重排现有系统的交互主次**：实现“指令为主界面为辅”，把原有的系统页面级入口重组。
9. **划清定位边界**：不是死板的 OpenAPI Chat，不是基于 GUI 点选的自动化脚本 RPA，更不是随意发散生成的重写前端。它被局限为一层稳定可控的自然语言操作层。
10. **聚焦落地场景**：系统首先应用在功能复杂、筛选项巨多的企业后台（这些页面正是最该被“嘴替”的高价值高成本区域）。

---

## 二、 MVP 阶段架构与固定技术栈（版本已锁定）

针对 MVP 阶段的高效交付要求，整体技术栈已调整并精简：

### 1. 后端主栈
- **Python**：通过标准的 Conda 环境与 `requirements.txt` 管理依赖（**使用本机现有的名为的llm环境 里面有大量所需环境**）。
- **FastAPI**：应用主服务框架。
- **Pydantic v2**：应用层唯一的数据契约层和类型系统（包含协议与设定）。
- **LangGraph 1.x**：系统唯一任务编排、状态机、人工确认（Human-in-the-loop）框架。不使用预发布的 2.0 版。
- **httpx**：统一的 HTTP 请求执行客户端。
- **SQLAlchemy 2**：唯一的数据库 ORM（集成 Pydantic `from_attributes=True` 支持）。
- **SQLite + aiosqlite**：**MVP阶段替代 PostgreSQL 和 Redis**。LangGraph 采用 `langgraph-checkpoint-sqlite` 作为持久化存储节点，主业务数据也写在本地 SQLite 中（存储于 `workspace/lui.db` 和 `workspace/checkpoints.db`）。没有 Alembic，直接使用 `create_all` 构建元数据。

### 2. 前端主栈
- **Vue 3.5.x + TypeScript**：前端主框架。
- **Vite 7.x**：构建工具（不用最新的 Vite 8 以避开生态不兼容风险）。
- **Vue Router 4** + **Pinia 3**：核心路由与状态管理。
- **Element Plus 2.13.x**：基础组件库。
- **Apache ECharts 6**：用于数据图表展现。
- **pnpm 10**：唯一的 Node 模块依赖管理工具。

### 3. 数据层与设计模式
- **模型分离**：Pydantic 专管校验与 Schema，SQLAlchemy 专管数据库存储，二者解耦。
- **SSE 推送**：放弃 WebSocket，前端通过 Server-Sent Events 获取实时流的更新。
- **UI Block 轻量规范**：借鉴 A2UI 和 AG-UI 思想，全系统只允许 8 种白名单组件。模型绝不允许输出自定义的 HTML、JS、前端框架源码或样式。

---

## 三、 功能子系统详细设计

### 1. Project Modeler (OpenAPI 摄取驱动)
**MVP 阶段暂不考虑 Git 解析，而是最大化利用现代后端框架自动导出的 API 定义规范。**
- **确定性提取优先**：假设目标项目为 FastAPI，优先利用其原生的 `/openapi.json` 端点或文件进行摄取。通过标准的 OpenAPI SDK（如 `openapi-core`）立刻获得 80% 的确定性能力与元数据。
- **发现闭环**：通过 OpenAPI 摄取生成基础拓扑后，再配合终端日志与简单正则扫描器（如寻找 `axios`调用痕迹），并搭配 AI 进行语义解释。后续只需略微修改提取插件策略，即可轻松适配 NestJS、SpringDoc 等其他提供 Swagger/OpenAPI 的框架。
- **能力图谱 (Capability Graph) 明确定义**：生成的能力地图必须强制遵循 Pydantic 定义，并在输出时必须包含具体的 `domain`、`best_modalities`（最佳展现组件）、`requires_confirmation`（是否需要拦截）以及 `user_intent_examples`，为后续 LangGraph 路由节点提供可依赖的物理锚点。

### 2. 声明式 UI 与事件流协议 (直接对接业界标准)
**绝不重复造通信通信双端协议的轮子，全盘引入以下成熟规范：**
- **A2UI 声明式规范**：基于 Google 的 A2UI 思想，模型只输出 JSON Lines 格式的交互描述流。只允许模型挑选内置白名单的安全组件（如 `metric_card` 等），而非直接输出底层 Web 代码（避开渲染投毒）。这确保了严格数据格式跨端安全分发。
- **AG-UI 事件状态流**：结合由 CopilotKit 发扬的 AG-UI 协议。前后端通信不依靠自创字典结构，而是基于原生 SSE（Server-Sent Events）实现 Agent 侧内部运转（如 LangGraph checkpoint 进度、权限审批节点）和 UI 表现意图（图表打平）的双向无缝同步，天然对接 LangGraph 工作流进度上链。

系统目前白名单限定 8 种渲染器块：
1. `text_block` (默认文本反馈)
2. `metric_card` (数据面板)
3. `data_table` (可分页数据表)
4. `echart_card` (配置驱动图表)
5. `confirm_panel` (审批放流器)
6. `filter_form` (补充参数搜集器)
7. `timeline_card` (事件节点序列与流转)
8. `diff_card` (对照与变化)

### 3. 执行权限配置 (Safety Level)
所有的请求必须匹配以下的安全分级：
- `readonly_safe`: 直接代理执行
- `readonly_sensitive`: 直接执行，并在返回至 LLM/UI 时触发字段级脱敏拦截
- `soft_write`: 人工确认必须，使用 graph 的 interrupt，通过后执行
- `hard_write / critical`: MVP阶段**绝对阻断拦截**

---

## 四、 仓库工程目录架构

```text
talk-to-interface/
│
├── backend/                              # ===== Python 后端 =====
│   ├── requirements.txt                  # 定义所有 Python 依赖
│   ├── .env.example                      # 环境变量模板
│   │
│   └── app/
│       ├── __init__.py
│       ├── main.py                       # FastAPI 应用入口，配置 CORS / SSE
│       ├── config.py                     # Pydantic Settings
│       ├── db.py                         # SQLAlchemy Session + create_all
│       │
│       ├── models/                       # SQLAlchemy ORM 模型
│       │   ├── project.py                # 项目/发现状态/GIT Hash等属性
│       │   ├── session.py                # 存储会话记录
│       │   ├── task.py                   # task_runs/task_events (Event Sourcing)
│       │   └── audit.py                  # policy_verdicts / http_executions 等审计用大表
│       │
│       ├── schemas/                      # Pydantic v2 双端共享协议规范
│       │   ├── route_map.py              # 路由的物理声明
│       │   ├── capability.py             # RouteMap 之上的逻辑聚合
│       │   ├── ui_block.py               # 8种白名单 Schema
│       │   ├── event.py                  # SSE 推送的联合类型流规范
│       │   ├── policy.py                 # 分级策略与判定
│       │   └── task.py                   
│       │
│       ├── api/                          # FastAPI REST 接口
│       │   ├── projects.py               # 导入及触发分析
│       │   ├── sessions.py               # SSE、会话流转接口
│       │   ├── approvals.py              # 审批回调口
│       │   └── audit.py                  
│       │
│       ├── graph/                        # LangGraph 核心编排流
│       │   ├── state.py                  
│       │   ├── builder.py                
│       │   └── nodes/                    # 严格按业务划分的功能图节点
│       │       ├── parse_intent.py
│       │       ├── select_capabilities.py
│       │       ├── draft_plan.py
│       │       ├── policy_check.py
│       │       ├── request_params.py
│       │       ├── approval_gate.py      # LangGraph Interrupt 持久化锚点
│       │       ├── execute_requests.py   # executor 衔接
│       │       ├── summarize.py 
│       │       ├── decide_modality.py    # 决策响应所需的展现形态 UI Blocks
│       │       ├── emit_blocks.py
│       │       └── persist_audit.py      # 落库存证
│       │
│       ├── discovery/                    # AI 项目发现模块 (增量建模引擎)
│       │   ├── agent.py                  # 基于 ReAct 和 Tools 的主探测机器人
│       │   ├── prompts.py                # 增量及全量扫描两套规则引导字典
│       │   ├── tools.py                  # 封装基于底层 shell/git/文件读取的方法
│       │   └── merger.py                 # 针对差分结果进行数据层融合归集的大方法
│       │
│       ├── policy/                       # 安全网关系统
│       │   ├── permission.py
│       │   ├── safety.py
│       │   ├── execution_matrix.py
│       │   └── redaction.py
│       │
│       └── executor/                     
│           └── http_executor.py          # 完全隔绝且拥有超细粒度记录的 httpx 客户端
│
├── frontend/                             # ===== Vue 前端 =====
│   ├── package.json                      # 锁定所有组件库的版本
│   ├── vite.config.ts                    # 启动项、Proxy 到 :8000
│   └── src/
│       ├── main.ts                       
│       ├── App.vue                       # Layout: 项目侧栏 + 主对聊流 + UI展示挂载区 + 审计Drawer
│       ├── router/index.ts               
│       ├── stores/                       # Project / Session / UIBlock / Audit 状态树
│       ├── views/                        # ChatPage / ProjectModelPage / Capability / Audit 等主视图
│       ├── composables/                  
│       │   ├── useEventStream.ts         # SSE 推流解析转换层
│       │   └── useBlockRenderer.ts       # 负责将 Json 配置挂载解析到组件实例上
│       └── components/                   
│           └── ui-blocks/                # 与 schema `ui_blocks.py` 严格对应绘制规范组件群块
│
├── workspace/                            # ===== 唯一读写运行区 =====
│   ├── .gitkeep                          
│   # 忽略追踪: lui.db, checkpoints.db, logs/, 等运行时文件
│
├── sample-projects/                      # 模拟及对照用样例包 (需准备Git初始环境)
└── README.md
```

---

## 五、 给 AI 助手的执行指令 (请原样提供给执行器)

> 你是一个高级开发 Agent。当前我们要基于以上设计搭建 `Talk-to-Interface` 工程。
> 你的工作必须**完全遵循**以下执行阶段，上一个阶段没有跑通前，**绝对不允许**去开启新目录。
> 任何向 `workspace/` 以外的地方发起的写操作都会被视作失败。
> 遇到不确定的包，主动写入 `requirements.txt` / `package.json` 并发起包管理安装，不需要等待人类。

### Phase 1: 基础设施及 Pydantic Schema 锁定 (引入 OTel 遥测)
1. 拉起基础环境与目录结构。通过集成 `opentelemetry-sdk` 等标准件全面接入 OpenTelemetry 收集端，保证随后的 API、LangGraph Node、HTTP Executions 都带入统一全局的 `Trace ID` 以避免流程黑盒化。
2. 搭建后端的 `schemas`：实现其中所有的基础协议规范并附带详尽的类型描述（包括统一使用 A2UI / AG-UI 事件字典设计 Capability、UIBlock 白名单数据结构）。
3. 搭建后端的 `models`：创建完全隔离的 SQLite 表结构模型与执行库 `app/db.py`（推荐利用 `SQLModel` 统一 Pydantic 与 SQLAlchemy 定义，为后期平滑扩展至 PostgreSQL 等预留低成本空间）。跑完初始脚本并在 `workspace/` 中顺畅建立 `lui.db`。

### Phase 2: “长了眼睛”的项目能力发现组件 (OpenAPI 摄取驱动)
1. 编写基于标准库（如 `openapi-core`）的 `OpenAPIIngestor` 提取器，放置于 `discovery/scanners` 下，实现对目标工程 `openapi.json` 秒级的实体属性提取抽象；
2. 为交叉印证编写轻量化的简单前端 `axios/fetch` 正则文本过滤扫描器，对 API 打上“是否被项目 UI 真实使用”标签；以此构建安全文件系统沙箱探索区。
3. 撰写 AI 归类与整理意图提示词任务点，让 Agent 根据解析后的裸路由数据补充生成完整的 `CapabilityGraph` 属性（基于 domain, metrics, ui 规划补齐）。写一个个独立单元测试，用你顺手造的小破 FastAPI Demo (自带 swagger 的工程放入 `sample-projects`) 喂给它跑通结果。

### Phase 3: LangGraph 状态机长流程
1. 设计 LangGraph 的强类型传递状态池 `state.py`。
2. 配置好 `sqlite-saver` 的 Checkpoint 拦截网。
3. 实现从 `parse_intent` 处理用户输入到最后 `emit_blocks` 数据拼装组建下发的流水线节点代码骨架。
4. 提供外置的 `HTTPExecutor`。

### Phase 4: Vue 动态组件流水线适配
1. 配置好响应式的前端 `EventSource` 请求挂载器，采用 AG-UI 标准同步承接后端 SSE 流转中吐出的进度和事件打点。
2. 完全基于 A2UI 规范数据字段要求，安全按白名单一比一渲染出对应的 UI Blocks 组件映射。坚决禁止 Vue 层跳出协议或自作主张的越权解读机制，彻底将大模型返回锁定于渲染预设，复杂的图表映射利用 `ECharts` 数据透传解决。

### Phase 5: 审计与人工屏障 (Human-in-the-Loop)
1. 完善安全分级逻辑（`policy/execution_matrix.py`）。
2. 当拦截被判定需要执行 `soft_write` 操作，LangGraph 进入 `interrupt`。前端拦截指令，唤出 `ConfirmPanel`，并允许向 `api/approvals/{id}` 抛出通过信号。Graph 恢复向下流动完成核心闭环落地。
