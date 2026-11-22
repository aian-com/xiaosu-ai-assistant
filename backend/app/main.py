from contextlib import asynccontextmanager
from pathlib import Path
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from app.config import Settings
from app.core.logging import setup_logging
from app.api import admin, chat, documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(title="小苏 API", version="0.2.0", lifespan=lifespan)
app.include_router(documents.router)
app.include_router(documents.sources)
app.include_router(chat.router)
app.include_router(admin.router)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logging.getLogger("xiaosu.api").error("database_failed type=%s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "数据库暂不可用，请检查数据库配置与迁移状态"})


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logging.getLogger("xiaosu.api").error("request_failed type=%s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "服务暂时无法完成请求，请稍后重试。"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "stage": "framework", "note": "进程存活不代表外部接入已验证"}


@app.get("/readiness")
def readiness() -> dict[str, bool]:
    settings = Settings()
    return {
        "model_configured": bool(settings.llm_api_key.get_secret_value() and settings.llm_model),
        "embedding_configured": bool(settings.embedding_api_key.get_secret_value() and settings.embedding_model and settings.embedding_base_url),
        "im_configured": bool(settings.dingtalk_client_id and settings.dingtalk_client_secret.get_secret_value()),
        "model_verified": False,
        "im_verified": False,
    }


static = Path(__file__).resolve().parents[2] / "static"
if static.exists():
    app.mount("/", StaticFiles(directory=static, html=True), name="frontend")
