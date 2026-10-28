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
    datasets_cron: str = "0 23 * * 0"  # weekly (Sunday 23:00 UTC = Monday 07:00 Asia/Taipei)
    log_level: str = "INFO"
    log_json: bool = True
    fred_series: str = "DGS10"
    fred_start: str = "2015-01-01"
    # TWSE: months of daily history fetched per stock (>=13 needed for a 52-week window)
    twse_history_months: int = 13
    # Seconds between www.twse.com.tw requests (TWSE blocks bursts; keep >= 3)
    twse_min_interval_s: float = 3.0
    # Optional: Alpha Vantage key for US equity prices (free tier: 25 req/day). Unset -> UNAVAILABLE.
    alphavantage_api_key: str = ""
    # Optional: Tiingo key for US equity/ETF daily prices (free Starter plan). Unset -> UNAVAILABLE.
    tiingo_api_key: str = ""
    # First date requested from price APIs (>= 10 years of history for drawdown / relative performance)
    us_price_start: str = "2015-01-01"
    # SEC filing-level XBRL (dimensional facts): number of recent 10-Q/10-K filings to parse
    sec_filings_limit: int = 12
    # Risk engine: refuse to show a precise overall score below this weighted coverage
    risk_min_coverage: float | None = None  # None -> value in registry/risk.yaml

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
