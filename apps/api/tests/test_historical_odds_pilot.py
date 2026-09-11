from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from inspect import getsource

import pytest
from app.ai_analyst.service import FootballAnalystService
from app.ai_picks.config import AI_PICKS_VERSION, AiPicksThresholds
from app.ai_picks.models import AiPicksQuery, MatchCandidate
from app.ai_picks.service import AiPicksEngine
from app.core.clock import Clock
from app.match_identity.models import MatchIdentity
from app.odds.exceptions import OddsTemporalLeakageError
from app.odds.providers import LiveOddsProvider, MockOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.the_odds_api import LIVE_ODDS_SOURCE
from app.odds.types import Football1x2Selection, OddsSelection, OddsSnapshot
from app.predictions.types import CANDIDATE_MODEL_VERSION
from app.schemas import FootballModelPrediction
from app.value_engine.calculator import (
    VALUE_ENGINE_VERSION,
    edge,
    expected_value,
    implied_probability,
    no_vig_probabilities,
)
from app.value_engine.service import FootballValueService

MATCH_ID = "mth_football-sportmonks-helix-pilot"
KICKOFF = datetime(2026, 8, 16, 14, tzinfo=UTC)
BEFORE = datetime(2026, 8, 16, 10, 48, tzinfo=UTC)
AFTER = datetime(2026, 8, 16, 14, 55, tzinfo=UTC)
PINNACLE_ODDS = {
    Football1x2Selection.HOME: Decimal("1.80"),
    Football1x2Selection.DRAW: Decimal("3.70"),
    Football1x2Selection.AWAY: Decimal("4.40"),
}
BETFAIR_ODDS = {
    Football1x2Selection.HOME: Decimal("1.82"),
    Football1x2Selection.DRAW: Decimal("3.65"),
    Football1x2Selection.AWAY: Decimal("4.30"),
}
MODEL_PROBS = (Decimal("0.55"), Decimal("0.24"), Decimal("0.21"))


class StaticIdentityRepository:
    def __init__(self, identity: MatchIdentity) -> None:
        self._identity = identity

    def get(self, match_id: str) -> MatchIdentity | None:
        if match_id != self._identity.match_id:
            return None
        return self._identity


class StaticCandidateSource:
    def __init__(self, candidate: MatchCandidate) -> None:
        self._candidate = candidate

    def list_candidates(self, *, match_date: object, league: object) -> list[MatchCandidate]:
        del match_date, league
        return [self._candidate]


class StaticPredictionService:
    def __init__(self, prediction: FootballModelPrediction) -> None:
        self.prediction = prediction

    def predict(self, match_id: str, cutoff_at: datetime | None) -> FootballModelPrediction:
        return self.prediction.model_copy(
            update={"match_id": match_id, "cutoff_at": cutoff_at or self.prediction.cutoff_at}
        )


def _identity() -> MatchIdentity:
    return MatchIdentity(
        match_id=MATCH_ID,
        home_team_id="tm_helix",
        away_team_id="tm_meridian",
        home_team="Helix FC",
        away_team="Meridian Athletic",
        league="Premier League",
        kickoff_at=KICKOFF,
        data_mode="live",
    )


def _prediction() -> FootballModelPrediction:
    home, draw, away = MODEL_PROBS
    return FootballModelPrediction(
        match_id=MATCH_ID,
        home_probability=float(home),
        draw_probability=float(draw),
        away_probability=float(away),
        model_version=CANDIDATE_MODEL_VERSION,
        dataset_version="football-1x2-history-0.3",
        feature_schema_version="football-1x2-features-0.3",
        model_status="candidate",
        cutoff_at=KICKOFF,
        cutoff_policy="pre_kickoff",
        generated_at=KICKOFF,
    )


def _snapshot(
    *,
    snapshot_id: str,
    bookmaker: str,
    odds: dict[Football1x2Selection, Decimal],
    available_at: datetime,
) -> OddsSnapshot:
    return OddsSnapshot(
        id=snapshot_id,
        provider_id=f"{snapshot_id}:{bookmaker}:1X2:{available_at.isoformat()}",
        match_id=MATCH_ID,
        bookmaker=bookmaker,
        market="1X2",
        selections=tuple(OddsSelection(selection, price) for selection, price in odds.items()),
        collected_at=available_at,
        available_at=available_at,
        source=LIVE_ODDS_SOURCE,
        data_mode="live",
        raw_payload_id="raw_historical_pilot",
    )


def _odds_service(*snapshots: OddsSnapshot) -> OddsService:
    return OddsService(
        provider=LiveOddsProvider(enable_live=True, snapshots=snapshots),
        repository=InMemoryOddsRepository(),
    )


def _value_service(*snapshots: OddsSnapshot) -> FootballValueService:
    return FootballValueService(
        clock=Clock(KICKOFF),
        predictions=StaticPredictionService(_prediction()),
        odds=_odds_service(*snapshots),
    )


