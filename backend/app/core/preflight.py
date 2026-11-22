"""Prepare an automatically created SQLite database for local development."""
from sqlalchemy import text
from app.config import get_settings
from app.core.db import session


def main() -> None:
    settings = get_settings()
    if not settings.admin_secret.get_secret_value():
        raise SystemExit("请在 .env 中填写 ADMIN_SECRET（后台登录口令）。")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with session() as db:
        db.execute(text("SELECT 1"))
    print("本地 SQLite 已准备，无需安装或手动创建数据库。")


if __name__ == "__main__":
    main()
