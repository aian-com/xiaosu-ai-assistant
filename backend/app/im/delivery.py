from urllib.parse import urlparse
import re
import httpx


async def reply(url: str, answer: str, citations: list[dict]) -> None:
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != "oapi.dingtalk.com"
            or parsed.path not in {"/robot/send", "/robot/sendBySession"}
            or parsed.username or parsed.password or parsed.port not in {None, 443}):
        raise ValueError("非允许的钉钉回复地址")
    answer = re.sub(r"[ \t]*\[cite:([^\]]+)\]", "", answer).strip()
    sources = "、".join(f"[{c['file']}]({c['url']})" for c in citations)
    text = answer + ("\n\n来源：" + sources if sources else "")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, json={"msgtype": "markdown", "markdown": {"title": "小苏", "text": text}})
        response.raise_for_status()
        if response.json().get("errcode") != 0:
            raise RuntimeError("钉钉拒绝消息，请检查 webhook 是否过期")
