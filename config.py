import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    master_key: str
    database_url: str = "sqlite+aiosqlite:///./ai_api_manager.db"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# 确保数据库目录存在
if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    db_path = db_path.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
