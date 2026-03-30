import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.schemas.route_map import RouteMap
from app.graph.llm_client import llm_client
from app.models.project import Project

_PROJECT_CONTEXT_PROMPT = """
你是一个资深架构师和技术总结专家。
我将为你提供一个后端服务项目的候选接口清单，以及提取到的极少量自述文件片段（如果有的话）。
请你根据这些接口和描述，概括这个项目“总体上是用来干什么的”。

【输入信息】
接口列表总数：{route_count}
接口概览：
{routes_summary}

文档参考（可能极其残缺或写得很烂，甚至没有）：
{docs_reference}

【你的任务】
请用一到两句话（不超过 300 字）全局概况以下内容：
1. 这是什么垂直领域的应用系统？（如：电商交易后台、OA办公系统、基础鉴权微服务等）
2. 该系统提供的核心基础能力是什么？
你只需要输出这一段话，【绝对不要】输出 Markdown 标题或其他多余的分析思考过程。
"""

async def generate_project_context(
    route_map: RouteMap,
    source_path: str | None,
    db: AsyncSession,
) -> str:
    """自动生成并更新项目上下文"""
    route_count = len(route_map.routes)
    
    # 抽取具有代表性的摘要接口（比如前20个）
    routes_summary_lines = []
    for r in route_map.routes[:20]:
        summary_str = r.summary or "无备注"
        routes_summary_lines.append(f"- {r.method.value.upper()} {r.path} : {summary_str}")
    if route_count > 20:
        routes_summary_lines.append(f"... (以及其他 {route_count - 20} 个接口)")
    routes_summary = "\n".join(routes_summary_lines)
    
    # 尝试探索可能存在的元数据文档
    docs_reference = "（未提供源码路径，无法提取）"
    if source_path and os.path.exists(source_path) and os.path.isdir(source_path):
        docs_reference = "（项目目录下未找到常见的自述文件）"
        candidate_files = ["README.md", "README.txt", "package.json", "requirements.txt", "pom.xml", "pyproject.toml"]
        root_path = Path(source_path)
        
        for candidate in candidate_files:
            file_path = root_path / candidate
            if file_path.exists() and file_path.is_file():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read(3000) # 只取前3000个字符避免挤爆上下文
                        docs_reference = f"来源文件: {candidate}\n内容截取:\n{content}"
                        break
                except Exception:
                    continue
                    
    # 调用 LLM 进行推断
    prompt = _PROJECT_CONTEXT_PROMPT.format(
        route_count=route_count,
        routes_summary=routes_summary,
        docs_reference=docs_reference
    )
    
    try:
        content, _, _ = await llm_client.chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.3
        )
        global_context = content.strip()
    except Exception as e:
        print(f"[ProjectContextEnricher] 全局上下文推断失败: {e}")
        global_context = "AI全局总结失败，暂无整体概念描述。"
        
    # 保存结果回数据库 (平滑追加)
    try:
        result = await db.execute(select(Project).where(Project.id == route_map.project_id))
        project = result.scalar_one_or_none()
        if project:
            original = project.description or ""
            # 若已经包含了前缀，为了防止重复就覆盖或者跳过，简单处理为重新拼接
            # 其实导入时一般是短句。若已有AI结果可能也是被触发第二次。这里做个清理。
            clean_original = original.split("【AI 提取的全局业务上下文】：")[0].strip()
            
            new_desc = clean_original
            if new_desc:
                new_desc += "\n\n"
            new_desc += f"【AI 提取的全局业务上下文】：\n{global_context}"
            
            project.description = new_desc
            await db.commit()
    except Exception as e:
        print(f"[ProjectContextEnricher] 保存上下文到描述字段时出现异常: {e}")
        
    return global_context
