from html import escape
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from app.config import get_settings
from app.core.db import session
from app.core.models import Chunk, Document, Version
from app.core.security import check_signature, require_admin
from app.knowledge import service

router = APIRouter(prefix="/api/documents", dependencies=[Depends(require_admin)])
sources = APIRouter(prefix="/api/sources")


@router.get("")
def listing() -> list[dict]:
    return service.list_documents()


@router.post("", status_code=202)
async def upload(file: UploadFile = File(...)) -> dict:
    limit = get_settings().max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)
    await file.close()
    if not content or len(content) > limit:
        raise HTTPException(413, "文件为空或超过大小限制")
    return service.upload(file.filename or "", content)


@router.delete("/{document_id}")
def remove(document_id: str) -> dict:
    service.remove(document_id)
    return {"deleted": True}


@router.post("/{document_id}/retry")
def retry(document_id: str) -> dict:
    service.retry(document_id)
    return {"queued": True}


@sources.get("/{version_id}", response_class=HTMLResponse)
def source(version_id: str, expires: int, sig: str) -> HTMLResponse:
    check_signature(version_id, expires, sig)
    with session() as db:
        version = db.get(Version, version_id)
        doc = db.get(Document, version.document_id) if version else None
        if not doc:
            raise HTTPException(404, "原文不存在")
        if doc.deleted or doc.active_version != version_id:
            return HTMLResponse("<meta charset='utf-8'><h1>该文档已删除或更新</h1><p>请重新提问，获取当前版本引用。</p>", status_code=410)
        chunks = db.scalars(select(Chunk).where(Chunk.version_id == version_id).order_by(Chunk.ordinal))
        body = "".join(f'<section id="chunk-{c.id}"><h3>{escape(c.location)}</h3><pre>{escape(c.text)}</pre></section>' for c in chunks)
        return HTMLResponse(f'<!doctype html><meta charset="utf-8"><title>{escape(doc.name)}</title><style>body{{max-width:900px;margin:40px auto;padding:20px;font:16px/1.8 sans-serif}}pre{{white-space:pre-wrap}}section{{padding:18px;border-bottom:1px solid #ddd}}section:target{{background:#fff0b3}}</style><h1>{escape(doc.name)}</h1>{body}', headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})
