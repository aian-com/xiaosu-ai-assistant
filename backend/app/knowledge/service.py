import hashlib
from email.header import decode_header, make_header
from pathlib import Path
from sqlalchemy import select
from fastapi import HTTPException
from app.config import get_settings
from app.core.db import session, transaction
from app.core.models import Chunk, Document, Job, Version, uid
from app.agent.provider import embed, embedding_id
from app.knowledge.vectors import cosine
from app.core.security import source_url


def upload(name: str, content: bytes) -> dict:
    if name.startswith("=?"):
        name = str(make_header(decode_header(name)))
    name = Path(name.replace("\\", "/")).name.strip()
    if not name or len(name) > 255 or Path(name).suffix.lower() not in {".md", ".txt", ".pdf", ".docx"}:
        raise HTTPException(400, "文件名或格式不支持")
    digest = hashlib.sha256(content).hexdigest()
    with transaction() as db:
        doc = db.scalar(select(Document).where(Document.name == name))
        if doc is None:
            doc = Document(name=name)
            db.add(doc)
            db.flush()
        latest = db.get(Version, doc.latest_version) if doc.latest_version else None
        compatible = True
        if latest and latest.status == "indexed":
            previous_chunk = db.scalar(select(Chunk).where(Chunk.version_id == latest.id).limit(1))
            compatible = bool(previous_chunk and previous_chunk.embedding_model == embedding_id())
        if not doc.deleted and latest and latest.digest == digest and compatible and latest.status in {"pending", "indexed"}:
            return {"id": doc.id, "version_id": latest.id, "deduplicated": True}
        version_id = uid()
        folder = get_settings().data_dir / "uploads"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{version_id}{Path(name).suffix.lower()}"
        path.write_bytes(content)
        version = Version(id=version_id, document_id=doc.id, digest=digest, path=str(path))
        db.add(version)
        db.flush()
        db.add(Job(version_id=version_id))
        doc.latest_version = version_id
        doc.deleted = False
        return {"id": doc.id, "version_id": version_id, "deduplicated": False}


def list_documents() -> list[dict]:
    with session() as db:
        result = []
        for doc in db.scalars(select(Document).where(Document.deleted.is_(False)).order_by(Document.name)):
            v = db.get(Version, doc.latest_version)
            chunk = db.scalar(select(Chunk).where(Chunk.version_id == doc.active_version).limit(1)) if doc.active_version else None
            needs_reindex = bool(chunk and chunk.embedding_model != embedding_id())
            result.append({"id": doc.id, "name": doc.name, "status": v.status if v else "failed", "error": v.error if v else None, "active_version": doc.active_version, "latest_version": doc.latest_version, "needs_reindex": needs_reindex})
        return result


def remove(document_id: str) -> None:
    with transaction() as db:
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(404, "文档不存在")
        doc.deleted = True
        doc.active_version = None


def retry(document_id: str) -> None:
    with transaction() as db:
        doc = db.get(Document, document_id)
        if not doc or doc.deleted:
            raise HTTPException(404, "文档不存在")
        v = db.get(Version, doc.latest_version)
        if v and v.status == "indexed":
            # A new version keeps existing evidence immutable until the new index succeeds.
            replacement = Version(document_id=doc.id, digest=v.digest, path=v.path)
            db.add(replacement)
            db.flush()
            doc.latest_version = replacement.id
            db.add(Job(version_id=replacement.id))
            return
        if not v or v.status != "failed":
            raise HTTPException(409, "索引任务正在处理，请稍后重试")
        job = db.scalar(select(Job).where(Job.version_id == v.id))
        v.status, v.error = "pending", None
        job.status = "pending"


async def search(query: str) -> list[dict]:
    vector = (await embed([query]))[0]
    s = get_settings()
    with session() as db:
        rows = db.execute(select(Chunk, Document.name)
                          .join(Version, Chunk.version_id == Version.id)
                          .join(Document, Version.document_id == Document.id)
                          .where(Document.deleted.is_(False), Document.active_version == Version.id,
                                 Chunk.embedding_model == embedding_id())).all()
        ranked = sorted(((cosine(vector, c.embedding), c, name) for c, name in rows), key=lambda row: row[0], reverse=True)
        return [{"id": c.id, "version_id": c.version_id, "file": name, "location": c.location,
                 "text": c.text, "score": round(score, 4), "url": source_url(c.version_id, c.id)}
                for score, c, name in ranked if score >= s.retrieval_min_score][:5]


def valid_citations(citations: list[dict]) -> bool:
    with session() as db:
        for c in citations:
            version = db.get(Version, c["version_id"])
            doc = db.get(Document, version.document_id) if version else None
            if not doc or doc.deleted or doc.active_version != version.id:
                return False
            chunk = db.get(Chunk, c["id"])
            if not chunk or chunk.version_id != version.id or chunk.embedding_model != embedding_id():
                return False
    return True
