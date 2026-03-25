"""
能力图谱生成器
通过全量代码切块注入 LLM，推断 OpenAPI 路由的高级能力属性
"""

import uuid
from datetime import datetime
from typing import Any, List

from pydantic import BaseModel, Field

from app.discovery.code_chunker import CodeChunker
from app.graph.llm_client import llm_client
from app.schemas.capability import (
    Capability,
    CapabilityGraph,
    Domain,
    EvidenceRef,
    ModalityType,
    PermissionLevel,
    RouteRef,
    SafetyLevel,
)
from app.schemas.route_map import RouteInfo, RouteMap
from app.config import settings


# ==================== LLM 结构化输出定义 ====================

class EnhancedRouteAnalysis(BaseModel):
    """单条路由增强分析结果"""
    route_id: str = Field(description="路由唯一标识 (method:path) 必须与输入一致")
    domain: Domain = Field(description="推断的业务领域")
    permission_level: PermissionLevel = Field(description="推断的最低权限等级")
    safety_level: SafetyLevel = Field(description="推断的安全等级")
    data_sensitivity: str = Field(description="数据敏感程度: low, medium, high")
    requires_confirmation: bool = Field(description="调用此接口是否必须让人类二次确认")
    best_modalities: List[ModalityType] = Field(description="推测适合呈现数据的最佳 UI 组件类型")
    ai_usage_guidelines: str = Field(description="根据源码分析出的调用约束、隐含限制和最佳实践说明")
    source_code_analysis: str = Field(description="关于此路由背后源码逻辑的简短分析摘要")


class BatchRouteAnalysisResult(BaseModel):
    """批量分析结果集"""
    analyses: List[EnhancedRouteAnalysis] = Field(description="路由解析结果列表")


# ==================== Prompt 定义 ====================

CAPABILITY_INFER_PROMPT = """
你是一个高级代码分析和架构还原引擎。
你的任务是：阅读提供的后端源码片段，并结合 OpenAPI 中的路由定义，精准推断每个路由的真实业务含义和调用约束。

### 源码切片 (Source Code Chunk) ###
{code_chunk}

### 需要分析的 OpenAPI 路由集合 ###
{routes_json}

请深入阅读源码中关于这些路由函数的实现逻辑、依赖关系及涉及的 Pydantic 模型。
对于每一个路由，如果能在源码切片中找到实现或其线索，请分析并返回其高级属性。如果找不到实质性线索，请结合常识给出最保守、最安全的基线估计。

**要求返回的 JSON 数组结构须符合 BatchRouteAnalysisResult 的要求。**

特别注意：
1. **ai_usage_guidelines**: 至关重要！请指出在调用此接口时，源码中有没有校验逻辑（如不能修改其他人的记录？某些状态下不能删除？时间格式有无特殊要求）。
2. **safety_level**: 对数据库有破坏性或不可逆写操作必须标记为 `hard_write` 或 `critical`。
3. **requires_confirmation**: 如果涉及转账、删除、核心配置更改等危险操作，必须设为 true。
"""


# ==================== 图谱构建器 ====================

