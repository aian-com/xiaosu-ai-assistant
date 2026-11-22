import asyncio
from unittest.mock import AsyncMock
import httpx
import pytest
from app.agent import tools, runner
from app.agent.service import enqueue, process
from app.core.schemas import ChatInput
from tests.test_agent import MockLLM


def test_logs_written_to_file(monkeypatch, tmp_path):
    import logging
    from app.config import get_settings
    from app.core.logging import setup_logging
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    get_settings.cache_clear()
    logger = logging.getLogger("xiaosu")
    before = list(logger.handlers)
    try:
        setup_logging()
        setup_logging()
        logging.getLogger("xiaosu.test").warning("fallback_log_probe")
        content = (tmp_path / "logs" / "xiaosu.log").read_text(encoding="utf-8")
        assert content.count("fallback_log_probe") == 1
    finally:
        for handler in list(logger.handlers):
            if handler not in before:
                logger.removeHandler(handler)
                handler.close()


@pytest.mark.parametrize("failure", ["timeout", "rate_limit"])
def test_internal_api_retries(monkeypatch, failure):
    calls = []
    def handle(request):
        calls.append(request)
        if len(calls) < 3:
            if failure == "timeout":
                raise httpx.ReadTimeout("test", request=request)
            return httpx.Response(429)
        return httpx.Response(200, json={"id": "001", "name": "张三", "dept": "研发部"})
    original = httpx.AsyncClient
    monkeypatch.setattr(tools.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    monkeypatch.setattr(tools.asyncio, "sleep", AsyncMock())
    result = asyncio.run(tools.execute("get_employee", {"employee_id": "001"}))
    assert result["employee"]["id"] == "001"
    assert len(calls) == 3


def test_model_failure_returns_error_event(monkeypatch):
    def unavailable():
        raise httpx.ReadTimeout("private upstream details")
    monkeypatch.setattr(runner, "chat_client", unavailable)
    mid, _ = enqueue(ChatInput(text="现在几点", external_id="failure"))
    async def collect():
        return [event async for event in process(mid)]
    events = asyncio.run(collect())
    assert events[-1]["event"] == "error"
    assert "暂时无法" in events[-1]["data"]
    assert "private" not in events[-1]["data"]


def test_fabricated_citation_is_rejected(monkeypatch):
    from types import SimpleNamespace as NS
    class InvalidAnswer(MockLLM):
        async def create(self, **kwargs):
            if kwargs.get("stream"):
                async def chunks():
                    yield NS(usage=None, choices=[NS(delta=NS(content="虚构制度 [cite:invented]"))])
                return chunks()
            return await super().create(**kwargs)
    monkeypatch.setattr(runner, "chat_client", InvalidAnswer)
    async def collect():
        return [event async for event in runner.run("问题", [], "mock")]
    events = asyncio.run(collect())
    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["citations"] == []
    assert "没找到可验证" in events[-1]["data"]["answer"]
