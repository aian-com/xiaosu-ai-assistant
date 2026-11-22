import pytest
from app.config import get_settings
from app.core.db import factory
from app.core.models import Base


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + (tmp_path / "test.sqlite3").as_posix())
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ADMIN_SECRET", "test-only")
    monkeypatch.setenv("EMBEDDING_MODEL", "mock-embedding")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-only")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    get_settings.cache_clear()
    factory.cache_clear()
    engine = factory().kw["bind"]
    Base.metadata.create_all(engine)
    # Explicit test double only; production always calls the embedding provider.
    async def mock_embed(texts):
        return [[1.0, 0.0, 0.0] for _ in texts]
    monkeypatch.setattr("app.knowledge.service.embed", mock_embed)
    monkeypatch.setattr("app.knowledge.worker.embed", mock_embed)
    yield
    engine.dispose()
    factory.cache_clear()
    get_settings.cache_clear()
