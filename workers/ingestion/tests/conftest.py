from datetime import UTC, datetime
from pathlib import Path

import pytest

from predicta_ingestion.clock import Clock, parse_rfc3339
from predicta_ingestion.config import Settings, get_settings
from predicta_ingestion.identity.resolver import IdentityResolver
from predicta_ingestion.persistence.memory import MemoryCanonicalSink
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.providers.mock import (
    MockBasketballProvider,
    MockFootballProvider,
    MockOddsProvider,
    MockTennisProvider,
)
from predicta_ingestion.raw.store import FilesystemRawStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "mock"
SPORTMONKS_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "sportmonks"
NOW = parse_rfc3339("2026-09-09T18:00:00Z")
TEST_SPORTMONKS_TOKEN = "sm_test_secret_do_not_log"


@pytest.fixture(autouse=True)
def isolate_live_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPORTMONKS_API_TOKEN", raising=False)
    monkeypatch.delenv("PREDICTA_INGESTION_SPORTMONKS_KEY", raising=False)
    monkeypatch.delenv("PREDICTA_INGESTION_ENABLE_LIVE", raising=False)
    monkeypatch.delenv("PREDICTA_INGESTION_DATA_MODE", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def clock() -> Clock:
    return Clock(NOW)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        data_mode="mock",
        enable_live=False,
        mock_now="2026-09-09T18:00:00Z",
        sportmonks_key="",
    )


@pytest.fixture
def pipeline(clock: Clock, settings: Settings, tmp_path: Path) -> IngestionPipeline:
    return IngestionPipeline(
        settings=settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=MemoryCanonicalSink(),
        resolver=IdentityResolver(clock),
    )


@pytest.fixture
def football_provider(clock: Clock) -> MockFootballProvider:
    return MockFootballProvider(clock, FIXTURES)


@pytest.fixture
def basketball_provider(clock: Clock) -> MockBasketballProvider:
    return MockBasketballProvider(clock, FIXTURES)


@pytest.fixture
def tennis_provider(clock: Clock) -> MockTennisProvider:
    return MockTennisProvider(clock, FIXTURES)


@pytest.fixture
def odds_provider(clock: Clock) -> MockOddsProvider:
    return MockOddsProvider(clock, FIXTURES)


@pytest.fixture
def live_settings() -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        data_mode="live",
        enable_live=True,
        mock_now="2026-09-09T18:00:00Z",
        sportmonks_key=TEST_SPORTMONKS_TOKEN,
    )


@pytest.fixture
def live_pipeline(clock: Clock, live_settings: Settings, tmp_path: Path) -> IngestionPipeline:
    return IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=MemoryCanonicalSink(),
        resolver=IdentityResolver(clock),
    )


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)
