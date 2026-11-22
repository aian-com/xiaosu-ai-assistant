import asyncio
import logging
import time
from collections.abc import AsyncIterator
from sqlalchemy import select
from app.agent.runner import run
from app.config import get_settings
from app.core.db import session, transaction
from app.core.locks import async_lock
from app.core.models import Conversation, Message, Setting
from app.core.schemas import ChatInput


def enqueue(request: ChatInput, reply_url: str | None = None) -> tuple[str, bool]:
    with transaction() as db:
        existing = db.scalar(select(Message).where(Message.platform == request.platform, Message.external_id == request.external_id))
        if existing:
            return existing.id, False
        key = request.conversation_key()
        if not db.get(Conversation, key):
            db.add(Conversation(id=key, platform=request.platform, tenant_id=request.tenant_id, user_id=request.user_id, channel_id=request.channel_id))
            db.flush()
        message = Message(platform=request.platform, external_id=request.external_id, conversation_id=key, question=request.text, reply_url=reply_url)
        db.add(message)
        db.flush()
        return message.id, True


async def process(message_id: str) -> AsyncIterator[dict]:
    try:
        async for event in _process(message_id):
            yield event
    except TimeoutError:
        answer = "当前会话繁忙，请稍后重试。"
        with transaction() as db:
            row = db.get(Message, message_id)
            row.status, row.error, row.answer = "failed", "ConversationBusy", answer
        yield {"event": "error", "data": answer}


async def _process(message_id: str) -> AsyncIterator[dict]:
    start = time.monotonic()
    with session() as db:
        current = db.get(Message, message_id)
        key = current.conversation_id
    async with async_lock("conversation:" + key, timeout=get_settings().request_timeout):
        with transaction() as db:
            current = db.get(Message, message_id)
            if current.status in {"done", "failed"}:
                yield {"event": "done", "data": {"answer": current.answer, "citations": current.citations, "usage": current.usage}}
                return
            current.status = "running"
            question = current.question
            previous = list(db.scalars(select(Message).where(Message.conversation_id == key, Message.status == "done", Message.id != message_id).order_by(Message.created_at.desc()).limit(8)))
            history: list[dict] = []
            for row in reversed(previous):
                history.extend([{"role": "user", "content": row.question}, {"role": "assistant", "content": row.answer}])
            setting = db.get(Setting, "model")
            model = setting.value["name"] if setting else get_settings().llm_model
        calls: list[dict] = []
        try:
            async with asyncio.timeout(get_settings().request_timeout):
                async for event in run(question, history, model):
                    if event["event"] == "tool":
                        calls.append(event["data"])
                        with transaction() as db:
                            db.get(Message, message_id).tool_calls = list(calls)
                    if event["event"] == "done":
                        with transaction() as db:
                            row = db.get(Message, message_id)
                            row.answer = event["data"]["answer"]
                            row.citations = event["data"]["citations"]
                            row.usage = event["data"]["usage"]
                            row.status = "done"
                            row.latency_ms = int((time.monotonic() - start) * 1000)
                        logging.getLogger("xiaosu.chat").info("chat_completed id=%s tools=%s", message_id, len(calls))
                    yield event
        except asyncio.CancelledError:
            with transaction() as db:
                row = db.get(Message, message_id)
                if row.status == "running":
                    row.status, row.error = "failed", "ClientDisconnected"
                    row.answer = "请求已中断，请重新发送。"
            raise
        except Exception as exc:
            code = type(exc).__name__
            logging.getLogger("xiaosu.chat").warning("chat_failed id=%s type=%s", message_id, code)
            answer = "小苏暂时无法完成查询，请稍后重试或联系管理员检查模型与服务配置。"
            with transaction() as db:
                row = db.get(Message, message_id)
                row.answer, row.error, row.status = answer, code, "failed"
                row.latency_ms = int((time.monotonic() - start) * 1000)
            yield {"event": "error", "data": answer}
