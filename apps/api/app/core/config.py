"""
Core Settings Configuration
"""

from typing import List, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Data Migration Platform API"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "default_secret_key_change_me_in_production"
    JWT_SECRET_KEY: str = "default_jwt_secret_key_change_me_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    COOKIE_SECURE: bool = False  # Set to True in production (HTTPS)
    COOKIE_SAMESITE: Literal["lax", "none", "strict"] = "lax"
    COOKIE_DOMAIN: str | None = None

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    FRONTEND_URL: str = "http://localhost:3000"

    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres_password@localhost:5432/migration_platform"
    REDIS_URL: str = "redis://redis:6379/0"

    GEMINI_API_KEY: str = ""
    AI_PROVIDER: str = "gemini"
    AI_MODEL_NAME: str = "gemini-1.5-pro"

    MAX_CLOUD_ROWS: int = 500_000
    MAX_CLOUD_SIZE_MB: float = 100.0

    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
