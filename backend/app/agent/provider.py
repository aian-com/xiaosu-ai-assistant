from openai import AsyncOpenAI
from app.config import get_settings
import hashlib
import math


def embedding_id() -> str:
    s = get_settings()
    identity = s.embedding_base_url.rstrip("/") + "|" + s.embedding_model
    return "embedding:" + hashlib.sha256(identity.encode()).hexdigest()


def chat_client() -> AsyncOpenAI:
    s = get_settings()
    if not s.llm_api_key.get_secret_value() or not s.llm_model or not s.llm_base_url:
        raise ValueError("聊天模型未配置，请管理员补充 LLM 配置")
    return AsyncOpenAI(api_key=s.llm_api_key.get_secret_value(), base_url=s.llm_base_url, timeout=30, max_retries=2)


async def embed(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    if not s.embedding_api_key.get_secret_value() or not s.embedding_model or not s.embedding_base_url:
        raise ValueError("向量模型未配置，请管理员补充 EMBEDDING 配置")
    async with AsyncOpenAI(api_key=s.embedding_api_key.get_secret_value(), base_url=s.embedding_base_url, timeout=60, max_retries=2) as client:
        result: list[list[float]] = []
        for start in range(0, len(texts), 32):
            batch = texts[start:start + 32]
            response = await client.embeddings.create(model=s.embedding_model, input=batch, encoding_format="float")
            items = sorted(response.data, key=lambda x: x.index)
            if [item.index for item in items] != list(range(len(batch))):
                raise ValueError("Embedding 返回数量或索引不正确")
            for item in items:
                vector = item.embedding
                if not vector or any(not math.isfinite(v) for v in vector) or not any(vector):
                    raise ValueError("Embedding 返回无效向量")
                if result and len(vector) != len(result[0]):
                    raise ValueError("Embedding 返回维度不一致")
                result.append(vector)
        return result
