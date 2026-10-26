"""Application settings, loaded from environment variables (or a .env file).

No secrets are hardcoded. See ../../.env.example for every variable.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "sqlite:///./data/aibm.db"
    sec_user_agent: str = Field(default="", description="'<app> <contact email>' required by SEC")
    sec_max_rps: float = 5.0
    http_timeout_s: float = 30.0
    cors_origins: str = "http://localhost:3000"
    scheduler_enabled: bool = False
    scheduler_cron: str = "30 22 * * *"
    log_level: str = "INFO"
    log_json: bool = True
    fred_series: str = "DGS10"
    fred_start: str = "2015-01-01"

    @field_validator("sec_max_rps")
    @classmethod
    def _cap_rps(cls, v: float) -> float:
        # SEC fair-access policy: max 10 requests/second. Never exceed it.
        return max(0.1, min(float(v), 10.0))

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
