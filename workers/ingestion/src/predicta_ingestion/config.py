import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DataMode = Literal["mock", "live"]
AppEnv = Literal["development", "test", "staging", "production"]

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = PACKAGE_ROOT / "fixtures" / "mock"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PREDICTA_INGESTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: AppEnv = "development"
    data_mode: DataMode = "mock"
    enable_live: bool = False
    mock_now: str = "2026-09-09T18:00:00Z"
    database_url: str = "postgresql+psycopg://predicta:predicta@localhost:5432/predicta"
    raw_store_path: Path = Field(default=Path("./var/raw"))
    max_payload_bytes: int = 2_000_000
    http_timeout_seconds: float = 20.0
    http_max_retries: int = 3
    sportmonks_base_url: str = "https://api.sportmonks.com/v3/football"
    api_football_key: str = ""
    sportmonks_key: str = ""
    the_odds_api_key: str = ""
    balldontlie_key: str = ""
    api_tennis_key: str = ""

    @field_validator("api_football_key", "sportmonks_key", "the_odds_api_key", "balldontlie_key", "api_tennis_key")
    @classmethod
    def empty_keys_ok(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def accept_unprefixed_sportmonks_token(self) -> "Settings":
        if self.sportmonks_key:
            return self
        unprefixed = (os.environ.get("SPORTMONKS_API_TOKEN") or "").strip()
        if unprefixed:
            self.sportmonks_key = unprefixed
        return self

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    def resolved_data_mode(self) -> DataMode:
        if not self.enable_live:
            return "mock"
        return self.data_mode


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and settings.data_mode == "mock":
        raise RuntimeError("data_mode=mock is forbidden when PREDICTA_INGESTION_ENV=production.")
    if settings.enable_live and settings.data_mode == "mock":
        raise RuntimeError("Live ingestion cannot run with data_mode=mock.")
    return settings
