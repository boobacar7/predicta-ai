from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.ai_picks.config import AiPicksThresholds
from app.ai_picks.models import AiPicksQuery, ExclusionReason, MatchCandidate, Opportunity
from app.ai_picks.service import AiPicksEngine
from app.core.clock import Clock
from app.odds.exceptions import IncompleteOddsMarketError, OddsTemporalLeakageError, OddsUnavailableError
from app.odds.providers import MockOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.types import Football1x2Selection, OddsSelection, OddsSnapshot
from app.predictions.exceptions import PitFeaturesUnavailableError
from app.schemas import FootballModelPrediction
from app.value_engine.models import FootballValueAnalysis, SelectionValue
from app.value_engine.service import FootballValueService

MATCH_ID = "match_ai_pick"
CUTOFF = datetime(2026, 7, 7, 16, tzinfo=UTC)


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


class StaticCandidateSource:
    def __init__(self, candidates: list[MatchCandidate] | None = None) -> None:
        self.candidates = candidates or [MatchCandidate(MATCH_ID, "Test League", CUTOFF)]
        self.last_filters: tuple[date | None, str | None] | None = None

    def list_candidates(self, *, match_date: date | None, league: str | None) -> list[MatchCandidate]:
        self.last_filters = (match_date, league)
        return self.candidates


class StaticValueService:
    def __init__(self, analysis: FootballValueAnalysis) -> None:
        self.analysis = analysis

    def evaluate(self, match_id: str, cutoff_at: datetime | None) -> FootballValueAnalysis:
        return self.analysis.model_copy(update={"match_id": match_id})


class RaisingValueService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def evaluate(self, match_id: str, cutoff_at: datetime | None) -> FootballValueAnalysis:
        raise self.error


def _analysis() -> FootballValueAnalysis:
    snapshot = OddsSnapshot(
        id="snapshot",
        provider_id="provider-snapshot",
        match_id=MATCH_ID,
        bookmaker="Fictional Sportsbook",
        market="1X2",
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal("2.00")),
            OddsSelection(Football1x2Selection.DRAW, Decimal("4.00")),
            OddsSelection(Football1x2Selection.AWAY, Decimal("5.00")),
        ),
        collected_at=CUTOFF - timedelta(hours=2),
        available_at=CUTOFF - timedelta(hours=1),
        source="test-mock-odds",
        data_mode="mock",
    )
    odds = OddsService(
        provider=MockOddsProvider((snapshot,)),
        repository=InMemoryOddsRepository(),
    )
    odds._provider.source = "test-mock-odds"  # type: ignore[attr-defined]
    return FootballValueService(
        clock=Clock(CUTOFF),
        predictions=StaticPredictionService(),
        odds=odds,
    ).evaluate(MATCH_ID, CUTOFF)


def _query(**overrides: object) -> AiPicksQuery:
    values: dict[str, object] = {
        "match_date": None,
        "league": None,
        "limit": 20,
        "offset": 0,
        "minimum_edge": None,
        "minimum_ev": None,
    }
    values.update(overrides)
    return AiPicksQuery(**values)  # type: ignore[arg-type]


def _engine(
    *,
    value_service: object | None = None,
    source: StaticCandidateSource | None = None,
    thresholds: AiPicksThresholds | None = None,
) -> AiPicksEngine:
    return AiPicksEngine(
        values=value_service or StaticValueService(_analysis()),  # type: ignore[arg-type]
        candidates=source or StaticCandidateSource(),
        thresholds=thresholds or AiPicksThresholds(),
    )


def test_eligible_pick_uses_prediction_odds_and_value_outputs() -> None:
    result = _engine().list_picks(_query())
    home = next(item for item in result.items if item.selection == "HOME")
    assert home.model_probability == pytest.approx(0.60)
    assert home.odds == pytest.approx(2.00)
    assert home.implied_probability == pytest.approx(0.50)
    assert home.edge == pytest.approx(0.10)
    assert home.ev == pytest.approx(0.20)
    assert home.opportunity_score == pytest.approx(0.30)
    assert home.rank == 1
    assert home.model_status == "candidate"
    assert home.ai_picks_version == "ai-picks-0.1"
    assert home.data_mode == "mock"
    assert {item.reason for item in result.exclusions} == {ExclusionReason.NEGATIVE_EV}


def test_negative_ev_and_negative_edge_reasons_are_explicit() -> None:
    thresholds = AiPicksThresholds()
    negative_ev = AiPicksEngine._selection_exclusion(
        probability=Decimal("0.4"),
        value=SelectionValue(edge=0.1, ev=-0.1),
        age_seconds=0,
        thresholds=thresholds,
    )
    negative_edge = AiPicksEngine._selection_exclusion(
        probability=Decimal("0.4"),
        value=SelectionValue(edge=-0.1, ev=0.1),
        age_seconds=0,
        thresholds=thresholds,
    )
    assert negative_ev == ExclusionReason.NEGATIVE_EV
    assert negative_edge == ExclusionReason.NEGATIVE_EDGE


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (OddsUnavailableError("invalid odds"), ExclusionReason.INVALID_ODDS),
        (IncompleteOddsMarketError("incomplete"), ExclusionReason.INCOMPLETE_MARKET),
        (PitFeaturesUnavailableError("missing prediction"), ExclusionReason.PREDICTION_UNAVAILABLE),
        (OddsTemporalLeakageError("future odds"), ExclusionReason.PIT_UNAVAILABLE),
    ],
)
def test_pipeline_failures_are_not_silently_dropped(error: Exception, reason: ExclusionReason) -> None:
    result = _engine(value_service=RaisingValueService(error)).list_picks(_query())
    assert result.items == []
    assert result.exclusions[0].reason == reason
    assert result.exclusions[0].detail


