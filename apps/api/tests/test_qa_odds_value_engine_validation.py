from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import product
from pathlib import Path

import pytest
from app.core.clock import Clock, parse_rfc3339, to_rfc3339
from app.odds.exceptions import (
    IncompleteOddsMarketError,
    OddsTemporalLeakageError,
    OddsUnavailableError,
)
from app.odds.providers import MockOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.types import Football1x2Selection as Selection
from app.odds.types import OddsSelection, OddsSnapshot
from app.predictions.exceptions import PitFeaturesUnavailableError
from app.schemas import FootballModelPrediction
from app.value_engine import calculator
from app.value_engine.exceptions import InvalidPredictionError
from app.value_engine.service import FootballValueService, PredictionService
from fastapi.testclient import TestClient
from tests.conftest import make_app

MATCH_ID = "qa_match"
CUTOFF = datetime(2026, 7, 7, 16, tzinfo=UTC)
SOURCE = "qa-mock-odds"
COMPLETE_ODDS = {
    Selection.HOME: Decimal("2.00"),
    Selection.DRAW: Decimal("4.00"),
    Selection.AWAY: Decimal("5.00"),
}
HISTORICAL_MATCH_IDS = (
    "mth_football-sportmonks-19722183",
    "mth_football-sportmonks-19715615",
    "mth_football-sportmonks-19732709",
)
REPO_ROOT = Path(__file__).resolve().parents[3]


