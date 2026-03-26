"""
发现管线兼容层
逐步替代旧 discovery service 命名
"""

from app.discovery.service import DiscoveryService, run_discovery

__all__ = ["DiscoveryService", "run_discovery"]
