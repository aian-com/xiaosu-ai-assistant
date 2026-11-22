import asyncio
import logging
import time
import httpx
from app.config import get_settings
from app.im.cards import Card, visible
from sqlalchemy import select, update
from app.agent.service import process
from app.core.db import session, transaction
from app.core.locks import async_lock
from app.core.logging import setup_logging
from app.core.models import Message, Setting
from app.im.delivery import reply
from app.knowledge.service import valid_citations


async def tick() -> bool:
    with session() as db:
        row = db.scalar(select(Message).where(Message.platform == "dingtalk", Message.delivery == "pending").order_by(Message.created_at).limit(1))
        if not row:
            return False
        message_id, url = row.id, row.reply_url
    card = None
    client = httpx.AsyncClient(timeout=15)
    try:
        with session() as db:
            target = db.get(Setting, "im-target:" + message_id)
            target = target.value if target else None
        if get_settings().dingtalk_card_template_id and target:
            try:
                card = await Card.create(client, "xiaosu-" + message_id, target)
            except Exception as exc:
                logging.getLogger("xiaosu.im").warning("card_create_failed type=%s", type(exc).__name__)
        draft, last_update = "", 0.0
        async for event in process(message_id):
            if event["event"] == "delta":
                draft += event["data"]
                if card and time.monotonic() - last_update >= 0.8:
                    try:
                        await card.update(visible(draft))
                        last_update = time.monotonic()
                    except Exception:
                        try:
                            await card.update("实时更新中断，完整答案将另行发送。", final=True, failed=True)
                        except Exception:
                            pass
                        card = None
    except BaseException:
        await client.aclose()
        raise
    with session() as db:
        row = db.get(Message, message_id)
        answer, citations = row.answer, row.citations
    if citations and not valid_citations(citations):
        answer, citations = "相关文档刚刚发生更新或删除，请重新提问获取当前依据。", []
        with transaction() as db:
            row = db.get(Message, message_id)
            row.answer, row.citations = answer, citations
    try:
        if card:
            sources = "、".join(f"[{c['file']}]({c['url']})" for c in citations)
            try:
                await card.update(visible(answer) + ("\n\n来源：" + sources if sources else ""), final=True)
            except Exception:
                await reply(url, answer, citations)
        else:
            await reply(url, answer, citations)
        delivery = "sent"
    except Exception as exc:
        delivery = "failed"
        logging.getLogger("xiaosu.im").warning("delivery_failed id=%s type=%s", message_id, type(exc).__name__)
    finally:
        await client.aclose()
    with transaction() as db:
        row = db.get(Message, message_id)
        row.delivery = delivery
        row.reply_url = None  # Remove temporary credential once delivery finishes.
        target = db.get(Setting, "im-target:" + message_id)
        if target:
            db.delete(target)
    return True


async def run() -> None:
    setup_logging()
    async with async_lock("im-worker", timeout=0):
        with transaction() as db:
            db.execute(update(Message).where(Message.platform == "dingtalk", Message.status == "running").values(status="queued"))
        while True:
            try:
                if not await tick():
                    await asyncio.sleep(1)
            except Exception as exc:
                logging.getLogger("xiaosu.im").warning("worker_failed type=%s", type(exc).__name__)
                await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(run())
