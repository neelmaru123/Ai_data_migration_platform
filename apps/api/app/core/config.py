"""
Core Settings Configuration
"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Data Migration Platform API"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "default_secret_key_change_me_in_production"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres_password@postgres:5432/migration_platform"
    REDIS_URL: str = "redis://redis:6379/0"

    GEMINI_API_KEY: str = ""
    AI_PROVIDER: str = "gemini"
    AI_MODEL_NAME: str = "gemini-1.5-pro"

    MAX_CLOUD_ROWS: int = 500_000
    MAX_CLOUD_SIZE_MB: float = 100.0

    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
