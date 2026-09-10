from datetime import UTC, datetime
from pathlib import Path

import pytest

from predicta_ingestion.clock import Clock, parse_rfc3339
from predicta_ingestion.config import Settings
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
NOW = parse_rfc3339("2026-09-09T18:00:00Z")


@pytest.fixture
def clock() -> Clock:
    return Clock(NOW)


@pytest.fixture
def settings() -> Settings:
    return Settings(env="test", data_mode="mock", enable_live=False, mock_now="2026-09-09T18:00:00Z")


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


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)
