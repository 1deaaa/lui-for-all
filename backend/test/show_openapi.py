"""展示 OpenAPI 文件结构"""
import httpx
import json

resp = httpx.get('http://localhost:8010/openapi.json', timeout=10)
data = resp.json()

print('=== OpenAPI 文件结构 ===')
print(f'title: {data.get("info", {}).get("title")}')
print(f'description: {data.get("info", {}).get("description")}')
print(f'paths 数量: {len(data.get("paths", {}))}')
print()

# 展示几个典型路径
paths = list(data.get('paths', {}).items())[:5]
for path, methods in paths:
    print(f'--- {path} ---')
    for method, detail in methods.items():
        print(f'  {method.upper()}:')
        print(f'    summary: {detail.get("summary")}')
        print(f'    operationId: {detail.get("operationId")}')
        print(f'    description: {detail.get("description")}')
    print()

# 展示 schemas
print('=== Components/Schemas (数据模型) ===')
schemas = list(data.get('components', {}).get('schemas', {}).items())[:2]
for name, schema in schemas:
    print(f'{name}: {json.dumps(schema, indent=2, ensure_ascii=False)[:300]}...')
