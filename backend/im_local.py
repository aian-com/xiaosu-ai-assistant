"""Local Stream launcher: keep SDK connection tickets out of logs."""
import asyncio
import logging
from pathlib import Path
import dingtalk_stream
from app.config import get_settings
from app.core.logging import setup_logging
from app.im.adapter import Handler

async def main():
    setup_logging()
    settings = get_settings()
    logger = logging.getLogger("dingtalk-local-private")
    logger.disabled = True
    client = dingtalk_stream.DingTalkStreamClient(dingtalk_stream.Credential(
        settings.dingtalk_client_id, settings.dingtalk_client_secret.get_secret_value()), logger=logger)
    client.register_callback_handler(dingtalk_stream.ChatbotMessage.TOPIC, Handler())
    task = asyncio.create_task(client.start())
    status = Path(__file__).resolve().parents[1] / "local" / "im-connection.txt"
    status.parent.mkdir(parents=True, exist_ok=True)
    try:
        while not task.done():
            status.write_text("connected" if client.websocket is not None else "connecting", encoding="utf-8")
            await asyncio.sleep(2)
        await task
    finally:
        status.write_text("stopped", encoding="utf-8")

if __name__ == "__main__":
    asyncio.run(main())