class CapabilityGraphBuilder:
    """能力图谱构建器 (AI 驱动)"""

    def __init__(self, route_map: RouteMap):
        self.route_map = route_map
        self.routes = route_map.routes

    def _generate_fallback_user_intent_examples(self, route: RouteInfo) -> list[str]:
        """生成保底的用户意图示例"""
        examples: list[str] = []
        method = route.method.value
        summary = route.summary or route.operation_id or route.path

        if method == "GET":
            examples.append(f"获取{summary}")
        elif method == "POST":
            examples.append(f"创建{summary}")
        elif method in ["PUT", "PATCH"]:
            examples.append(f"更新{summary}")
        elif method == "DELETE":
            examples.append(f"删除{summary}")

        return examples[:3]

    def _extract_parameter_hints(self, route: RouteInfo) -> dict[str, Any]:
        """提取基础参数提示"""
        hints: dict[str, Any] = {}
        for param in route.parameters:
            hints[param.name] = {
                "type": param.type_hint,
                "required": param.required,
                "description": param.description,
                "default": param.default,
                "example": param.example,
            }
        return hints

    async def _analyze_routes_with_ai(self) -> dict[str, EnhancedRouteAnalysis]:
        """使用 LLM 批量分析路由"""
        analysis_map: dict[str, EnhancedRouteAnalysis] = {}
        
        # 1. 切分全量代码获取 Chunks
        backend_dir = r"d:\Desktop\talk-to-interface\backend\app"
        chunker = CodeChunker(base_dir=backend_dir)
        code_chunks = chunker.process_directory()
        
        # 2. 准备基础路由信息集合（缩减体积送给 AI）
        routes_summary = []
        for r in self.routes:
            routes_summary.append({
                "route_id": r.route_id,
                "path": r.path,
                "method": r.method.value,
                "summary": r.summary,
                "description": r.description
            })
            
        import json
        routes_json = json.dumps(routes_summary, ensure_ascii=False)

        # 3. 循环注入 Chunk 进行分析
        # 优化：通常可以将所有未分析好的路由一次性丢给 LLM 读第一个 Chunk
        # 简化起见，我们目前仅把切出的每一块代码依次让大模型看一遍，更新 analysis_map
        for i, chunk in enumerate(code_chunks):
            print(f"[CapabilityBuilder] 正在让 AI 阅读第 {i+1}/{len(code_chunks)} 块代码...")
            try:
                prompt = CAPABILITY_INFER_PROMPT.format(
                    code_chunk=chunk,
                    routes_json=routes_json
                )
                
                # 发起模型调用
                result = await llm_client.parse_json_response(
                    messages=[{"role": "user", "content": prompt}],
                    schema=BatchRouteAnalysisResult,
                    temperature=0.1  # 保持结构化输出稳定
                )
                
                # 合并或覆盖结果
                for analysis in result.analyses:
                    analysis_map[analysis.route_id] = analysis
                    
            except Exception as e:
                print(f"[CapabilityBuilder] Chunk {i+1} 分析失败: {e}")
                
        return analysis_map

    async def build(self) -> CapabilityGraph:
        """构建完整的能力图谱"""
        capabilities: list[Capability] = []
        domain_summary: dict[str, int] = {}

        # 1. 触发 AI 批量分析
        print(f"[CapabilityBuilder] 正在启动全量源码注入分析...")
        ai_analyses = await self._analyze_routes_with_ai()
        print(f"[CapabilityBuilder] AI 成功分析了 {len(ai_analyses)} 个路由")

        # 2. 拼装能力定义
        for route in self.routes:
            capability_id = route.operation_id or route.route_id.replace(":", "_").replace("/", "_")
            
            # 获取 AI 的增强分析，如果没有则给出最保守的默认值
            analysis = ai_analyses.get(route.route_id)
            
            if analysis:
                domain = analysis.domain
                permission_level = analysis.permission_level
                safety_level = analysis.safety_level
                data_sensitivity = analysis.data_sensitivity
                requires_confirmation = analysis.requires_confirmation
                best_modalities = analysis.best_modalities
                ai_usage_guidelines = analysis.ai_usage_guidelines
                source_code_analysis = analysis.source_code_analysis
            else:
                # 极端熔断时的保守兜底
                domain = Domain.UNKNOWN
                permission_level = PermissionLevel.ADMIN
                safety_level = SafetyLevel.CRITICAL if route.method.value in ["DELETE", "POST", "PUT"] else SafetyLevel.READONLY_SENSITIVE
                data_sensitivity = "high"
                requires_confirmation = True
                best_modalities = [ModalityType.TEXT_BLOCK]
                ai_usage_guidelines = "⚠️ AI 分析失败。请极其谨慎地使用此操作。"
                source_code_analysis = "未能通过源码找到此路由的实际逻辑。"

            # 构建能力记录
            capability = Capability(
                capability_id=capability_id,
                name=route.summary or route.operation_id or route.path,
                description=route.description or f"执行 {route.method.value} {route.path} 操作",
                domain=domain,
                backed_by_routes=[RouteRef(route_id=route.route_id, role="primary")],
                user_intent_examples=self._generate_fallback_user_intent_examples(route),
                required_permission_level=permission_level,
                safety_level=safety_level,
                data_sensitivity=data_sensitivity,
                best_modalities=best_modalities,
                requires_confirmation=requires_confirmation,
                ai_usage_guidelines=ai_usage_guidelines,
                source_code_analysis=source_code_analysis,
                evidence_refs=[
                    EvidenceRef(
                        type="code_scan",
                        source=self.route_map.source,
                        confidence=0.85 if analysis else 0.1,
                    )
                ],
                parameter_hints=self._extract_parameter_hints(route),
            )
            capabilities.append(capability)

            # 统计领域分布
            domain_key = capability.domain.value
            domain_summary[domain_key] = domain_summary.get(domain_key, 0) + 1

        return CapabilityGraph(
            project_id=self.route_map.project_id,
            version=f"v{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            capabilities=capabilities,
            domain_summary=domain_summary,
            generated_at=datetime.utcnow().isoformat(),
        )


async def build_capability_graph(route_map: RouteMap) -> CapabilityGraph:
    """便捷函数：从路由地图异步构建能力图谱"""
    builder = CapabilityGraphBuilder(route_map)
    return await builder.build()