class StaticPredictionService:
    def __init__(
        self,
        *,
        home: float = 0.60,
        draw: float = 0.20,
        away: float = 0.20,
    ) -> None:
        self.home = home
        self.draw = draw
        self.away = away

    def predict(self, match_id: str, cutoff_at: datetime | None) -> FootballModelPrediction:
        return FootballModelPrediction(
            match_id=match_id,
            home_probability=self.home,
            draw_probability=self.draw,
            away_probability=self.away,
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
        raise PitFeaturesUnavailableError("QA prediction unavailable.")


def make_snapshot(
    *,
    match_id: str = MATCH_ID,
    snapshot_id: str = "qa_odds_1",
    available_at: datetime = CUTOFF - timedelta(minutes=10),
    collected_at: datetime | None = None,
    odds: dict[Selection, Decimal] | None = None,
) -> OddsSnapshot:
    resolved_odds = COMPLETE_ODDS if odds is None else odds
    resolved_collected = collected_at or available_at - timedelta(seconds=1)
    return OddsSnapshot(
        id=snapshot_id,
        provider_id=snapshot_id,
        match_id=match_id,
        bookmaker="QA Fictional Bookmaker",
        market="1X2",
        selections=tuple(
            OddsSelection(selection, decimal_odds)
            for selection, decimal_odds in resolved_odds.items()
        ),
        collected_at=resolved_collected,
        available_at=available_at,
        source=SOURCE,
        data_mode="mock",
    )


def make_value_service(
    *snapshots: OddsSnapshot,
    predictions: PredictionService | None = None,
) -> FootballValueService:
    provider = MockOddsProvider(tuple(snapshots))
    provider.source = SOURCE
    return FootballValueService(
        clock=Clock(CUTOFF),
        predictions=predictions or StaticPredictionService(),
        odds=OddsService(
            provider=provider,
            repository=InMemoryOddsRepository(),
        ),
    )


def test_implied_probability_reference_values_and_invalid_inputs() -> None:
    assert calculator.implied_probability(Decimal("2.00")) == Decimal("0.5")
    assert calculator.implied_probability(Decimal("4.00")) == Decimal("0.25")
    assert calculator.implied_probability(Decimal("5.00")) == Decimal("0.2")
    for invalid in (None, Decimal("1"), Decimal("0"), Decimal("-2"), "not-a-number"):
        with pytest.raises(ValueError, match="greater than 1"):
            calculator.implied_probability(invalid)  # type: ignore[arg-type]


def test_documented_reference_market_no_vig_is_correct() -> None:
    normalized, overround = calculator.no_vig_probabilities(COMPLETE_ODDS)
    assert overround == Decimal("0.95")
    assert normalized[Selection.HOME] == Decimal("0.5") / Decimal("0.95")
    assert normalized[Selection.DRAW] == Decimal("0.25") / Decimal("0.95")
    assert normalized[Selection.AWAY] == Decimal("0.2") / Decimal("0.95")
    assert sum(normalized.values(), Decimal(0)) == Decimal(1)


@pytest.mark.parametrize(
    "prices",
    [
        ("2.00", "2.00", "2.00"),
        ("1.90", "3.20", "4.20"),
        ("2.10", "3.30", "3.70"),
        ("2.00", "4.00", "5.00"),
        ("1.50", "3.50", "6.00"),
        ("1.61", "4.00", "5.50"),
        ("2.37", "3.20", "3.10"),
        ("1.80", "3.60", "4.50"),
        ("1.73", "3.75", "5.00"),
        ("3.10", "3.10", "3.10"),
    ],
)
def test_valid_markets_must_not_fail_no_vig_normalization(
    prices: tuple[str, str, str],
) -> None:
    odds = {
        selection: Decimal(price)
        for selection, price in zip(Selection, prices, strict=True)
    }
    normalized, overround = calculator.no_vig_probabilities(odds)
    assert overround > 0
    assert sum(normalized.values(), Decimal(0)) == Decimal(1)
    for value in normalized.values():
        assert Decimal(0) < value < Decimal(1)


def test_no_vig_grid_does_not_reject_valid_markets() -> None:
    prices = [Decimal(str(value)) / Decimal(10) for value in range(15, 51)]
    accepted = 0
    for home, draw, away in product(prices, repeat=3):
        normalized, _ = calculator.no_vig_probabilities(
            {
                Selection.HOME: home,
                Selection.DRAW: draw,
                Selection.AWAY: away,
            }
        )
        assert sum(normalized.values(), Decimal(0)) == Decimal(1)
        accepted += 1
    assert accepted == 46_656


@pytest.mark.parametrize(
    "invalid_odds",
    [None, Decimal("1"), Decimal("0"), Decimal("-2"), "not-a-number"],
)
def test_no_vig_refuses_invalid_or_non_numeric_odds(invalid_odds: object) -> None:
    odds = {
        Selection.HOME: Decimal("2.00"),
        Selection.DRAW: Decimal("4.00"),
        Selection.AWAY: invalid_odds,
    }
    with pytest.raises(ValueError, match="greater than 1"):
        calculator.no_vig_probabilities(odds)  # type: ignore[arg-type]


def test_no_vig_refuses_missing_selections() -> None:
    with pytest.raises(ValueError, match="complete football 1X2"):
        calculator.no_vig_probabilities(
            {
                Selection.HOME: Decimal("2.00"),
                Selection.DRAW: Decimal("4.00"),
            }
        )


def test_edge_and_ev_cover_positive_zero_negative_and_monotonicity() -> None:
    assert calculator.edge("0.60", "0.50") == Decimal("0.10")
    assert calculator.edge("0.50", "0.50") == Decimal("0.00")
    assert calculator.edge("0.40", "0.50") == Decimal("-0.10")
    assert calculator.expected_value("0.60", "2.00") == Decimal("0.20")
    assert calculator.expected_value("0.50", "2.00") == Decimal("0.00")
    assert calculator.expected_value("0.40", "2.00") == Decimal("-0.20")
    assert calculator.expected_value("0.60", "2.20") > calculator.expected_value("0.60", "2.00")
    assert calculator.expected_value("0.70", "2.00") > calculator.expected_value("0.60", "2.00")
    assert calculator.expected_value("0.40", "2.50") == Decimal("0.000")


@pytest.mark.parametrize(
    "selections",
    [
        {Selection.HOME: Decimal("2")},
        {Selection.HOME: Decimal("2"), Selection.DRAW: Decimal("4")},
        {Selection.HOME: Decimal("2"), Selection.AWAY: Decimal("5")},
        {Selection.DRAW: Decimal("4"), Selection.AWAY: Decimal("5")},
    ],
)
def test_every_incomplete_1x2_market_is_refused(
    selections: dict[Selection, Decimal],
) -> None:
    value = make_value_service(make_snapshot(odds=selections))
    with pytest.raises(IncompleteOddsMarketError):
        value.evaluate(MATCH_ID, CUTOFF)


def test_pit_before_equal_and_after_cutoff() -> None:
    before = make_value_service(
        make_snapshot(available_at=CUTOFF - timedelta(microseconds=1))
    ).evaluate(MATCH_ID, CUTOFF)
    assert before.odds.available_at < CUTOFF

    at_cutoff = make_value_service(
        make_snapshot(
            available_at=CUTOFF,
            collected_at=CUTOFF,
        )
    ).evaluate(MATCH_ID, CUTOFF)
    assert at_cutoff.odds.available_at == CUTOFF

    with pytest.raises(OddsTemporalLeakageError):
        make_value_service(
            make_snapshot(available_at=CUTOFF + timedelta(microseconds=1))
        ).evaluate(MATCH_ID, CUTOFF)


def test_anti_leakage_refuses_post_cutoff_away_then_accepts_complete_pre_cutoff() -> None:
    kickoff = CUTOFF
    home_draw_pre = make_snapshot(
        snapshot_id="qa_pre_home_draw",
        available_at=kickoff - timedelta(minutes=10),
        odds={
            Selection.HOME: Decimal("2"),
            Selection.DRAW: Decimal("4"),
        },
    )
    away_post = make_snapshot(
        snapshot_id="qa_post_away",
        available_at=kickoff + timedelta(minutes=5),
        odds={Selection.AWAY: Decimal("5")},
    )
    with pytest.raises(IncompleteOddsMarketError):
        make_value_service(home_draw_pre, away_post).evaluate(MATCH_ID, kickoff)

    complete_pre = make_snapshot(
        snapshot_id="qa_complete_pre",
        available_at=kickoff - timedelta(minutes=10),
    )
    accepted = make_value_service(complete_pre).evaluate(MATCH_ID, kickoff)
    assert accepted.odds.available_at == kickoff - timedelta(minutes=10)
    assert accepted.odds.available_at <= kickoff


@pytest.mark.parametrize("delta", [timedelta(minutes=1), timedelta(seconds=1), timedelta(microseconds=1)])
def test_anti_leakage_boundary_variations_around_cutoff(delta: timedelta) -> None:
    accepted = make_value_service(make_snapshot(available_at=CUTOFF - delta)).evaluate(
        MATCH_ID,
        CUTOFF,
    )
    assert accepted.odds.available_at <= CUTOFF

    with pytest.raises(OddsTemporalLeakageError):
        make_value_service(make_snapshot(available_at=CUTOFF + delta)).evaluate(
            MATCH_ID,
            CUTOFF,
        )


def test_mixed_selection_availability_refuses_then_complete_snapshot_accepts() -> None:
    pre_cutoff_partial = make_snapshot(
        snapshot_id="qa_pre_partial",
        odds={
            Selection.HOME: Decimal("2"),
            Selection.DRAW: Decimal("4"),
        },
    )
    post_cutoff_away = make_snapshot(
        snapshot_id="qa_post_away",
        available_at=CUTOFF + timedelta(minutes=5),
        odds={Selection.AWAY: Decimal("5")},
    )
    with pytest.raises(IncompleteOddsMarketError):
        make_value_service(pre_cutoff_partial, post_cutoff_away).evaluate(
            MATCH_ID,
            CUTOFF,
        )

    complete_pre_cutoff = make_snapshot(snapshot_id="qa_complete_pre")
    accepted = make_value_service(complete_pre_cutoff).evaluate(MATCH_ID, CUTOFF)
    assert accepted.odds.available_at == CUTOFF - timedelta(minutes=10)


def test_snapshot_history_is_append_only_and_latest_eligible_is_deterministic() -> None:
    repository = InMemoryOddsRepository()
    snapshots = (
        make_snapshot(
            snapshot_id="qa_early",
            available_at=CUTOFF - timedelta(minutes=30),
        ),
        make_snapshot(
            snapshot_id="qa_latest",
            available_at=CUTOFF - timedelta(minutes=5),
        ),
        make_snapshot(
            snapshot_id="qa_future",
            available_at=CUTOFF + timedelta(minutes=5),
        ),
    )
    provider = MockOddsProvider(snapshots)
    provider.source = SOURCE
    service = OddsService(provider=provider, repository=repository)
    assert service.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=CUTOFF).id == "qa_latest"
    assert [item.id for item in repository.history(MATCH_ID, "1X2")] == [
        "qa_early",
        "qa_latest",
        "qa_future",
    ]

    conflicting = make_snapshot(
        snapshot_id="qa_other_id",
        available_at=CUTOFF - timedelta(minutes=4),
    )
    object.__setattr__(conflicting, "provider_id", "qa_latest")
    with pytest.raises(ValueError, match="immutable"):
        repository.append(conflicting)


