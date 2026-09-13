from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.clock import Clock
from app.odds.exceptions import (
    IncompleteOddsMarketError,
    OddsTemporalLeakageError,
    OddsUnavailableError,
)
from app.odds.providers import LiveOddsProvider, MockOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.types import Football1x2Selection, OddsSelection, OddsSnapshot
from app.predictions.exceptions import PitFeaturesUnavailableError
from app.schemas import FootballModelPrediction
from app.value_engine.exceptions import InvalidPredictionError
from app.value_engine.service import FootballValueService
from fastapi.testclient import TestClient
from tests.conftest import make_app
from tests.live_assets import requires_live_assets

MATCH_ID = "match_value_test"
CUTOFF = datetime(2026, 7, 7, 16, tzinfo=UTC)
COLLECTED = datetime(2026, 7, 7, 14, 59, tzinfo=UTC)
AVAILABLE = datetime(2026, 7, 7, 15, tzinfo=UTC)


class StaticPredictionService:
    def predict(self, match_id: str, cutoff_at: datetime | None) -> FootballModelPrediction:
        return FootballModelPrediction(
            match_id=match_id,
            home_probability=0.60,
            draw_probability=0.20,
            away_probability=0.20,
            model_version="football-elo-v1-candidate",
            dataset_version="football-1x2-history-0.3",
            feature_schema_version="football-1x2-features-0.3",
            model_status="candidate",
            cutoff_at=cutoff_at or CUTOFF,
            cutoff_policy="pre_kickoff",
            generated_at=CUTOFF,
        )


class MissingPredictionService:
    def predict(self, match_id: str, cutoff_at: datetime | None) -> FootballModelPrediction:
        raise PitFeaturesUnavailableError("Prediction is absent.")


def snapshot(
    *,
    available_at: datetime = AVAILABLE,
    selections: tuple[OddsSelection, ...] | None = None,
    snapshot_id: str = "odds_snapshot_1",
) -> OddsSnapshot:
    return OddsSnapshot(
        id=snapshot_id,
        provider_id=snapshot_id,
        match_id=MATCH_ID,
        bookmaker="Fictional Sportsbook",
        market="1X2",
        selections=selections
        or (
            OddsSelection(Football1x2Selection.HOME, Decimal("2.00")),
            OddsSelection(Football1x2Selection.DRAW, Decimal("4.00")),
            OddsSelection(Football1x2Selection.AWAY, Decimal("5.00")),
        ),
        collected_at=COLLECTED,
        available_at=available_at,
        source="test-mock-odds",
        data_mode="mock",
    )


def service_for(*snapshots: OddsSnapshot) -> FootballValueService:
    provider = MockOddsProvider(tuple(snapshots))
    provider.source = "test-mock-odds"
    odds = OddsService(provider=provider, repository=InMemoryOddsRepository())
    return FootballValueService(
        clock=Clock(CUTOFF),
        predictions=StaticPredictionService(),
        odds=odds,
    )


def test_required_1x2_math_and_metadata() -> None:
    result = service_for(snapshot()).evaluate(MATCH_ID, CUTOFF)
    assert result.market_probabilities.home.implied_probability == pytest.approx(0.50)
    assert result.value.home.edge == pytest.approx(0.10)
    assert result.value.home.ev == pytest.approx(0.20)
    no_vig_total = (
        result.market_probabilities.home.no_vig_probability
        + result.market_probabilities.draw.no_vig_probability
        + result.market_probabilities.away.no_vig_probability
    )
    assert result.market_probabilities.overround == pytest.approx(0.95)
    assert no_vig_total == pytest.approx(1.0)
    assert result.metadata.value_engine_version == "value-engine-0.1"
    assert result.metadata.model_version == "football-elo-v1-candidate"
    assert result.metadata.dataset_version == "football-1x2-history-0.3"
    assert result.metadata.feature_schema_version == "football-1x2-features-0.3"
    assert result.metadata.model_status == "candidate"
    assert result.metadata.odds_source == "test-mock-odds"
    assert result.metadata.data_mode == "mock"
    assert result.metadata.cutoff_at == CUTOFF


@pytest.mark.parametrize(
    "odds",
    [None, Decimal("1"), Decimal("0"), Decimal("-2"), Decimal("NaN")],
)
def test_invalid_or_missing_odds_are_refused(odds: object) -> None:
    with pytest.raises(ValueError, match="greater than 1"):
        OddsSelection(Football1x2Selection.HOME, odds)  # type: ignore[arg-type]


def test_incoherent_or_naive_timestamps_are_refused() -> None:
    with pytest.raises(ValueError, match="timezone"):
        snapshot(available_at=datetime(2026, 7, 7, 15))
    with pytest.raises(ValueError, match="greater than or equal"):
        snapshot(available_at=datetime(2026, 7, 7, 14, 58, tzinfo=UTC))


def test_incomplete_market_is_refused() -> None:
    incomplete = snapshot(
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal("2")),
            OddsSelection(Football1x2Selection.DRAW, Decimal("4")),
        )
    )
    with pytest.raises(IncompleteOddsMarketError):
        service_for(incomplete).evaluate(MATCH_ID, CUTOFF)


