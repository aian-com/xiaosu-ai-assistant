from functools import lru_cache
from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore", env_ignore_empty=True)
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str = ""
    llm_model: str = ""
    llm_enable_thinking: bool = False
    embedding_model: str = ""
    embedding_api_key: SecretStr = SecretStr("")
    embedding_base_url: str = ""
    database_url: str = "sqlite:///" + (Path(__file__).resolve().parents[2] / "data" / "xiaosu.sqlite3").as_posix()
    admin_secret: SecretStr = SecretStr("")
    public_base_url: str = "http://localhost:8000"
    allowed_models: str = ""
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    log_dir: Path = Path(__file__).resolve().parents[2] / "logs"
    max_upload_mb: int = 20
    max_tool_rounds: int = 5
    request_timeout: int = 90
    retrieval_min_score: float = 0.45
    dingtalk_client_id: str = ""
    dingtalk_card_template_id: str = ""
    dingtalk_client_secret: SecretStr = SecretStr("")
    mock_api_url: str = "http://127.0.0.1:8001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
