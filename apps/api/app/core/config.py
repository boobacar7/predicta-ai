from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.value_engine.calculator import VALUE_ENGINE_VERSION

_REPO_ROOT = Path(__file__).resolve().parents[4]

DataMode = Literal["mock", "live"]
RepositoryKind = Literal["mock", "sql"]
AppEnv = Literal["development", "test", "staging", "production"]
AnalystNarrator = Literal["deterministic", "llm"]


class Settings(BaseSettings):
    """Runtime configuration. Secrets come from the environment, never from Git."""

    model_config = SettingsConfigDict(
        env_prefix="PREDICTA_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: AppEnv = "development"
    data_mode: DataMode = "mock"
    repository: RepositoryKind = "mock"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://predicta:predicta@localhost:5432/predicta"
    redis_url: str | None = None
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    request_id_header: str = "X-Request-ID"
    mock_now: str = "2026-09-09T18:00:00Z"
    value_formula_version: str = VALUE_ENGINE_VERSION
    analyst_narrator: AnalystNarrator = "deterministic"
    analyst_llm_model: str = "mock-explainer-0.1"
    analyst_prompt_version: str = "analyst-prompt-0.1"
    analyst_llm_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    football_model_version: str = "football-elo-v1-candidate"
    football_registry_dir: Path = _REPO_ROOT / "workers" / "ml" / "var" / "registry"
    football_dataset_path: Path = _REPO_ROOT / "workers" / "ingestion" / "var" / "football-1x2-history.parquet"
    football_prematch_dataset_path: Path = (
        _REPO_ROOT / "workers" / "ingestion" / "var" / "football-1x2-prematch.parquet"
    )
    football_raw_archive_dir: Path = _REPO_ROOT / "workers" / "ingestion" / "var" / "raw"
    ai_picks_candidate_match_ids: tuple[str, ...] = ("mth_football-sportmonks-19719892",)
    ai_picks_minimum_edge: Decimal = Decimal("0")
    ai_picks_minimum_ev: Decimal = Decimal("0")
    ai_picks_minimum_model_probability: Decimal = Decimal("0")
    ai_picks_maximum_odds_age_seconds: int = Field(default=86400, gt=0)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("redis_url", mode="before")
    @classmethod
    def empty_redis(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_deployed(self) -> bool:
        return self.env in ("staging", "production")

    def resolved_data_mode(self) -> DataMode:
        """Mock repositories cannot be advertised as live data."""
        if self.repository == "mock":
            return "mock"
        return self.data_mode

    @model_validator(mode="after")
    def refuse_mock_in_deployed_envs(self) -> Self:
        if not self.is_deployed:
            return self
        if self.repository == "mock":
            raise ValueError(f"Mock repositories are forbidden when PREDICTA_API_ENV={self.env}.")
        if self.data_mode == "mock":
            raise ValueError(f"data_mode=mock is forbidden when PREDICTA_API_ENV={self.env}.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
