import asyncio
import logging
import dingtalk_stream
from app.agent.service import enqueue
from app.config import get_settings
from app.core.db import session
from app.core.logging import setup_logging
from app.core.models import Setting, now
from app.core.schemas import ChatInput
from app.im.delivery import reply


class Handler(dingtalk_stream.ChatbotHandler):
    async def process(self, callback):
        incoming = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
        try:
            if not incoming.text or not incoming.text.content:
                return dingtalk_stream.AckMessage.STATUS_OK, "Unsupported message type"
            request = ChatInput(platform="dingtalk", tenant_id=incoming.sender_corp_id or incoming.chatbot_corp_id or "unknown",
                                channel_id=incoming.conversation_id, user_id=incoming.sender_staff_id or incoming.sender_id,
                                external_id=incoming.message_id, text=incoming.text.content.strip())
            message_id, _ = await asyncio.to_thread(enqueue, request, incoming.session_webhook)
            with session() as db, db.begin():
                db.merge(Setting(key="im-target:" + message_id, value={"type": incoming.conversation_type, "conversation": incoming.conversation_id, "user": incoming.sender_staff_id}))
                db.merge(Setting(key="im", value={"status": "receiving", "last_received": now().isoformat()}))
            return dingtalk_stream.AckMessage.STATUS_OK, "OK"
        except Exception as exc:
            logging.getLogger("xiaosu.im").warning("receive_failed type=%s", type(exc).__name__)
            if incoming.session_webhook:
                try:
                    await reply(incoming.session_webhook, "小苏暂时无法接收请求，请稍后重试。", [])
                except Exception:
                    pass
            return dingtalk_stream.AckMessage.STATUS_SYSTEM_EXCEPTION, "Temporary failure"


def main() -> None:
    setup_logging()
    s = get_settings()
    if not s.dingtalk_client_id or not s.dingtalk_client_secret.get_secret_value():
        raise SystemExit("请先配置 DINGTALK_CLIENT_ID 和 DINGTALK_CLIENT_SECRET")
    with session() as db, db.begin():
        db.merge(Setting(key="im", value={"status": "starting", "started_at": now().isoformat()}))
    client = dingtalk_stream.DingTalkStreamClient(dingtalk_stream.Credential(s.dingtalk_client_id, s.dingtalk_client_secret.get_secret_value()))
    client.register_callback_handler(dingtalk_stream.ChatbotMessage.TOPIC, Handler())
    client.start_forever()


if __name__ == "__main__":
    main()
