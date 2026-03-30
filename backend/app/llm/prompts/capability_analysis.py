"""
建图阶段 Prompt 资源
重构版：减少 AI 心智负担，提高 JSON 输出稳定性
"""

CAPABILITY_INFER_PROMPT = """
你是一个高度精准的后端代码分析专家。
我为你提供了一个由 {total} 条路由（Route）组成的严格候选清单，并且为你传入了这 {total} 条路由分别对应的准确源代码实现片段。

### 【整个项目的全局业务上下文背景】 ###
{global_context}
(请结合该全局系统设定，来理解以下局部代码的作用)

### 候选路由列表（共 {total} 条） ###
这里是需要分析的路由基本信息。每条都标有对应的 `seq_idx`（在本批次中的序号）和 `route_id`。
{routes_json}

### 对应的源码片段 ###
每个源码块开头都有显著的边界标记，例如 `####### [idx/total] route_id ##############`。
{code_chunk}

### 【极端严格的输出指令】 ###
1. **必须 1:1 精确输出**：我传入了 {total} 条路由，你**必须**在 JSON 的 `analyses` 数组中返回 **刚好 {total}** 条路由结果！
2. **绝对不允许任何省略**：所有的源码提取匹配都已经由前置引擎完成！严禁丢弃任何路由，也不允许因为任何理由跳过！
3. **按顺序处理**：请务必从第 1 条到第 {total} 条逐个对照代码块处理，不可漏掉中间项。
4. route_id 必须与候选列表中的原始 route_id 一字不差地完全一致。

### 输出 JSON 格式要求 ###
输出一个必须包含 {total} 个对象的 JSON ，严格结构如下：
{{
  "analyses": [
    {{
      "route_id": "POST:/api/login",
      "summary": "用户登录并获取Token",
      "domain": "auth",
      "safety_level": "readonly_safe",
      "requires_confirmation": false,
      "usage_note": "返回的token有效期24小时"
    }}
  ]
}}

domain 必须是以下之一: auth, customer, finance, inventory, content, analytics, operations, system, unknown
safety_level 必须是以下之一: readonly_safe, readonly_sensitive, soft_write, hard_write, critical
"""