def test_stale_odds_is_excluded() -> None:
    result = _engine(
        thresholds=AiPicksThresholds(maximum_odds_age=timedelta(minutes=30))
    ).list_picks(_query())
    assert result.items == []
    assert {item.reason for item in result.exclusions} == {ExclusionReason.STALE_ODDS}


def test_inconsistent_value_engine_output_is_excluded() -> None:
    analysis = _analysis()
    invalid_value = analysis.value.model_copy(
        update={"home": analysis.value.home.model_copy(update={"edge": 0.25})}
    )
    invalid = analysis.model_copy(update={"value": invalid_value})
    result = _engine(value_service=StaticValueService(invalid)).list_picks(_query())
    assert result.items == []
    assert result.exclusions[0].reason == ExclusionReason.INVALID_VALUE


def test_threshold_filters_and_metadata_are_centralized() -> None:
    result = _engine().list_picks(
        _query(minimum_edge=Decimal("0.11"), minimum_ev=Decimal("0.21"))
    )
    assert result.items == []
    assert result.metadata.minimum_edge == pytest.approx(0.11)
    assert result.metadata.minimum_ev == pytest.approx(0.21)
    assert result.metadata.scoring_formula == "opportunity_score = EV + Edge"
    assert result.metadata.candidate_model_allowed is True


def _opportunity(
    match_id: str,
    *,
    score: str,
    ev: str,
    edge: str,
    freshness: int,
    selection: Football1x2Selection = Football1x2Selection.HOME,
) -> Opportunity:
    return Opportunity(
        match_id=match_id,
        sport="football",
        league="League",
        market="1X2",
        selection=selection,
        model_probability=Decimal("0.6"),
        implied_probability=Decimal("0.5"),
        no_vig_probability=Decimal("0.48"),
        edge=Decimal(edge),
        ev=Decimal(ev),
        odds=Decimal("2"),
        odds_source="mock",
        model_version="football-elo-v1-candidate",
        model_status="candidate",
        value_engine_version="value-engine-0.1",
        cutoff_at=CUTOFF,
        generated_at=CUTOFF,
        data_mode="mock",
        odds_available_at=CUTOFF - timedelta(hours=1),
        data_freshness=freshness,
        opportunity_score=Decimal(score),
    )


def test_ranking_and_tie_break_are_deterministic() -> None:
    opportunities = [
        _opportunity("match_b", score="0.3", ev="0.2", edge="0.1", freshness=2),
        _opportunity("match_score", score="0.4", ev="0.1", edge="0.3", freshness=1),
        _opportunity("match_ev", score="0.3", ev="0.25", edge="0.05", freshness=1),
        _opportunity("match_a", score="0.3", ev="0.2", edge="0.1", freshness=2),
        _opportunity("match_fresh", score="0.3", ev="0.2", edge="0.1", freshness=1),
    ]
    first = AiPicksEngine._rank_opportunities(opportunities)
    second = AiPicksEngine._rank_opportunities(list(reversed(opportunities)))
    expected = ["match_score", "match_ev", "match_a", "match_b", "match_fresh"]
    assert [item.match_id for item in first] == expected
    assert [item.match_id for item in second] == expected


def test_filters_are_passed_to_candidate_source() -> None:
    source = StaticCandidateSource()
    requested_date = date(2026, 7, 7)
    _engine(source=source).list_picks(_query(match_date=requested_date, league="Test League"))
    assert source.last_filters == (requested_date, "Test League")


def test_pagination_preserves_global_ranks() -> None:
    candidates = [
        MatchCandidate("match_a", "Test League", CUTOFF),
        MatchCandidate("match_b", "Test League", CUTOFF),
    ]
    result = _engine(source=StaticCandidateSource(candidates)).list_picks(
        _query(limit=1, offset=1)
    )
    assert result.total == 4
    assert len(result.items) == 1
    assert result.items[0].rank == 2


def test_duplicate_match_candidates_do_not_duplicate_selections() -> None:
    duplicate = MatchCandidate(MATCH_ID, "Test League", CUTOFF)
    result = _engine(source=StaticCandidateSource([duplicate, duplicate])).list_picks(_query())
    keys = {(item.match_id, item.market, item.selection) for item in result.items}
    assert len(keys) == len(result.items)
    assert result.metadata.evaluated_matches == 1