def test_requested_cutoff_must_bound_returned_prediction_cutoff() -> None:
    requested_cutoff = CUTOFF
    returned_cutoff = CUTOFF + timedelta(minutes=10)

    class LaterCutoffPredictionService(StaticPredictionService):
        def predict(self, match_id: str, cutoff_at: datetime | None) -> FootballModelPrediction:
            return super().predict(match_id, returned_cutoff)

    odds_between_cutoffs = make_snapshot(
        available_at=CUTOFF + timedelta(minutes=5),
    )
    with pytest.raises(InvalidPredictionError):
        make_value_service(
            odds_between_cutoffs,
            predictions=LaterCutoffPredictionService(),
        ).evaluate(MATCH_ID, requested_cutoff)


def test_value_engine_uses_requested_cutoff_for_odds_selection() -> None:
    requested_cutoff = CUTOFF
    post_request_odds = make_snapshot(
        available_at=CUTOFF + timedelta(minutes=5),
    )

    class MatchingPredictionService(StaticPredictionService):
        def predict(self, match_id: str, cutoff_at: datetime | None) -> FootballModelPrediction:
            return super().predict(match_id, requested_cutoff)

    with pytest.raises(OddsTemporalLeakageError):
        make_value_service(
            post_request_odds,
            predictions=MatchingPredictionService(),
        ).evaluate(MATCH_ID, requested_cutoff)


