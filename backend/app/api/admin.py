from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from app.config import get_settings
from app.core.db import session
from app.core.models import Conversation, Message, Setting
from app.core.security import require_admin

router = APIRouter(prefix="/api", dependencies=[Depends(require_admin)])


class ModelChoice(BaseModel):
    model: str


def allowed_models() -> list[str]:
    s = get_settings()
    return list(dict.fromkeys(x.strip() for x in (s.allowed_models + "," + s.llm_model).split(",") if x.strip()))


@router.get("/settings")
def settings() -> dict:
    s = get_settings()
    with session() as db:
        choice = db.get(Setting, "model")
        im = db.get(Setting, "im")
        return {"model": choice.value["name"] if choice else s.llm_model, "allowed_models": allowed_models(),
                "model_configured": bool(s.llm_api_key.get_secret_value() and s.llm_model and s.llm_base_url),
                "embedding_configured": bool(s.embedding_api_key.get_secret_value() and s.embedding_model and s.embedding_base_url),
                "embedding_model": s.embedding_model,
                "im_configured": bool(s.dingtalk_client_id and s.dingtalk_client_secret.get_secret_value()),
                "im": im.value if im else {"status": "not_started"}, "im_streaming": False,
                "verification": "本地开发：基础流程待验证，模型配置可后续补充"}


@router.patch("/settings")
def update_settings(choice: ModelChoice) -> dict:
    if choice.model not in allowed_models():
        raise HTTPException(400, "模型不在服务端允许列表")
    with session() as db, db.begin():
        db.merge(Setting(key="model", value={"name": choice.model}))
    return {"model": choice.model}


@router.get("/conversations")
def conversations(user: str = "", since: datetime | None = None, limit: int = Query(100, ge=1, le=200)) -> list[dict]:
    with session() as db:
        query = select(Message, Conversation).join(Conversation).order_by(Message.created_at.desc()).limit(limit)
        if user:
            query = query.where(Conversation.user_id == user)
        if since:
            query = query.where(Message.created_at >= since)
        return [{"id": m.id, "conversation_id": m.conversation_id, "platform": m.platform, "user": c.user_id,
                 "question": m.question, "answer": m.answer, "citations": m.citations, "tool_calls": m.tool_calls,
                 "usage": m.usage, "error": m.error, "status": m.status, "delivery": m.delivery,
                 "latency_ms": m.latency_ms, "created_at": m.created_at.isoformat()}
                for m, c in db.execute(query)]
