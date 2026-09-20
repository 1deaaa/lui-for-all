"""
总结与 UI 输出节点兼容层。

当前真实实现仍位于 app.graph.nodes（summarize_node/emit_blocks_node），
本模块保留转发导出，供历史导入路径兼容。
"""

from app.graph.nodes import emit_blocks_node, summarize_node

__all__ = ["summarize_node", "emit_blocks_node"]
