import asyncio
import logging
from pathlib import Path
from sqlalchemy import delete, select, update
from app.agent.provider import embed, embedding_id
from app.config import get_settings
from app.core.db import session, transaction
from app.core.locks import async_lock
from app.core.logging import setup_logging
from app.core.models import Chunk, Document, Job, Version, now
from app.knowledge.parser import parse


async def process_one() -> bool:
    with transaction() as db:
        job = db.scalar(select(Job).where(Job.status == "pending").order_by(Job.updated_at).limit(1))
        if not job:
            return False
        job.status, job.updated_at = "running", now()
        job_id, version_id = job.id, job.version_id
        version = db.get(Version, version_id)
        path, document_id = version.path, version.document_id
    try:
        parts = await asyncio.to_thread(parse, Path(path))
        vectors = await embed([part.text for part in parts])
        if len(vectors) != len(parts):
            raise ValueError("embedding 数量不匹配")
        with transaction() as db:
            doc = db.get(Document, document_id)
            version = db.get(Version, version_id)
            job = db.get(Job, job_id)
            if doc.deleted or doc.latest_version != version_id:
                version.status, job.status = "failed", "cancelled"
                version.error = "文档已删除或被较新的上传替代"
                return True
            db.execute(delete(Chunk).where(Chunk.version_id == version_id))
            for i, (part, vector) in enumerate(zip(parts, vectors)):
                db.add(Chunk(version_id=version_id, ordinal=i, location=part.location, text=part.text,
                             embedding=vector, embedding_model=embedding_id()))
            doc.active_version = version_id
            version.status, version.error = "indexed", None
            job.status, job.updated_at = "done", now()
    except Exception as exc:
        logging.getLogger("xiaosu.index").warning("index_failed version=%s type=%s", version_id, type(exc).__name__)
        with transaction() as db:
            version = db.get(Version, version_id)
            version.status = "failed"
            version.error = str(exc)[:250] if isinstance(exc, ValueError) else f"索引失败：{type(exc).__name__}，请检查解析器或模型配置"
            job = db.get(Job, job_id)
            job.status, job.updated_at = "failed", now()
    return True


async def run() -> None:
    setup_logging()
    async with async_lock("index-worker", timeout=0):
        with transaction() as db:
            db.execute(update(Job).where(Job.status == "running").values(status="pending"))
        while True:
            if not await process_one():
                await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(run())
