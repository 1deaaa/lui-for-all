# LUI-for-All 贡献指南

欢迎来到 LUI-for-All。

如果你愿意让更多系统可以被自然语言可靠地操作，这个项目非常需要你的贡献。我们会尽量把规则讲清楚，让你可以快速开始并且少踩坑。

## 先看重点

当前最优先的工作是：扩展更多后端框架适配器。

原因很简单：发现链路已经稳定在 OpenAPI + AST 双轨上，新增适配器会直接扩大可接入系统范围，收益最大。

## 已适配与待适配

说明：
- 已适配：仓库内已有稳定适配器，且有代表样例参与回归测试。
- 待适配：暂未有稳定适配器或仅部分语法覆盖。

### 已适配（欢迎继续增强精度）

| 语言 | 已适配框架/风格 |
|---|---|
| Python | FastAPI, Flask, Sanic, Starlette, Litestar, aiohttp, Bottle, Quart, Django URLConf |
| Node.js / TypeScript | NestJS, Express, Fastify, Koa Router, Hono, Elysia, Restify, Node native imperative dispatch |
| Java | Spring Boot, Spring MVC |
| C# / .NET | ASP.NET Core Attribute Controller, Minimal API |
| Go | Gin, Echo, Fiber, Chi（含基础 net/http 模式） |

### 待适配（优先级高）

| 语言 | 待适配方向 |
|---|---|
| Ruby | Rails routes.rb, Sinatra |
| PHP | Laravel routes/web.php & routes/api.php, Slim |
| Java | Quarkus, Micronaut（JAX-RS/注解变体） |
| .NET | MVC 约定式路由的更完整覆盖 |
| Go | 更复杂 net/http + mux 组合路由 |
| Node.js | hapi 等未覆盖 DSL 变体 |

## 除了框架适配，还很值得贡献的点

1. AST 提取准确率
- 减少误提取和漏提取，尤其是跨文件、嵌套路由、前缀拼接场景。

2. 提取性能
- 优化大仓库扫描性能、缓存命中率、并发策略，减少重复扫描。

3. OpenAPI 与 AST 对齐
- 处理参数风格差异、prefix 合并、模糊匹配边界，提升 route_id 命中率。

4. 示例项目质量
- 完善 backend_for_test 下样例，让路由函数有真实行为，便于回归和演示。

5. 测试体系
- 扩展代表样例测试、回归测试、失败场景测试，保证新增适配器可持续维护。

6. 文档与国际化
- 同步维护中英日文档，减少口径漂移。

7. 可观测性与安全
- 提升发现链路日志可读性、异常诊断信息、审计与安全策略说明。

## 适配器贡献最短路径

1. 在 backend/app/discovery/adapters 下新增适配器文件。
2. 继承 FrameAdapter 并至少实现：
- can_handle(source_path)
- get_tree_sitter_query()
- _extract_routes_from_tree(...)
3. 在 backend/app/discovery/adapters/__init__.py 的 _REGISTRY 注册。
4. 在 backend_for_test 增加或更新代表样例。
5. 运行回归测试并确保通过。

## 建议的本地验证命令

在 backend 目录执行：

```bash
C:/APP/conda/envs/llm/python.exe -m pytest test/test_route_extractor_representative_samples.py test/test_adapter_registry_metadata.py -q
```

如果你改了发现链路缓存相关逻辑，也建议加跑：

```bash
C:/APP/conda/envs/llm/python.exe -m pytest test/test_semantic_ingestor_cache_reuse.py -q
```

## CI 自动测试

仓库配置了 CI 工作流，会在以下时机自动运行：

- **触发条件**：向 `main` / `master` 发起 PR 或直接 push 时自动触发。
- **后端测试**：Python 3.11 + pytest，运行 `backend/test/` 下全部测试。
- **前端检查**：Node 20 + pnpm，执行 lint 和 build。

PR 页面会显示 CI 状态（✅ 通过 / ❌ 失败）。**维护者会优先审核 CI 通过的 PR**；CI 未通过时建议先修复再请求审核。

## PR 友好清单

提交前建议自查：

- 变更目标清晰，避免一次 PR 混入无关改动。
- 新增/修改适配器时，同步补充样例或测试。
- 文档与代码口径一致，尤其是"已适配"和"理论可迁移"要分开写。
- 不引入与任务无关的大范围重排。
- CI 全部通过后再请求审核。

## 历史路径说明

旧路径 backend/app/discovery/adapters/CONTRIBUTING.md 仍保留为兼容入口；
根目录 CONTRIBUTING.md 是当前推荐维护的主文档。

感谢你的投入，欢迎随时提 PR。
