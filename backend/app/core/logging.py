import logging
from logging.handlers import RotatingFileHandler
from app.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("xiaosu")
    destination = str((settings.log_dir / "xiaosu.log").resolve())
    if any(isinstance(h, RotatingFileHandler) and h.baseFilename == destination for h in logger.handlers):
        return
    handler = RotatingFileHandler(settings.log_dir / "xiaosu.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger("xiaosu").setLevel(logging.INFO)
    logging.getLogger("xiaosu").addHandler(handler)
    # Do not enable HTTP debug logging: headers and signed URLs contain secrets.
