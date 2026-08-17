"""Central application configuration.

Every environment value is read from environment variables (or a .env file)
so the platform can be deployed to any environment without code changes.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Federated AI Platform"
    ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "change-me-in-production-9f8e7d6c5b4a39281706"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str = "sqlite:///./federated_platform.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672//"

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:4173,http://localhost:3000"
    ENABLE_HEAVY_DEPS: bool = False

    # Celery / worker
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Security aggregation
    MASK_KEY_BYTES: int = 32
    AES_KEY_BYTES: int = 32
    RSA_KEY_BITS: int = 2048
    MAX_PRIVACY_BUDGET: float = 8.0

    # Rate limiting (simple token bucket)
    RATE_LIMIT_PER_MINUTE: int = 300

    # Feature flags default
    DEFAULT_FEATURE_FLAGS: str = "secure_aggregation=true;ai_assistant=true;federated_lab=true;reports=true"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def feature_flag_map(self) -> dict:
        flags: dict = {}
        for part in self.DEFAULT_FEATURE_FLAGS.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                flags[k.strip()] = v.strip().lower() == "true"
        return flags

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
