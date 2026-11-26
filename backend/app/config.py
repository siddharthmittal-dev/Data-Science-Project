from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from typing import Literal

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://terra:terra_local_only@localhost:5433/terra"
    test_database_url: str = "postgresql+psycopg://terra:terra_local_only@localhost:5433/terra_test"
    cors_origins: str = "http://localhost:3000"
    cookie_secure: bool = False
    signup_enabled: bool = False
    clinic_timezone: str = "Asia/Kolkata"
    assistant_provider: Literal["local", "cloudflare"] = "local"
    cloudflare_account_id: str = ""
    cloudflare_api_token: SecretStr = SecretStr("")
    cloudflare_model: str = "@cf/meta/llama-3.1-8b-instruct"
    openai_api_key: SecretStr = SecretStr("")
    openai_rag_model: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    rag_index_path: Path = BACKEND_DIR / "rag-local" / "index.json"
    rag_redis_url: SecretStr = SecretStr("")
    rag_ocr_executable: str = "tesseract"
    rag_ocr_language: str = "eng"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
