import json
import httpx
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, './backend')
from app.discovery.route_extractor import RouteExtractor

async def test_batch_extraction():
    source_path = "proj_for_test"
    
    print("正在拉取 OpenAPI 文档...")
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://localhost:6687/openapi.json")
        openapi_data = resp.json()
        
    routes_data = []
    # 提取所有路由
    for path, methods in openapi_data.get("paths", {}).items():
        for method, info in methods.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch", "options"]:
                continue
            routes_data.append({
                "method": method.upper(),
                "path": path,
                "operation_id": info.get("operationId", ""),
                "summary": info.get("summary", "")
            })
            
    print(f"从 OpenAPI 读取到 {len(routes_data)} 条路由")
    
    # 精准提取代码
    extractor = RouteExtractor(source_path)
    route_pairs = [(r['method'], r['path']) for r in routes_data]
    
    print("\n开始精准提取函数体...")
    snippets = extractor.extract_batch(route_pairs)
    
    found_count = sum(1 for s in snippets.values() if s is not None)
    print(f"成果: 成功提取 {found_count} / {len(routes_data)} 条路由")
    
    # 按 32K 字符进行分块
    chunks = []
    current_chunk_code = []
    current_chunk_routes = []
    current_length = 0
    MAX_LENGTH = 32000
    
    for route in routes_data:
        route_id = f"{route['method'].upper()}:{route['path']}"
        snippet = snippets.get(route_id)
        
        if not snippet:
            continue
            
        code_block = snippet.to_context_block()
        block_length = len(code_block)
        
        route_meta = {
            "route_id": route_id,
            "path": route['path'],
            "method": route['method'],
            "summary": route.get('summary', '') or route.get('operation_id', '')
        }
        
        if current_length + block_length > MAX_LENGTH and current_length > 0:
            chunks.append({
                "code": "\n\n".join(current_chunk_code),
                "routes_json": current_chunk_routes
            })
            current_chunk_code = []
            current_chunk_routes = []
            current_length = 0
            
        current_chunk_code.append(code_block)
        current_chunk_routes.append(route_meta)
        current_length += block_length

    if current_chunk_code:
        chunks.append({
            "code": "\n\n".join(current_chunk_code),
            "routes_json": current_chunk_routes
        })

    print(f"\n按限制 32K 字符分块，总共生成了 {len(chunks)} 个块。")
    
    if chunks:
        chunk_0 = chunks[0]
        output_file = Path("chunk_0_test.txt")
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("========== ROUTES JSON ==========\n")
            json.dump(chunk_0["routes_json"], f, ensure_ascii=False, indent=2)
            f.write("\n\n========== CODE CHUNK ==========\n")
            f.write(chunk_0["code"])
            
        print(f"\n已将第一个代码块保存至 {output_file.absolute()}")
        print(f"第一个块包含 {len(chunk_0['routes_json'])} 条路由分析任务，包含字符数: {len(chunk_0['code'])}")

if __name__ == "__main__":
    asyncio.run(test_batch_extraction())
