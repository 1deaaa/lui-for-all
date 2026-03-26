"""
调试脚本：打印 CodeChunker 实际扫描的文件列表和第一个 chunk 的内容
"""
import sys
sys.path.insert(0, 'backend')

from pathlib import Path
from app.discovery.code_chunker import CodeChunker

# 模拟 capability_builder.py 里的逻辑
backend_dir = Path('backend/app/discovery/capability_builder.py').resolve().parents[1]
print(f"[DEBUG] 扫描目录: {backend_dir}")
print()

chunker = CodeChunker(base_dir=str(backend_dir))
files = chunker.scan_files()
print(f"[DEBUG] 共扫描到 {len(files)} 个文件:")
for f in files:
    print(f"  - {f.relative_to(backend_dir)}")

print()
chunks = chunker.generate_chunks(files)
print(f"\n[DEBUG] 生成 {len(chunks)} 个 chunk")
print(f"[DEBUG] Chunk 1 前 500 字符:\n{'='*50}")
print(chunks[0][:500] if chunks else "(空)")
print('='*50)
