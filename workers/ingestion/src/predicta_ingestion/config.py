import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DataMode = Literal["mock", "live"]
AppEnv = Literal["development", "test", "staging", "production"]

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = PACKAGE_ROOT / "fixtures" / "mock"
SKIP_DOTENV_ENV = "PREDICTA_INGESTION_SKIP_DOTENV"
ENV_FILE_ENV = "PREDICTA_INGESTION_ENV_FILE"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PREDICTA_INGESTION_",
        env_file=None,
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
    api_football_key: str = Field(default="", repr=False)
    sportmonks_key: str = Field(default="", repr=False)
    the_odds_api_key: str = Field(default="", repr=False)
    balldontlie_key: str = Field(default="", repr=False)
    api_tennis_key: str = Field(default="", repr=False)

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


def local_env_candidates(*, env_file: Path | None = None) -> list[Path]:
    """Resolve .env locations from the package/CLI, never from a hardcoded machine path."""
    if env_file is not None:
        return [env_file]
    explicit = (os.environ.get(ENV_FILE_ENV) or "").strip()
    if explicit:
        return [Path(explicit)]
    cwd_env = Path.cwd() / ".env"
    package_env = PACKAGE_ROOT / ".env"
    if cwd_env.resolve() == package_env.resolve():
        return [package_env]
    return [package_env, cwd_env]


def load_local_env(*, env_file: Path | None = None) -> tuple[Path, ...]:
    """Load a local .env into os.environ without overriding explicit process variables.

    `SPORTMONKS_API_TOKEN` is unprefixed, so pydantic-settings will not map it unless
    it is present in the process environment. dotenv fills that gap. Existing env vars
    always win (`override=False`).
    """
    if env_file is None and _skip_dotenv():
        return ()
    loaded: list[Path] = []
    seen: set[Path] = set()
    for candidate in local_env_candidates(env_file=env_file):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        load_dotenv(resolved, override=False)
        loaded.append(resolved)
    return tuple(loaded)


def _skip_dotenv() -> bool:
    return (os.environ.get(SKIP_DOTENV_ENV) or "").strip().lower() in {"1", "true", "yes"}


@lru_cache
def get_settings() -> Settings:
    load_local_env()
    settings = Settings()
    if settings.is_production and settings.data_mode == "mock":
        raise RuntimeError("data_mode=mock is forbidden when PREDICTA_INGESTION_ENV=production.")
    if settings.enable_live and settings.data_mode == "mock":
        raise RuntimeError("Live ingestion cannot run with data_mode=mock.")
    return settings
