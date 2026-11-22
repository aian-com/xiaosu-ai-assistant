import asyncio
import httpx
import pytest
from app.im.delivery import reply


@pytest.mark.parametrize("path", ["/robot/send", "/robot/sendBySession"])
def test_reply_supports_session_webhook(monkeypatch, path):
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"errcode": 0})
    client = httpx.AsyncClient
    monkeypatch.setattr("app.im.delivery.httpx.AsyncClient", lambda **kw: client(transport=httpx.MockTransport(handle), **kw))
    asyncio.run(reply("https://oapi.dingtalk.com" + path + "?session=test", "回答", []))
    assert len(requests) == 1
    assert "回答" in requests[0].content.decode()


@pytest.mark.parametrize("url", [
    "http://oapi.dingtalk.com/robot/sendBySession",
    "https://example.com/robot/sendBySession",
    "https://oapi.dingtalk.com/other",
    "https://user@oapi.dingtalk.com/robot/sendBySession",
])
def test_reply_rejects_untrusted_url(url):
    with pytest.raises(ValueError):
        asyncio.run(reply(url, "回答", []))
