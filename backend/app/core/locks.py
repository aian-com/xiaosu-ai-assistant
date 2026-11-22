import asyncio
import hashlib
from contextlib import asynccontextmanager
from filelock import FileLock, Timeout
from app.config import get_settings


def lock_for(name: str) -> FileLock:
    folder = get_settings().data_dir / "locks"
    folder.mkdir(parents=True, exist_ok=True)
    return FileLock(folder / (hashlib.sha256(name.encode()).hexdigest() + ".lock"), thread_local=False)


@asynccontextmanager
async def async_lock(name: str, timeout: float = 90):
    lock = lock_for(name)
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            lock.acquire(timeout=0)
            break
        except Timeout:
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError("任务繁忙，请稍后重试") from None
            await asyncio.sleep(0.1)
    try:
        yield
    finally:
        lock.release()