def test_repository_history_must_be_isolated_by_source_and_data_mode() -> None:
    repository = InMemoryOddsRepository()
    repository.append(make_snapshot())

    class EmptyLiveProvider:
        source = "qa-live-source"
        data_mode = "live"

        def fetch(self, match_id: str, market: str) -> tuple[OddsSnapshot, ...]:
            return ()

    with pytest.raises(OddsUnavailableError):
        OddsService(
            provider=EmptyLiveProvider(),  # type: ignore[arg-type]
            repository=repository,
        ).market_at(match_id=MATCH_ID, market="1X2", cutoff_at=CUTOFF)


def test_persisted_history_should_remain_replayable_during_provider_failure() -> None:
    repository = InMemoryOddsRepository()
    persisted = make_snapshot()
    repository.append(persisted)

    class FailingProvider:
        source = SOURCE
        data_mode = "mock"

        def fetch(self, match_id: str, market: str) -> tuple[OddsSnapshot, ...]:
            raise OddsUnavailableError("Provider unavailable during replay.")

    selected = OddsService(
        provider=FailingProvider(),  # type: ignore[arg-type]
        repository=repository,
    ).market_at(match_id=MATCH_ID, market="1X2", cutoff_at=CUTOFF)
    assert selected == persisted


def test_latest_complete_snapshot_should_ignore_newer_incomplete_snapshot() -> None:
    complete = make_snapshot(
        snapshot_id="qa_complete_old",
        available_at=CUTOFF - timedelta(minutes=10),
    )
    incomplete = make_snapshot(
        snapshot_id="qa_incomplete_new",
        available_at=CUTOFF - timedelta(minutes=5),
        odds={
            Selection.HOME: Decimal("2"),
            Selection.DRAW: Decimal("4"),
        },
    )
    result = make_value_service(complete, incomplete).evaluate(MATCH_ID, CUTOFF)
    assert result.odds.provider_id == complete.provider_id


def test_serialized_subsecond_cutoff_must_replay_identically() -> None:
    base = datetime(2026, 7, 7, 16, tzinfo=UTC)
    snapshot = make_snapshot(
        available_at=base + timedelta(microseconds=400_000),
        collected_at=base,
    )
    initial_cutoff = base + timedelta(microseconds=500_000)
    service = make_value_service(snapshot)
    first = service.evaluate(MATCH_ID, initial_cutoff)
    serialized_cutoff = first.metadata.model_dump(mode="json")["cutoff_at"]
    assert serialized_cutoff == "2026-07-07T16:00:00.500000Z"
    replayed = service.evaluate(MATCH_ID, parse_rfc3339(serialized_cutoff))
    assert replayed.value == first.value
    assert replayed.market_probabilities == first.market_probabilities


def test_rfc3339_preserves_fractional_seconds() -> None:
    value = datetime(2026, 7, 7, 16, 0, 0, 400000, tzinfo=UTC)
    assert to_rfc3339(value) == "2026-07-07T16:00:00.400000Z"
    assert parse_rfc3339(to_rfc3339(value)) == value
    assert to_rfc3339(CUTOFF) == "2026-07-07T16:00:00Z"


