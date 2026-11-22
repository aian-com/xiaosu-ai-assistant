import hashlib
import hmac
import time
from fastapi import Header, HTTPException
from app.config import get_settings


def require_admin(authorization: str = Header(default="")) -> None:
    secret = get_settings().admin_secret.get_secret_value()
    if not secret:
        raise HTTPException(503, "请先在服务端配置 ADMIN_SECRET")
    if not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(401, "需要管理员身份")


def signature(version: str, expires: int) -> str:
    key = get_settings().admin_secret.get_secret_value()
    if not key:
        raise ValueError("ADMIN_SECRET 未配置")
    return hmac.new(key.encode(), f"{version}:{expires}".encode(), hashlib.sha256).hexdigest()


def source_url(version: str, chunk: str) -> str:
    expires = int(time.time()) + 3600
    return f"{get_settings().public_base_url}/api/sources/{version}?expires={expires}&sig={signature(version, expires)}#chunk-{chunk}"


def check_signature(version: str, expires: int, sig: str) -> None:
    if expires < time.time() or not hmac.compare_digest(signature(version, expires), sig):
        raise HTTPException(403, "引用链接已过期，请重新提问获取链接")
