import asyncio
import pytest
from app.config import get_settings
from types import SimpleNamespace as NS
from app.agent import runner
from app.agent.service import enqueue, process
from app.core.db import session
from app.core.models import Message
from app.core.schemas import ChatInput


class MockMessage:
    def __init__(self, calls):
        self.tool_calls = calls

    def model_dump(self, **kwargs):
        return {"role": "assistant", "tool_calls": [{"id": "clock1", "type": "function", "function": {"name": "current_time", "arguments": "{}"}}]}


class MockLLM:
    def __init__(self):
        self.chat = NS(completions=self)
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        usage = NS(prompt_tokens=10, completion_tokens=2, total_tokens=12)
        if kwargs.get("stream"):
            async def chunks():
                yield NS(usage=None, choices=[NS(delta=NS(content="已查询当前上海时间。"))])
                yield NS(usage=usage, choices=[])
            return chunks()
        calls = [NS(id="clock1", function=NS(name="current_time", arguments="{}"))] if len(self.requests) == 1 else []
        return NS(usage=usage, choices=[NS(message=MockMessage(calls))])


@pytest.mark.parametrize("thinking", [False, True])
def test_mock_llm_tools_stream_usage_and_persistence(monkeypatch, thinking):
    monkeypatch.setenv("LLM_ENABLE_THINKING", str(thinking).lower())
    get_settings.cache_clear()
    mock = MockLLM()
    monkeypatch.setattr(runner, "chat_client", lambda: mock)
    request = ChatInput(text="现在几点？", user_id="A", external_id="unique")
    mid, created = enqueue(request)
    assert created
    assert enqueue(request) == (mid, False)

    async def collect():
        return [event async for event in process(mid)]
    events = asyncio.run(collect())
    assert any(e["event"] == "delta" for e in events)
    assert all(r["extra_body"] == {"enable_thinking": False} for r in mock.requests if not r.get("stream"))
    assert mock.requests[-1]["extra_body"] == {"enable_thinking": thinking}
    assert events[-1]["data"]["usage"]["total_tokens"] == 36
    tool_message = next(m for m in mock.requests[1]["messages"] if m["role"] == "tool")
    assert "last_week_start" in tool_message["content"]
    with session() as db:
        saved = db.get(Message, mid)
        assert saved.status == "done"
        assert saved.tool_calls[0]["name"] == "current_time"
    assert request.conversation_key() != request.model_copy(update={"user_id": "B"}).conversation_key()
