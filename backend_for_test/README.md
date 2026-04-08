# backend_for_test

这里放置用于路由发现与路由函数提取测试的示例后端。

## 代表性样例矩阵

| 代表样例 | 路由风格派系 | 已实测覆盖（当前适配器） | 理论可迁移（需新增适配器） |
|---|---|---|---|
| fastapi_sample | Python 装饰器路由（`@router.get` / `@app.post`） | FastAPI、Flask、Sanic、Starlette、Litestar、Falcon、aiohttp、Tornado、Bottle、Quart | Ruby Sinatra/Grape、PHP Slim（同类“方法 + 路径 + 处理器”模式） |
| node_sample | Node 路由调用链（`app.get()` / `router.post()`） | Express、Fastify、Koa Router、Hono、Elysia、Restify、hapi | PHP Laravel/Lumen/Slim、Ruby Hanami（同类调用式路由 DSL） |
| django_sample | URLConf 集中声明（`path/re_path/include`） | Django、Django REST Framework | Ruby on Rails (`routes.rb`)、PHP Laravel (`routes/web.php`) |
| springboot_sample | 控制器注解路由（类前缀 + 方法注解） | Java Spring Boot、Spring MVC | C# ASP.NET Core Attribute Controller、PHP Symfony Attribute Route |
| aspnetcore_sample | Minimal API 映射（`MapGet/MapPost/MapMethods`） | ASP.NET Core Minimal API | Java Javalin/Spark、Go net/http + mux（同类“代码注册路由”） |
| go_gin_sample | 分组链式注册（`Group + METHOD(path, handler)`） | Gin、Echo、Fiber、Chi | Rust Actix/Axum、PHP Slim（分组 + 方法调用） |
| node_native_sample | 无框架手写路由表（method/path 到 handler 映射） | Node.js built-in http | Python wsgiref/werkzeug 手写路由、Ruby Rack、PHP Swoole 原生分发 |

补充说明：

- 上表“已实测覆盖”对应当前仓库适配器 + 代表样例测试。
- 上表“理论可迁移”表示语法结构高度相似，原则上可提取，但需要新增或扩展对应适配器后再算正式支持。

## 覆盖目标

- 请求方法：GET POST PUT PATCH DELETE HEAD OPTIONS
- 两级提取：
	- 一级：AST 提取路由节点（extract_all_routes）
	- 二级：按 method/path 提取路由函数实现（extract_batch）

## 使用范围说明

- 本目录样例用于后端提取测试，不要求构建运行。
- 除 fastapi_sample 与 node_sample 外，其余样例不接入 docker-compose 与前端导入预置。

## 现有可运行示例（用于导入预置）

### FastAPI 示例

- Base URL: http://localhost:8010
- OpenAPI URL: http://localhost:8010/openapi.json
- 登录接口 route_id: POST:/api/auth/login
- 用户名字段: username
- 密码字段: password
- 登录测试账号: 111
- 登录测试密码: 111111

### Node 示例

- Base URL: http://localhost:8020
- OpenAPI URL: http://localhost:8020/openapi.json
- 登录接口 route_id: POST:/api/auth/login
- 用户名字段: username
- 密码字段: password
- 登录测试账号: 111
- 登录测试密码: 111111