def test_post_cutoff_odds_are_refused_as_temporal_leakage() -> None:
    future = snapshot(
        available_at=datetime(2026, 7, 7, 16, 0, 1, tzinfo=UTC)
    )
    with pytest.raises(OddsTemporalLeakageError):
        service_for(future).evaluate(MATCH_ID, CUTOFF)


def test_latest_eligible_snapshot_is_used_without_overwriting_history() -> None:
    repository = InMemoryOddsRepository()
    early = snapshot(snapshot_id="early")
    late = snapshot(
        snapshot_id="late",
        available_at=datetime(2026, 7, 7, 15, 30, tzinfo=UTC),
    )
    provider = MockOddsProvider((late, early))
    provider.source = "test-mock-odds"
    odds = OddsService(provider=provider, repository=repository)
    chosen = odds.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=CUTOFF)
    assert chosen.id == "late"
    assert [item.id for item in repository.history(MATCH_ID, "1X2")] == ["early", "late"]
    odds.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=CUTOFF)
    assert len(repository.history(MATCH_ID, "1X2")) == 2


def test_repository_refuses_silent_snapshot_overwrite() -> None:
    repository = InMemoryOddsRepository()
    original = snapshot()
    repository.append(original)
    changed = OddsSnapshot(
        id=original.id,
        provider_id=original.provider_id,
        match_id=original.match_id,
        bookmaker=original.bookmaker,
        market=original.market,
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal("2.10")),
            *original.selections[1:],
        ),
        collected_at=original.collected_at,
        available_at=original.available_at,
        source=original.source,
        data_mode=original.data_mode,
    )
    with pytest.raises(ValueError, match="immutable"):
        repository.append(changed)


def test_prediction_absence_is_propagated() -> None:
    value = FootballValueService(
        clock=Clock(CUTOFF),
        predictions=MissingPredictionService(),
        odds=OddsService(
            provider=MockOddsProvider(()),
            repository=InMemoryOddsRepository(),
        ),
    )
    with pytest.raises(PitFeaturesUnavailableError, match="absent"):
        value.evaluate(MATCH_ID, CUTOFF)


def test_invalid_prediction_is_refused() -> None:
    invalid = StaticPredictionService()
    invalid.predict = lambda match_id, cutoff_at: FootballModelPrediction.model_construct(  # type: ignore[method-assign]
        match_id=match_id,
        sport="football",
        market="1X2",
        home_probability=0.8,
        draw_probability=0.2,
        away_probability=0.2,
        model_version="football-elo-v1-candidate",
        dataset_version="football-1x2-history-0.3",
        feature_schema_version="football-1x2-features-0.3",
        model_status="candidate",
        cutoff_at=CUTOFF,
        cutoff_policy="pre_kickoff",
        generated_at=CUTOFF,
    )
    value = FootballValueService(
        clock=Clock(CUTOFF),
        predictions=invalid,
        odds=OddsService(
            provider=MockOddsProvider((snapshot(),)),
            repository=InMemoryOddsRepository(),
        ),
    )
    with pytest.raises(InvalidPredictionError, match="sum to 1"):
        value.evaluate(MATCH_ID, CUTOFF)


def test_reproducibility() -> None:
    value = service_for(snapshot())
    first = value.evaluate(MATCH_ID, CUTOFF)
    second = value.evaluate(MATCH_ID, CUTOFF)
    assert first == second


def test_mock_and_live_provider_modes_are_explicit() -> None:
    assert MockOddsProvider().data_mode == "mock"
    live = LiveOddsProvider()
    assert live.data_mode == "live"
    with pytest.raises(OddsUnavailableError, match="never synthesized"):
        live.fetch(MATCH_ID, "1X2")


@requires_live_assets
def test_value_api_rfc9457_and_request_id_for_missing_odds() -> None:
    app = make_app()
    container = app.state.container
    container.football_odds = OddsService(
        provider=MockOddsProvider(()),
        repository=InMemoryOddsRepository(),
    )
    client = TestClient(app)
    response = client.get(
        "/api/v1/football/value/mth_football-sportmonks-19719892",
        headers={"X-Request-ID": "req_value_missing_odds"},
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["X-Request-ID"] == "req_value_missing_odds"
    assert response.json()["request_id"] == "req_value_missing_odds"
    assert response.json()["type"] == "/problems/odds-unavailable"


@requires_live_assets
def test_value_api_success_metadata_and_request_id() -> None:
    client = TestClient(make_app())
    response = client.get(
        "/api/v1/football/value/mth_football-sportmonks-19719892",
        headers={"X-Request-ID": "req_value_success"},
    )
    assert response.status_code == 200
    body = response.json()
    assert response.headers["X-Request-ID"] == "req_value_success"
    assert body["request_id"] == "req_value_success"
    assert body["data_mode"] == "mock"
    metadata = body["data"]["metadata"]
    assert metadata["value_engine_version"] == "value-engine-0.1"
    assert metadata["model_version"] == "football-elo-v1-candidate"
    assert metadata["model_status"] == "candidate"
    assert metadata["odds_source"] == "predicta-mock-odds-v0.1"
    assert metadata["data_mode"] == "mock"
