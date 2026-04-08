import pytest

from app.graph import nodes_agentic


@pytest.mark.asyncio
async def test_agentic_finish_returns_draft_without_local_token_simulation(monkeypatch):
    nodes_agentic._task_run_llm_cache.clear()
    emitted_events: list[tuple[str, dict]] = []

    def fake_emit(event: str, **payload):
        emitted_events.append((event, payload))

    async def fake_stream_chat_completion(*args, **kwargs):
        yield "token", '{"action":"finish","think":"done","final_answer":"你好，流式世界"}'

    monkeypatch.setattr(nodes_agentic, "_emit", fake_emit)
    monkeypatch.setattr(nodes_agentic.llm_client, "stream_chat_completion", fake_stream_chat_completion)

    state = {
        "agentic_iterations": 0,
        "available_capabilities": [],
        "chat_history": [],
        "user_message": "你好",
        "agentic_history": [],
        "project_description": "测试项目",
        "response_language": "简体中文",
    }
    config = {"configurable": {"thread_id": "test-finish-stream"}}

    result = await nodes_agentic.agentic_loop_node(state, config)

    assert result["agentic_done"] is True
    assert result["final_answer_draft"] == "你好，流式世界"
    assert "summary_text" not in result

    token_events = [
        payload
        for event_name, payload in emitted_events
        if event_name == "token_emitted"
    ]
    assert token_events == []


@pytest.mark.asyncio
async def test_agentic_finish_without_final_answer_returns_protocol_error(monkeypatch):
    nodes_agentic._task_run_llm_cache.clear()

    def fake_emit(event: str, **payload):
        return None

    async def fake_stream_chat_completion(*args, **kwargs):
        yield "token", '{"action":"finish","think":"done"}'

    monkeypatch.setattr(nodes_agentic, "_emit", fake_emit)
    monkeypatch.setattr(nodes_agentic.llm_client, "stream_chat_completion", fake_stream_chat_completion)

    state = {
        "agentic_iterations": 0,
        "available_capabilities": [],
        "chat_history": [],
        "user_message": "请帮我查询一条数据",
        "agentic_history": [],
        "project_description": "测试项目",
        "response_language": "简体中文",
    }
    config = {"configurable": {"thread_id": "test-finish-missing-final-answer"}}

    result = await nodes_agentic.agentic_loop_node(state, config)

    assert result["agentic_done"] is True
    assert result.get("error") == "AI 输出格式错误：finish 缺少 final_answer"
    assert "final_answer_draft" not in result


@pytest.mark.asyncio
async def test_plain_text_agentic_output_returns_protocol_error(monkeypatch):
    nodes_agentic._task_run_llm_cache.clear()

    def fake_emit(event: str, **payload):
        return None

    async def fake_stream_plain_text(*args, **kwargs):
        yield "token", "后端正在流式输出。\n我已完成验证。"

    monkeypatch.setattr(nodes_agentic, "_emit", fake_emit)
    monkeypatch.setattr(nodes_agentic.llm_client, "stream_chat_completion", fake_stream_plain_text)

    state = {
        "agentic_iterations": 0,
        "available_capabilities": [],
        "chat_history": [],
        "user_message": "请调用接口读取一条真实数据",
        "agentic_history": [],
        "project_description": "测试项目",
        "response_language": "简体中文",
    }
    config = {"configurable": {"thread_id": "test-plain-text-protocol-error"}}

    result = await nodes_agentic.agentic_loop_node(state, config)
    assert "final_answer_draft" not in result
    assert result.get("error", "").startswith("AI 输出格式错误")
