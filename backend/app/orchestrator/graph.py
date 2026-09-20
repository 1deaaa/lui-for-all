"""
编排图兼容层（过渡层）。

当前运行时的主图位于 app.graph.graph（Agentic Loop 四节点：
agent_entry → agentic_loop → summarize → emit_blocks），
本模块仅转发该实现。新功能不得向本兼容层添加业务逻辑。
"""

from app.graph.graph import create_talk_to_interface_graph, graph_app

__all__ = ["create_talk_to_interface_graph", "graph_app"]
