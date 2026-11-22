from functools import lru_cache
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from app.config import get_settings


@lru_cache
def factory() -> sessionmaker[Session]:
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "sqlite":
        raise ValueError("当前版本使用 SQLite，请清空旧 DATABASE_URL，系统会自动创建本地数据库")
    if url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    return sessionmaker(engine, expire_on_commit=False)


def session() -> Session:
    return factory()()


@contextmanager
def transaction():
    """Acquire SQLite's writer reservation before read-modify-write operations."""
    with session() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
