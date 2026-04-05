# FastAPI 标准测试项目

这是用于 LUI-for-All 的 FastAPI 示例后端，目标是覆盖常见后端请求类型与操作，方便做能力发现和自动化回归测试。

## 运行

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8010
```

## OpenAPI

- 文档页: `http://localhost:8010/docs`
- OpenAPI: `http://localhost:8010/openapi.json`

## 覆盖范围

- 请求方法: `GET` `POST` `PUT` `PATCH` `DELETE` `HEAD` `OPTIONS`
- 参数类型: Path / Query / Header / Cookie / JSON Body / Form / Multipart
- 返回类型: JSON / CSV 文件下载 / SSE 流式事件
- 业务操作: 登录鉴权、用户 CRUD、批量更新、嵌套资源、任务状态、幂等支付、Webhook
