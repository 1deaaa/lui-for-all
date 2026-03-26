"""
编排图兼容层
当前复用既有实现，后续逐步迁移内部细节
"""

from app.graph.graph import create_talk_to_interface_graph, graph_app

__all__ = ["create_talk_to_interface_graph", "graph_app"]
