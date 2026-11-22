import asyncio
from types import SimpleNamespace as NS
import pytest
from pydantic import SecretStr
from app.agent import provider
from app.config import get_settings
from app.core.db import transaction
from app.core.models import Chunk
from app.knowledge import service
from app.knowledge.worker import process_one
from sqlalchemy import select


class FakeEmbeddingAPI:
    def __init__(self, malformed=False):
        self.embeddings = self
        self.requests = []
        self.malformed = malformed

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        data = [NS(index=i, embedding=[float(text), 1.0]) for i, text in enumerate(kwargs["input"])]
        return NS(data=[] if self.malformed else list(reversed(data)))


def test_embedding_batches_restore_response_order(monkeypatch):
    client = FakeEmbeddingAPI()
    monkeypatch.setattr(provider, "AsyncOpenAI", lambda **kwargs: client)
    result = asyncio.run(provider.embed([str(i) for i in range(33)]))
    assert result == [[float(i), 1.0] for i in range(33)]
    assert [len(r["input"]) for r in client.requests] == [32, 1]
    assert all(r["model"] == "mock-embedding" for r in client.requests)


def test_bad_embedding_count_is_rejected(monkeypatch):
    monkeypatch.setattr(provider, "AsyncOpenAI", lambda **kwargs: FakeEmbeddingAPI(True))
    with pytest.raises(ValueError, match="数量或索引"):
        asyncio.run(provider.embed(["1"]))


def test_missing_config_has_no_local_fallback(monkeypatch):
    monkeypatch.setattr(get_settings(), "embedding_api_key", SecretStr(""))
    with pytest.raises(ValueError, match="未配置"):
        asyncio.run(provider.embed(["年假"]))


def test_legacy_vectors_excluded_and_rebuildable():
    # Regression fixture only: old persisted indexes must never enter semantic search.
    doc = service.upload("policy.md", "年假制度：年假五天。".encode())
    asyncio.run(process_one())
    with transaction() as db:
        for chunk in db.scalars(select(Chunk)):
            chunk.embedding_model = "local-char-ngram-v1"
    assert service.list_documents()[0]["needs_reindex"]
    assert asyncio.run(service.search("年假")) == []
    service.retry(doc["id"])
    asyncio.run(process_one())
    assert not service.list_documents()[0]["needs_reindex"]
    assert asyncio.run(service.search("年假"))