def test_odds_migration_must_backfill_data_mode_before_not_null() -> None:
    migration = (
        REPO_ROOT
        / "apps"
        / "api"
        / "alembic"
        / "versions"
        / "0004_odds_history.py"
    ).read_text(encoding="utf-8")
    update_block = migration.split('op.alter_column("odds_snapshots", "data_mode"', maxsplit=1)[0]
    assert "data_mode =" in update_block
    assert "COALESCE(data_mode, 'mock')" in update_block


def test_value_is_reproducible_and_preserves_candidate_and_mock_metadata() -> None:
    value = make_value_service(make_snapshot())
    first = value.evaluate(MATCH_ID, CUTOFF)
    second = value.evaluate(MATCH_ID, CUTOFF)
    assert first == second
    assert first.market_probabilities == second.market_probabilities
    assert first.value == second.value
    assert first.metadata.model_version == "football-elo-v1-candidate"
    assert first.metadata.model_status == "candidate"
    assert first.metadata.dataset_version == "football-1x2-history-0.3"
    assert first.metadata.feature_schema_version == "football-1x2-features-0.3"
    assert first.metadata.data_mode == "mock"
    assert first.metadata.odds_source == SOURCE


def test_value_engine_consumes_prediction_service_without_recomputing() -> None:
    predictions = StaticPredictionService(home=0.55, draw=0.25, away=0.20)
    result = make_value_service(make_snapshot(), predictions=predictions).evaluate(
        MATCH_ID,
        CUTOFF,
    )
    assert result.prediction.home_probability == pytest.approx(0.55)
    assert result.prediction.draw_probability == pytest.approx(0.25)
    assert result.prediction.away_probability == pytest.approx(0.20)
    assert result.metadata.model_version == "football-elo-v1-candidate"
    assert result.metadata.model_status == "candidate"
    assert result.value.home.edge == pytest.approx(0.05)


def test_invalid_probability_ranges_and_simplex_are_refused() -> None:
    invalid_range = FootballModelPrediction.model_construct(
        match_id=MATCH_ID,
        sport="football",
        market="1X2",
        home_probability=1.10,
        draw_probability=0.10,
        away_probability=-0.20,
        model_version="football-elo-v1-candidate",
        dataset_version="football-1x2-history-0.3",
        feature_schema_version="football-1x2-features-0.3",
        model_status="candidate",
        cutoff_at=CUTOFF,
        cutoff_policy="pre_kickoff",
        generated_at=CUTOFF,
    )
    invalid_simplex = FootballModelPrediction.model_construct(
        **{
            **invalid_range.__dict__,
            "home_probability": 0.60,
            "draw_probability": 0.30,
            "away_probability": 0.30,
        }
    )

    class InvalidPredictionService:
        def __init__(self, result: FootballModelPrediction) -> None:
            self.result = result

        def predict(self, match_id: str, cutoff_at: datetime | None) -> FootballModelPrediction:
            return self.result

    for prediction in (invalid_range, invalid_simplex):
        with pytest.raises(InvalidPredictionError):
            make_value_service(
                make_snapshot(),
                predictions=InvalidPredictionService(prediction),
            ).evaluate(MATCH_ID, CUTOFF)


def test_missing_prediction_metadata_must_be_refused_as_domain_error() -> None:
    incomplete = FootballModelPrediction.model_construct(
        match_id=MATCH_ID,
        sport="football",
        market="1X2",
        home_probability=0.60,
        draw_probability=0.20,
        away_probability=0.20,
        cutoff_at=CUTOFF,
    )

    class IncompletePredictionService:
        def predict(self, match_id: str, cutoff_at: datetime | None) -> FootballModelPrediction:
            return incomplete

    with pytest.raises(InvalidPredictionError):
        make_value_service(
            make_snapshot(),
            predictions=IncompletePredictionService(),
        ).evaluate(MATCH_ID, CUTOFF)


