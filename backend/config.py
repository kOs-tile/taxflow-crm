"""
TaxFlow CRM — Application Configuration
Uses Pydantic Settings for environment-based configuration with .env support.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "TaxFlow CRM"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    # ── Security ─────────────────────────────────────────────────────────────
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 hours for staff

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "taxflow.db"

    # ── AI Assistant ─────────────────────────────────────────────────────────
    ai_provider: Literal["openai", "deepseek"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    ai_context_privacy: Literal["minimum", "identity"] = "minimum"

    # ── Email (optional) ─────────────────────────────────────────────────────
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@taxflow.app"

    # ── Default Admin ─────────────────────────────────────────────────────────
    admin_email: str = "admin@taxflow.app"
    admin_password: str = Field(min_length=12)

    @property
    def ai_api_key(self) -> str:
        if self.ai_provider == "deepseek":
            return self.deepseek_api_key
        return self.openai_api_key

    @property
    def ai_model(self) -> str:
        if self.ai_provider == "deepseek":
            return self.deepseek_model
        return self.openai_model

    @property
    def ai_base_url(self) -> str | None:
        if self.ai_provider == "deepseek":
            return "https://api.deepseek.com/v1"
        return None  # OpenAI default


@lru_cache()
def get_settings() -> Settings:
    return Settings()
