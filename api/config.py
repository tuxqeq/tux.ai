from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://tuxai:tuxai@localhost:5432/tuxai"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Security
    JWT_SECRET: str = "CHANGE_ME_in_production_32_chars!!"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_HOURS: int = 8
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # AES master key — used to encrypt stored dataset AES keys at rest.
    # Must be exactly 32 bytes (ASCII or hex-encoded).
    MASTER_KEY: str = "CHANGE_ME_MASTER_KEY_32_bytes!!!"

    # Ollama
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "tux-ai-chat"

    # PII model path (relative to project root).
    # Falls back through pii_model_v2 → pii_model if the primary is missing.
    MODEL_PATH: str = "models/pii_model_v2"

    # gRPC
    GRPC_PORT: int = 50051

    # Rate limiting
    CHAT_RATE_LIMIT: str = "30/minute"
    LOGIN_RATE_LIMIT: str = "10/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
