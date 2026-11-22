"""Run explicitly against the already started local application."""
import time
from pathlib import Path
import httpx
from app.config import get_settings


def main():
    root = Path(__file__).resolve().parents[2]
    secret = get_settings().admin_secret.get_secret_value()
    with httpx.Client(base_url="http://127.0.0.1:8000", headers={"Authorization": f"Bearer {secret}"}, timeout=20) as client:
        assert client.get("/health").status_code == 200
        sample = root / "fixtures" / "knowledge" / "员工手册.md"
        response = client.post("/api/documents", files={"file": (sample.name, sample.read_bytes(), "text/markdown")})
        response.raise_for_status()
        document_id = response.json()["id"]
        for _ in range(40):
            documents = client.get("/api/documents").json()
            row = next(row for row in documents if row["id"] == document_id)
            if row["status"] != "pending":
                break
            time.sleep(0.25)
        settings = get_settings()
        configured = bool(settings.embedding_api_key.get_secret_value() and settings.embedding_model and settings.embedding_base_url)
        if configured:
            assert row["status"] == "indexed", row
            duplicate = client.post("/api/documents", files={"file": (sample.name, sample.read_bytes())}).json()
            assert duplicate["deduplicated"]
        else:
            assert row["status"] == "failed" and "未配置" in row["error"], row
        result = client.post("/api/chat/stream", json={"text": "本地启动检查：现在几点？"})
        assert result.status_code == 200
        assert "event: error" in result.text or "event: done" in result.text
        assert client.get("/api/conversations").json()
    assert httpx.get("http://127.0.0.1:5173/").status_code == 200
    assert httpx.get("http://127.0.0.1:8001/api/employee/001").json()["dept"] == "研发部"
    print("Live smoke passed: UI/API/upload/chat/logs/mock. Embedding indexing verified:", configured)


if __name__ == "__main__":
    main()