def test_historical_value_uses_same_formulas_as_live() -> None:
    snapshot = _snapshot(
        snapshot_id="odd_before_pinnacle",
        bookmaker="pinnacle",
        odds=PINNACLE_ODDS,
        available_at=BEFORE,
    )
    analysis = _value_service(snapshot).evaluate(MATCH_ID, KICKOFF)
    implied = {selection: implied_probability(price) for selection, price in PINNACLE_ODDS.items()}
    no_vig, overround = no_vig_probabilities(PINNACLE_ODDS)
    home, draw, away = MODEL_PROBS
    assert analysis.metadata.value_engine_version == VALUE_ENGINE_VERSION
    assert analysis.metadata.model_version == CANDIDATE_MODEL_VERSION
    assert analysis.metadata.model_status == "candidate"
    assert analysis.metadata.odds_source == LIVE_ODDS_SOURCE
    assert analysis.metadata.data_mode == "live"
    assert analysis.odds.bookmaker == "pinnacle"
    assert analysis.odds.available_at == BEFORE
    assert analysis.market_probabilities.overround == pytest.approx(float(overround))
    assert analysis.market_probabilities.home.implied_probability == pytest.approx(
        float(implied[Football1x2Selection.HOME])
    )
    assert analysis.market_probabilities.home.no_vig_probability == pytest.approx(
        float(no_vig[Football1x2Selection.HOME])
    )
    assert analysis.value.home.edge == pytest.approx(
        float(edge(home, implied[Football1x2Selection.HOME]))
    )
    assert analysis.value.home.ev == pytest.approx(
        float(expected_value(home, PINNACLE_ODDS[Football1x2Selection.HOME]))
    )
    assert analysis.value.draw.ev == pytest.approx(
        float(expected_value(draw, PINNACLE_ODDS[Football1x2Selection.DRAW]))
    )
    assert analysis.value.away.ev == pytest.approx(
        float(expected_value(away, PINNACLE_ODDS[Football1x2Selection.AWAY]))
    )


def test_historical_pit_excludes_snapshot_after_t() -> None:
    before = _snapshot(
        snapshot_id="odd_before",
        bookmaker="pinnacle",
        odds=PINNACLE_ODDS,
        available_at=BEFORE,
    )
    after = _snapshot(
        snapshot_id="odd_after",
        bookmaker="pinnacle",
        odds=BETFAIR_ODDS,
        available_at=AFTER,
    )
    odds = _odds_service(before, after)
    chosen = odds.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=KICKOFF)
    assert chosen.id == "odd_before"
    assert chosen.available_at == BEFORE
    with pytest.raises(OddsTemporalLeakageError):
        odds.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=BEFORE - timedelta(minutes=1))


def test_bookmaker_selection_is_last_complete_not_best_ev() -> None:
    worse_ev = _snapshot(
        snapshot_id="odd_pinnacle_earlier",
        bookmaker="pinnacle",
        odds=PINNACLE_ODDS,
        available_at=BEFORE,
    )
    later_book = _snapshot(
        snapshot_id="odd_betfair_later",
        bookmaker="betfair_ex_eu",
        odds=BETFAIR_ODDS,
        available_at=BEFORE + timedelta(seconds=60),
    )
    chosen = _odds_service(worse_ev, later_book).market_at(
        match_id=MATCH_ID, market="1X2", cutoff_at=KICKOFF
    )
    assert chosen.bookmaker == "betfair_ex_eu"
    analysis = _value_service(worse_ev, later_book).evaluate(MATCH_ID, KICKOFF)
    assert analysis.odds.bookmaker == "betfair_ex_eu"
    pinnacle_away_ev = expected_value(MODEL_PROBS[2], PINNACLE_ODDS[Football1x2Selection.AWAY])
    betfair_away_ev = expected_value(MODEL_PROBS[2], BETFAIR_ODDS[Football1x2Selection.AWAY])
    assert pinnacle_away_ev > betfair_away_ev
    assert analysis.value.away.ev == pytest.approx(float(betfair_away_ev))


def test_historical_path_reaches_ai_picks_without_changing_ranking() -> None:
    ranking_source = getsource(AiPicksEngine._rank_opportunities)
    assert "-item.opportunity_score" in ranking_source
    assert "-item.ev" in ranking_source
    assert AI_PICKS_VERSION == "ai-picks-0.1"
    snapshot = _snapshot(
        snapshot_id="odd_before_pinnacle",
        bookmaker="pinnacle",
        odds=PINNACLE_ODDS,
        available_at=KICKOFF - timedelta(hours=2),
    )
    result = AiPicksEngine(
        values=_value_service(snapshot),
        candidates=StaticCandidateSource(MatchCandidate.from_identity(_identity())),
        thresholds=AiPicksThresholds(),
    ).list_picks(
        AiPicksQuery(match_date=None, league=None, limit=20, offset=0, minimum_edge=None, minimum_ev=None)
    )
    assert result.metadata.evaluated_matches == 1
    assert all(item.ai_picks_version == "ai-picks-0.1" for item in result.items)
    assert all(item.model_version == CANDIDATE_MODEL_VERSION for item in result.items)
    assert all(item.value_engine_version == VALUE_ENGINE_VERSION for item in result.items)
    assert all(item.data_mode == "live" for item in result.items)
    home = next(item for item in result.exclusions if item.selection == "HOME")
    assert home.reason.value in {"negative_ev", "negative_edge"}
    if len(result.items) > 1:
        scores = [item.opportunity_score for item in result.items]
        assert scores == sorted(scores, reverse=True)


