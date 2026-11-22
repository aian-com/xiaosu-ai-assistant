import asyncio
from io import BytesIO
from docx import Document as WordDocument
from fastapi.testclient import TestClient
from app.main import app
from app.knowledge.service import upload, search, remove, list_documents
from app.knowledge.worker import process_one


def test_incremental_update_delete_and_citation():
    first = upload("handbook.md", "# 年假制度\n\n年假为五天。".encode())
    assert asyncio.run(process_one())
    duplicate = upload("handbook.md", "# 年假制度\n\n年假为五天。".encode())
    assert duplicate["deduplicated"]
    assert duplicate["version_id"] == first["version_id"]
    sources = asyncio.run(search("年假"))
    assert sources and all(s["version_id"] == first["version_id"] for s in sources)
    url = sources[0]["url"].replace("http://localhost:8000", "")
    assert TestClient(app).get(url).status_code == 200
    second = upload("handbook.md", "# 年假制度\n\n年假为十天。".encode())
    assert asyncio.run(process_one())
    assert all(s["version_id"] == second["version_id"] for s in asyncio.run(search("年假")))
    assert TestClient(app).get(url).status_code == 410
    remove(first["id"])
    assert asyncio.run(search("年假")) == []


def test_deleted_pending_document_never_returns():
    doc = upload("pending.txt", "设备申领需要负责人批准。".encode())
    remove(doc["id"])
    asyncio.run(process_one())
    assert list_documents() == []
    assert asyncio.run(search("设备申领")) == []


def test_failed_replacement_keeps_previous_version():
    first = upload("guide.md", "新人入职需要账号开通。".encode())
    asyncio.run(process_one())
    upload("guide.md", b"")
    asyncio.run(process_one())
    assert list_documents()[0]["status"] == "failed"
    assert list_documents()[0]["active_version"] == first["version_id"]


def test_three_formats_and_admin_authentication():
    client = TestClient(app)
    assert client.get("/api/documents").status_code == 401
    word = WordDocument()
    word.add_paragraph("差旅申请需主管批准。")
    buffer = BytesIO()
    word.save(buffer)
    for name, content in [("a.md", "报销发票材料。".encode()), ("b.txt", "设备申领流程。".encode()), ("c.docx", buffer.getvalue())]:
        response = client.post("/api/documents", headers={"Authorization": "Bearer test-only"}, files={"file": (name, content)})
        assert response.status_code == 202
        asyncio.run(process_one())
    assert all(d["status"] == "indexed" for d in list_documents())


def test_mime_encoded_chinese_filename():
    from email.header import Header
    encoded = Header("员工手册.md", "utf-8").encode()
    upload(encoded, "报销需提交发票。".encode())
    asyncio.run(process_one())
    assert list_documents()[0]["name"] == "员工手册.md"
    assert list_documents()[0]["status"] == "indexed"
