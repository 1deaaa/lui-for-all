import pytest

from app.graph import nodes


@pytest.mark.asyncio
async def test_agent_entry_direct_streams_body_without_strategy_token(monkeypatch):
    emitted: list[tuple[str, dict]] = []

    def fake_emit(event: str, **payload):
        emitted.append((event, payload))

    async def fake_stream_chat_completion(*args, **kwargs):
        yield "token", "<strategy>direct</strategy>你好，"
        yield "token", "这是正文。"

    async def should_not_call_simple_completion(*args, **kwargs):
        raise AssertionError("agent_entry_node 不应调用 simple_completion")

    monkeypatch.setattr(nodes, "emit_runtime_event", fake_emit)
    monkeypatch.setattr(nodes.llm_client, "stream_chat_completion", fake_stream_chat_completion)
    monkeypatch.setattr(nodes.llm_client, "simple_completion", should_not_call_simple_completion)

    state = {
        "available_capabilities": [],
        "chat_history": [],
        "user_message": "请直接回复",
        "response_language": "简体中文",
        "project_description": "测试项目",
    }

    result = await nodes.agent_entry_node(state)

    assert result["request_complexity"] == "direct"
    assert result["agentic_done"] is True
    assert result["summary_text"] == "你好，这是正文。"

    token_payloads = [payload for event, payload in emitted if event == "token_emitted"]
    assert token_payloads
    assert all("<strategy>" not in str(p.get("token", "")) for p in token_payloads)


@pytest.mark.asyncio
async def test_agent_entry_agentic_does_not_emit_body_tokens(monkeypatch):
    emitted: list[tuple[str, dict]] = []

    def fake_emit(event: str, **payload):
        emitted.append((event, payload))

    async def fake_stream_chat_completion(*args, **kwargs):
        yield "token", "<strategy>agentic</strategy>"
        yield "token", "这段文本不应发给前端"

    monkeypatch.setattr(nodes, "emit_runtime_event", fake_emit)
    monkeypatch.setattr(nodes.llm_client, "stream_chat_completion", fake_stream_chat_completion)

    state = {
        "available_capabilities": [],
        "chat_history": [],
        "user_message": "请调用接口读取数据",
        "response_language": "简体中文",
        "project_description": "测试项目",
    }

    result = await nodes.agent_entry_node(state)

    assert result["request_complexity"] == "agentic"
    assert result["agentic_done"] is False
    assert "summary_text" not in result

    token_payloads = [payload for event, payload in emitted if event == "token_emitted"]
    assert token_payloads == []