def test_controlled_end_to_end_http_math_and_rfc9457_errors() -> None:
    app = make_app()
    app.state.container._football_values = make_value_service(make_snapshot())
    client = TestClient(app)
    success = client.get(
        f"/api/v1/football/value/{MATCH_ID}",
        params={"cutoff_at": CUTOFF.isoformat()},
        headers={"X-Request-ID": "req_qa_value"},
    )
    assert success.status_code == 200
    assert success.headers["X-Request-ID"] == "req_qa_value"
    body = success.json()
    assert body["request_id"] == "req_qa_value"
    assert body["data"]["prediction"] == {
        "home_probability": 0.6,
        "draw_probability": 0.2,
        "away_probability": 0.2,
    }
    assert body["data"]["market_probabilities"]["home"]["implied_probability"] == 0.5
    assert body["data"]["value"]["home"] == {"edge": 0.1, "ev": 0.2}
    assert body["data"]["metadata"]["model_status"] == "candidate"

    cases = (
        (
            make_value_service(
                make_snapshot(
                    odds={
                        Selection.HOME: Decimal("2"),
                        Selection.DRAW: Decimal("4"),
                    }
                )
            ),
            422,
            "/problems/incomplete-odds-market",
        ),
        (
            make_value_service(
                make_snapshot(available_at=CUTOFF + timedelta(seconds=1))
            ),
            409,
            "/problems/odds-temporal-leakage",
        ),
        (
            make_value_service(
                make_snapshot(),
                predictions=MissingPredictionService(),
            ),
            422,
            "/problems/pit-features-unavailable",
        ),
    )
    for service, expected_status, expected_type in cases:
        app.state.container._football_values = service
        response = client.get(
            f"/api/v1/football/value/{MATCH_ID}",
            params={"cutoff_at": CUTOFF.isoformat()},
            headers={"X-Request-ID": f"req_qa_{expected_status}"},
        )
        payload = response.json()
        assert response.status_code == expected_status
        assert response.headers["content-type"].startswith("application/problem+json")
        assert payload["type"] == expected_type
        assert payload["status"] == expected_status
        assert payload["title"]
        assert payload["detail"]
        assert payload["request_id"] == f"req_qa_{expected_status}"


def test_valid_ordinary_market_must_succeed_end_to_end() -> None:
    app = make_app()
    app.state.container._football_values = make_value_service(
        make_snapshot(
            odds={
                Selection.HOME: Decimal("1.90"),
                Selection.DRAW: Decimal("3.20"),
                Selection.AWAY: Decimal("4.20"),
            }
        )
    )
    response = TestClient(app, raise_server_exceptions=False).get(
        f"/api/v1/football/value/{MATCH_ID}",
        params={"cutoff_at": CUTOFF.isoformat()},
        headers={"X-Request-ID": "req_qa_valid_market"},
    )
    assert response.status_code == 200
    market = response.json()["data"]["market_probabilities"]
    no_vig_sum = (
        market["home"]["no_vig_probability"]
        + market["draw"]["no_vig_probability"]
        + market["away"]["no_vig_probability"]
    )
    assert no_vig_sum == pytest.approx(1.0)


def test_three_historical_prediction_paths_with_explicit_mock_odds() -> None:
    app = make_app()
    container = app.state.container
    prediction_service = container.football_predictions()
    snapshots: list[OddsSnapshot] = []
    for index, match_id in enumerate(HISTORICAL_MATCH_IDS):
        prediction = prediction_service.predict(match_id, None)
        snapshots.append(
            make_snapshot(
                match_id=match_id,
                snapshot_id=f"qa_historical_mock_{index}",
                available_at=prediction.cutoff_at - timedelta(minutes=10),
            )
        )
    provider = MockOddsProvider(tuple(snapshots))
    provider.source = SOURCE
    container.football_odds = OddsService(
        provider=provider,
        repository=InMemoryOddsRepository(),
    )
    container._football_values = None
    client = TestClient(app)

    for match_id in HISTORICAL_MATCH_IDS:
        response = client.get(f"/api/v1/football/value/{match_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["match_id"] == match_id
        assert data["odds"]["available_at"] <= data["metadata"]["cutoff_at"]
        assert data["metadata"]["data_mode"] == "mock"
        assert data["metadata"]["model_version"] == "football-elo-v1-candidate"
        assert data["metadata"]["model_status"] == "candidate"


def test_openapi_value_contract_describes_latest_complete_snapshot() -> None:
    spec = (REPO_ROOT / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
    assert "latest" in spec
    assert "complete odds snapshot" in spec
    assert "does not mask an older complete snapshot" in spec
    assert "/football/value/{match_id}" in spec