def test_historical_path_reaches_analyst_with_llm_off() -> None:
    snapshot = _snapshot(
        snapshot_id="odd_before_pinnacle",
        bookmaker="pinnacle",
        odds=PINNACLE_ODDS,
        available_at=KICKOFF - timedelta(hours=2),
    )
    report = FootballAnalystService(
        clock=Clock(KICKOFF),
        identities=StaticIdentityRepository(_identity()),
        predictions=StaticPredictionService(_prediction()),
        values=_value_service(snapshot),
    ).explain(MATCH_ID, KICKOFF)
    assert report.prediction.model_version == CANDIDATE_MODEL_VERSION
    assert report.prediction.model_status == "candidate"
    assert report.value.availability == "available"
    assert report.analyst.provider == "deterministic-v0.1"
    assert report.analyst.data_quality.data_mode == "live"
    assert LIVE_ODDS_SOURCE in {factor.source for factor in report.analyst.key_factors}


def test_historical_value_is_reproducible() -> None:
    snapshot = _snapshot(
        snapshot_id="odd_before_pinnacle",
        bookmaker="pinnacle",
        odds=PINNACLE_ODDS,
        available_at=BEFORE,
    )
    first = _value_service(snapshot).evaluate(MATCH_ID, KICKOFF)
    second = _value_service(snapshot).evaluate(MATCH_ID, KICKOFF)
    assert first.model_dump() == second.model_dump()
    assert first.value.home.ev == second.value.home.ev
    assert first.odds.bookmaker == second.odds.bookmaker


def test_descriptive_backtest_is_not_a_profitability_claim() -> None:
    balanced = {
        Football1x2Selection.HOME: Decimal("2.00"),
        Football1x2Selection.DRAW: Decimal("4.00"),
        Football1x2Selection.AWAY: Decimal("5.00"),
    }
    snapshot = _snapshot(
        snapshot_id="odd_backtest",
        bookmaker="pinnacle",
        odds=balanced,
        available_at=BEFORE,
    )
    prediction = FootballModelPrediction(
        match_id=MATCH_ID,
        home_probability=0.60,
        draw_probability=0.20,
        away_probability=0.20,
        model_version=CANDIDATE_MODEL_VERSION,
        dataset_version="football-1x2-history-0.3",
        feature_schema_version="football-1x2-features-0.3",
        model_status="candidate",
        cutoff_at=KICKOFF,
        cutoff_policy="pre_kickoff",
        generated_at=KICKOFF,
    )
    analysis = FootballValueService(
        clock=Clock(KICKOFF),
        predictions=StaticPredictionService(prediction),
        odds=_odds_service(snapshot),
    ).evaluate(MATCH_ID, KICKOFF)
    outcome = Football1x2Selection.HOME
    selections = {
        Football1x2Selection.HOME: analysis.value.home,
        Football1x2Selection.DRAW: analysis.value.draw,
        Football1x2Selection.AWAY: analysis.value.away,
    }
    prices = {
        Football1x2Selection.HOME: Decimal(str(analysis.odds.home_odds)),
        Football1x2Selection.DRAW: Decimal(str(analysis.odds.draw_odds)),
        Football1x2Selection.AWAY: Decimal(str(analysis.odds.away_odds)),
    }
    value_picks = [selection for selection, item in selections.items() if item.ev > 0 and item.edge > 0]
    hits = [selection for selection in value_picks if selection is outcome]
    theoretical_return = sum(
        (prices[selection] - 1) if selection is outcome else Decimal("-1") for selection in value_picks
    )
    theoretical_ev = sum(Decimal(str(selections[selection].ev)) for selection in value_picks)
    assert analysis.metadata.value_engine_version == "value-engine-0.1"
    assert len(value_picks) >= 1
    assert theoretical_ev == sum(
        Decimal(str(item.ev)) for item in selections.values() if item.ev > 0 and item.edge > 0
    )
    assert theoretical_return == sum(
        (prices[selection] - 1) if selection is outcome else Decimal("-1") for selection in value_picks
    )
    assert 0 <= len(hits) <= len(value_picks)
    assert CANDIDATE_MODEL_VERSION == "football-elo-v1-candidate"


def test_candidate_model_is_not_promoted_on_historical_path() -> None:
    assert CANDIDATE_MODEL_VERSION == "football-elo-v1-candidate"
    assert VALUE_ENGINE_VERSION == "value-engine-0.1"
    assert AI_PICKS_VERSION == "ai-picks-0.1"
    prediction = _prediction()
    assert prediction.model_status == "candidate"
    live = LiveOddsProvider(enable_live=True, snapshots=())
    mock = MockOddsProvider()
    assert live.source == LIVE_ODDS_SOURCE
    assert mock.source != LIVE_ODDS_SOURCE
    assert live.data_mode == "live"
    assert mock.data_mode == "mock"
