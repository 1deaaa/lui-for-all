"""
代码全量切块工具
用于深度扫描指定后端的源码目录，将文件拼装成不超过配置字符上限的代码块 (Chunk)。
为 LLM 的全量代码注入提供安全切分。
"""

import os
from pathlib import Path
from typing import List


class CodeChunker:
    """全自动扫描后端代码并按上限切分成大块"""

    def __init__(self, base_dir: str, max_chunk_chars: int = 32_000):
        # 将传入目录解析为确切的 backend/app 目录
        self.base_dir = Path(base_dir)
        # 上限预留 10% 作为安全余量，确保不因边界溢出导致 LLM 输出被截断
        self.max_chunk_chars = int(max_chunk_chars * 0.90)
        # 有效扫描的后缀
        self.valid_extensions = {".py"}
        # 需要排除的目录（新增 test、migrations 等噪音目录）
        self.exclude_dirs = {"__pycache__", "venv", ".venv", ".git", "test", "tests", "migrations", "alembic"}
        # 需要排除的文件
        self.exclude_files = {"__init__.py"}

    def _is_valid_file(self, file_path: Path) -> bool:
        """判断文件是否应该被读入（通常只获取我们关心的业务实现和模型定义）"""
        if file_path.suffix not in self.valid_extensions:
            return False
        
        if file_path.name in self.exclude_files:
            return False

        # 检查父目录是否命中排除规则
        for parent in file_path.parents:
            if parent.name in self.exclude_dirs:
                return False
                
        return True

    def scan_files(self) -> List[Path]:
        """扫描该目录下的所有源码文件列表"""
        valid_files = []
        for root, dirs, files in os.walk(self.base_dir):
            root_path = Path(root)
            # 中断对被排除目录的深挖以节省时间
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            
            for file_name in files:
                file_path = root_path / file_name
                if self._is_valid_file(file_path):
                    valid_files.append(file_path)
                    
        return sorted(valid_files)

    def generate_chunks(self, files: List[Path]) -> List[str]:
        """将传入文件合并，按字符数上限切为完整的 Chunk"""
        chunks: List[str] = []
        current_chunk = ""
        current_length = 0

        for file_path in files:
            try:
                # 尽量相对路径以保持给 AI 阅读的清爽
                relative_path = file_path.relative_to(self.base_dir.parent)
                
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                file_header = f"\n\n--- 源码文件: {relative_path} ---\n"
                segment = file_header + content + "\n--- EOF ---\n"
                segment_len = len(segment)

                if current_length + segment_len > self.max_chunk_chars:
                    if not current_chunk:
                        # 单个文件就超过了上限，触发极端降级
                        print(f"[CodeChunker] Warning: File {file_path} too long ({segment_len} chars).")
                        # 将整个巨型文件视为一个 Chunk（或者也可以在文件内部粗暴切分）
                        # 暂时为保持方法定义不断首尾，容忍越界一次，因为通常文件没这么大
                        chunks.append(segment)
                        continue
                    # 将堆积完成的 Chunk 归档
                    chunks.append(current_chunk)
                    # 重置缓冲
                    current_chunk = segment
                    current_length = segment_len
                else:
                    # 并入当前缓冲
                    current_chunk += segment
                    current_length += segment_len
            
            except Exception as e:
                print(f"[CodeChunker] Failed to read {file_path}: {e}")

        # 将最后一块放入结果
        if current_chunk:
            chunks.append(current_chunk)

        print(f"[CodeChunker] 生成了 {len(chunks)} 块代码注入源数据.")
        return chunks

    def process_directory(self) -> List[str]:
        """执行端到端目录切块读取"""
        target_files = self.scan_files()
        return self.generate_chunks(target_files)

