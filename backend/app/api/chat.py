import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.agent.service import enqueue, process
from app.core.schemas import ChatInput
from app.core.security import require_admin

router = APIRouter(prefix="/api/chat", dependencies=[Depends(require_admin)])


@router.post("/stream")
def chat(request: ChatInput) -> StreamingResponse:
    if request.platform != "web":
        raise HTTPException(400, "此接口只接受 Web 调试消息")
    message_id, _ = enqueue(request)

    async def events():
        yield f"event: status\ndata: {json.dumps('已接收，正在处理', ensure_ascii=False)}\n\n"
        async for event in process(message_id):
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})
