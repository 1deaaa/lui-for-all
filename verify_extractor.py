"""验证提取质量：打印完整的函数体（不截断）"""
import sys, json, sqlite3
sys.path.insert(0, '.')

exec(open('test_route_extractor.py').read().split("if __name__")[0])  # 只加载类定义

SOURCE_PATH = r"d:\Desktop\talk-to-interface\proj_for_test"
extractor = RouteExtractor(SOURCE_PATH)

# 测试几个有代表性的路由
test_cases = [
    ("POST", "/api/register"),
    ("GET", "/api/system/notice"),
    ("GET", "/api/admin/my-quota-status"),
]

for method, path in test_cases:
    s = extractor.extract_route(method, path)
    if s:
        print(f"\n{'='*60}")
        print(f"✅ {method} {path}")
        print(f"   文件: {s.file_path}  行: {s.start_line}-{s.end_line}  总行数: {s.end_line - s.start_line + 1}")
        print(f"{'─'*60}")
        print(s.code)
    else:
        print(f"\n❌ {method} {path} 未找到")
