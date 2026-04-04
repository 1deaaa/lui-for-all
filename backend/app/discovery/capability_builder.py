"""
能力图谱生成器
重构版：使用路由函数精准提取器替代全量源码扫描
- 有 source_path：按路由 ID 精准提取函数体，并行注入 LLM
- 无 source_path：仅依赖 OpenAPI 元数据 + Method 规则推断
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, List

from app.discovery.route_extractor import RouteExtractor, RouteSnippet
from app.graph.llm_client import llm_client
from app.llm.prompts import CAPABILITY_INFER_PROMPT
from app.llm.schemas import BatchRouteAnalysisResult, RouteAnalysis
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


ProgressCallback = Callable[[int, str], Awaitable[None]]


# ==================== 安全等级推断规则 ====================

_SAFETY_MAP = {
    "readonly_safe": SafetyLevel.READONLY_SAFE,
    "readonly_sensitive": SafetyLevel.READONLY_SENSITIVE,
    "soft_write": SafetyLevel.SOFT_WRITE,
    "hard_write": SafetyLevel.HARD_WRITE,
    "critical": SafetyLevel.CRITICAL,
}

_DOMAIN_MAP = {
    "auth": Domain.AUTH,
    "customer": Domain.CUSTOMER,
    "finance": Domain.FINANCE,
    "inventory": Domain.INVENTORY,
    "content": Domain.CONTENT,
    "analytics": Domain.ANALYTICS,
    "operations": Domain.OPERATIONS,
    "system": Domain.SYSTEM,
}

_METHOD_DEFAULT_SAFETY = {
    "GET": SafetyLevel.READONLY_SAFE,
    "HEAD": SafetyLevel.READONLY_SAFE,
    "OPTIONS": SafetyLevel.READONLY_SAFE,
    "POST": SafetyLevel.SOFT_WRITE,
    "PUT": SafetyLevel.SOFT_WRITE,
    "PATCH": SafetyLevel.SOFT_WRITE,
    "DELETE": SafetyLevel.HARD_WRITE,
}

_MODALITY_BY_SAFETY = {
    SafetyLevel.READONLY_SAFE: [ModalityType.DATA_TABLE, ModalityType.TEXT_BLOCK],
    SafetyLevel.READONLY_SENSITIVE: [ModalityType.TEXT_BLOCK],
    SafetyLevel.SOFT_WRITE: [ModalityType.CONFIRM_PANEL, ModalityType.TEXT_BLOCK],
    SafetyLevel.HARD_WRITE: [ModalityType.CONFIRM_PANEL],
    SafetyLevel.CRITICAL: [ModalityType.TEXT_BLOCK],
}


def _infer_safety_from_method(method: str) -> SafetyLevel:
    return _METHOD_DEFAULT_SAFETY.get(method.upper(), SafetyLevel.SOFT_WRITE)


def _parse_safety(raw: str | None, method: str) -> SafetyLevel:
    if raw and raw in _SAFETY_MAP:
        return _SAFETY_MAP[raw]
    return _infer_safety_from_method(method)


def _parse_domain(raw: str | None) -> Domain:
    if raw and raw in _DOMAIN_MAP:
        return _DOMAIN_MAP[raw]
    return Domain.UNKNOWN


# ==================== 图谱构建器 ====================

class CapabilityGraphBuilder:
    """能力图谱构建器 (AI 驱动，并行版)"""

    def __init__(
        self,
        route_map: RouteMap,
        progress_callback: ProgressCallback | None = None,
        source_path: str | None = None,
        global_context: str | None = None,
    ):
        self.route_map = route_map
        self.routes = route_map.routes
        self.progress_callback = progress_callback
        self.source_path = source_path  # 目标项目本地源码路径
        self.global_context = global_context

    async def _report_progress(self, percent: int, message: str):
        if self.progress_callback:
            await self.progress_callback(percent, message)

    def _generate_fallback_summary(self, route: RouteInfo) -> str:
        """生成最基础的功能摘要"""
        method = route.method.value
        label = route.summary or route.operation_id or route.path.split("/")[-1]
        action_map = {"GET": "查询", "POST": "创建", "PUT": "更新", "PATCH": "修改", "DELETE": "删除"}
        return f"{action_map.get(method, '操作')}{label}"

    def _extract_parameter_hints(self, route: RouteInfo) -> dict[str, Any]:
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

    async def _analyze_route_chunk(
        self,
        chunk_idx: int,
        total_chunks: int,
        code_chunk: str,
        routes_json: str,
        total_routes_in_chunk: int,
    ) -> dict[str, RouteAnalysis]:
        """按块批量分析路由"""
        from app.config import WORKSPACE_DIR
        
        try:
            prompt = CAPABILITY_INFER_PROMPT.format(
                total=total_routes_in_chunk,
                code_chunk=code_chunk,
                routes_json=routes_json,
                global_context=self.global_context or "未知",
            )
            
            # 手动组装 LLM 请求，以便无论解析成功与否都能拦截到原始输出
            system_prompt = (
                "你是一个结构化数据提取助手。\n"
                "请严格按照指定的 JSON Schema 格式输出，不要添加任何额外的文本或解释。\n"
                "输出必须是有效的 JSON 格式，不要包含 markdown 代码块标记。"
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            content, _, _ = await llm_client.chat_completion(
                messages,
                response_format={"type": "json_object"},
            )
            
            # --- 核心测试逻辑：无条件保存原始返回到 workspace 目录（截断也会写入）---
            try:
                WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
                dump_path = WORKSPACE_DIR / f"chunk_{chunk_idx}_raw_result.json"
                with open(dump_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"[CapabilityBuilder] 📝 Chunk [{chunk_idx+1}] 原始输出已落盘: {dump_path} ({len(content)} 字符) | 预期输出：{total_routes_in_chunk} 条")
            except Exception as e_save:
                print(f"[CapabilityBuilder] ⚠️ 保存 Chunk [{chunk_idx+1}] 结果至文件时失败: {e_save}")
            # -----------------------------------------------------------------------

            # 尝试修复和解析
            repaired = llm_client._try_repair_json(content)
            if repaired is None:
                print(f"[CapabilityBuilder] ❌ Chunk [{chunk_idx+1}/{total_chunks}] 无法修复为有效 JSON，原始输出前 200 字: {content[:200]}")
                return {}
             
            result = BatchRouteAnalysisResult.model_validate(repaired)
            
            print(f"[CapabilityBuilder] ✅ Chunk [{chunk_idx+1}/{total_chunks}] 分析成功: 解析出 {len(result.analyses)} / {total_routes_in_chunk} 条路由")
            
            # 建立映射
            res_map = {}
            for ai_route in result.analyses:
                res_map[ai_route.route_id] = ai_route
            return res_map
        except Exception as e:
            import traceback
            print(f"[CapabilityBuilder] ❌ Chunk [{chunk_idx+1}/{total_chunks}] 分析失败: {type(e).__name__}: {e}")
            print(f"[CapabilityBuilder] 详细堆栈:\n{traceback.format_exc()}")
            return {}

    async def _analyze_routes_with_ai(
        self, source_path: str | None = None
    ) -> dict[str, RouteAnalysis]:
        """
        按路由精准提取函数体，拼接为 32K 块并行批量分析。
        - source_path 可用：提取精准函数体 → 分块 → 高质量批量分析
        - source_path 不可用：跳过 LLM，全量走规则兜底
        """
        if not source_path:
            await self._report_progress(45, "未提供源码路径，跳过 AI 分析，将使用规则推断")
            print("[CapabilityBuilder] source_path 未设置，跳过源码分析")
            return {}

        await self._report_progress(30, f"正在从 {source_path} 提取路由函数体...")
        print(f"\n[CapabilityBuilder] 🔧 开始精准提取 {len(self.routes)} 条路由的函数源码...")

        # 1. 提取源码
        try:
            extractor = RouteExtractor(source_path)
        except ValueError as e:
            print(f"[CapabilityBuilder] 源码路径无效: {e}，降级为规则推断")
            return {}

        route_pairs = [(r.method.value, r.path) for r in self.routes]
        snippets = extractor.extract_batch(route_pairs)

        found = sum(1 for s in snippets.values() if s is not None)
        print(f"[CapabilityBuilder] ✅ 函数源码提取完成：{found}/{len(self.routes)} 条路由找到具体实现代码")

        # 2. 按 32K 并入独立块
        MAX_LENGTH = 32000
        raw_chunks = []
        current_chunk_items = []
        current_length = 0

        for r in self.routes:
            route_id = r.route_id
            snippet = snippets.get(route_id)
            if not snippet:
                continue

            # 预估长度，稍微大一点留给编号字数
            block_length = len(snippet.code) + 200

            if current_length + block_length > MAX_LENGTH and current_length > 0:
                raw_chunks.append(current_chunk_items)
                current_chunk_items = []
                current_length = 0

            current_chunk_items.append((r, snippet))
            current_length += block_length

        if current_chunk_items:
            raw_chunks.append(current_chunk_items)

        # 转换为带严格编号的文本列表
        chunks = []
        for raw_items in raw_chunks:
            chunk_code = []
            chunk_routes = []
            total_in_chunk = len(raw_items)
            
            for idx, (route_info, snip) in enumerate(raw_items, start=1):
                chunk_code.append(snip.to_context_block(seq_idx=idx, total=total_in_chunk))
                chunk_routes.append({
                    "seq_idx": f"[{idx}/{total_in_chunk}]",
                    "route_id": route_info.route_id,
                    "path": route_info.path,
                    "method": route_info.method.value,
                    "summary": route_info.summary or route_info.operation_id or "",
                })
                
            chunks.append({
                "code": "\n\n".join(chunk_code),
                "routes_json": json.dumps(chunk_routes, ensure_ascii=False),
                "total_routes_in_chunk": total_in_chunk
            })

        total_chunks = len(chunks)
        await self._report_progress(50, f"源码提取完成，已打包为 {total_chunks} 个推理任务块，开始并行 AI 分析")
        print(f"[CapabilityBuilder] 已打包为 {total_chunks} 个块，即将开始请求大模型")

        if total_chunks == 0:
            return {}

        # 3. 并行发 LLM 请求（以块为单位）
        CONCURRENCY = 8
        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def analyze_with_sem(idx: int, chunk: dict):
            async with semaphore:
                return await self._analyze_route_chunk(
                    idx, 
                    total_chunks, 
                    chunk["code"], 
                    chunk["routes_json"],
                    chunk["total_routes_in_chunk"]
                )

        tasks = [analyze_with_sem(i, chunk) for i, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 4. 汇总
        analysis_map: dict[str, RouteAnalysis] = {}
        for res in results:
            if isinstance(res, dict):
                analysis_map.update(res)

        success_count = len(analysis_map)
        await self._report_progress(82, f"AI 分析完成：成功识别并分析出 {success_count} 条有效路由能力")
        print(f"[CapabilityBuilder] 🤖 AI 建模分析完成：成功识别并分析出 {success_count} 条有效路由能力 (剩余 {len(self.routes) - success_count} 条由规则降级处理)")
        return analysis_map

    async def build(self) -> CapabilityGraph:
        """构建完整的能力图谱"""
        capabilities: list[Capability] = []
        domain_summary: dict[str, int] = {}

        await self._report_progress(25, "已完成 OpenAPI 解析，准备进行并行 AI 能力建模")

        ai_analyses = await self._analyze_routes_with_ai(self.source_path)

        await self._report_progress(82, "AI 分析完成，正在组装能力图谱")

        for route in self.routes:
            capability_id = route.operation_id or route.route_id.replace(":", "_").replace("/", "_")
            analysis: RouteAnalysis | None = ai_analyses.get(route.route_id)

            if analysis:
                # 使用 AI 分析结果
                domain = _parse_domain(analysis.domain)
                safety_level = _parse_safety(analysis.safety_level, route.method.value)
                requires_confirmation = analysis.requires_confirmation
                summary = analysis.summary or self._generate_fallback_summary(route)
                ai_usage_guidelines = analysis.usage_note
                source_code_analysis = f"AI 分析摘要: {analysis.summary}"
                confidence = 0.85
            else:
                # 规则兜底：不再用 LLM "猜"，由 HTTP Method 决定默认值
                domain = Domain.UNKNOWN
                safety_level = _infer_safety_from_method(route.method.value)
                requires_confirmation = route.method.value in ("DELETE", "PUT", "PATCH")
                summary = self._generate_fallback_summary(route)
                ai_usage_guidelines = None
                source_code_analysis = None
                confidence = 0.3

            # 根据安全等级推断最佳 UI 组件（而非要求 AI 逐一指定）
            best_modalities = _MODALITY_BY_SAFETY.get(safety_level, [ModalityType.TEXT_BLOCK])

            # 权限等级：写操作默认要求 operator，只读默认 authenticated
            if safety_level in (SafetyLevel.HARD_WRITE, SafetyLevel.CRITICAL):
                permission_level = PermissionLevel.ADMIN
            elif safety_level == SafetyLevel.SOFT_WRITE:
                permission_level = PermissionLevel.OPERATOR
            else:
                permission_level = PermissionLevel.AUTHENTICATED

            capability = Capability(
                capability_id=capability_id,
                name=route.summary or route.operation_id or route.path,
                description=route.description or f"执行 {route.method.value} {route.path} 操作",
                summary=summary,
                domain=domain,
                backed_by_routes=[RouteRef(route_id=route.route_id, role="primary")],
                user_intent_examples=[summary],
                required_permission_level=permission_level,
                safety_level=safety_level,
                data_sensitivity="low" if safety_level == SafetyLevel.READONLY_SAFE else "medium",
                best_modalities=best_modalities,
                requires_confirmation=requires_confirmation,
                ai_usage_guidelines=ai_usage_guidelines,
                source_code_analysis=source_code_analysis,
                evidence_refs=[
                    EvidenceRef(
                        type="code_scan",
                        source=self.route_map.source,
                        confidence=confidence,
                    )
                ],
                parameter_hints=self._extract_parameter_hints(route),
            )
            capabilities.append(capability)

            domain_key = capability.domain.value
            domain_summary[domain_key] = domain_summary.get(domain_key, 0) + 1

        return CapabilityGraph(
            project_id=self.route_map.project_id,
            version=f"v{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            capabilities=capabilities,
            domain_summary=domain_summary,
            generated_at=datetime.utcnow().isoformat(),
        )


async def build_capability_graph(
    route_map: RouteMap,
    progress_callback: ProgressCallback | None = None,
    source_path: str | None = None,
    global_context: str | None = None,
) -> CapabilityGraph:
    """便捷函数：从路由地图异步构建能力图谱"""
    builder = CapabilityGraphBuilder(
        route_map,
        progress_callback=progress_callback,
        source_path=source_path,
        global_context=global_context,
    )
    return await builder.build()
