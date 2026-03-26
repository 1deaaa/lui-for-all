"""
LLM 结构化输出 Schema 兼容层
"""

from app.llm.schemas.capability_analysis import BatchRouteAnalysisResult, RouteAnalysis

# 兼容旧引用
EnhancedRouteAnalysis = RouteAnalysis

__all__ = ["RouteAnalysis", "EnhancedRouteAnalysis", "BatchRouteAnalysisResult"]
