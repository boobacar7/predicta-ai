from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from app.ai_analyst.service import FootballAnalystService
from app.ai_picks.config import AiPicksThresholds
from app.ai_picks.models import AiPicksQuery, MatchCandidate
from app.ai_picks.service import AiPicksEngine
from app.core.clock import Clock
from app.match_identity.models import MatchIdentity
from app.odds.exceptions import OddsUnavailableError
from app.odds.providers import LiveOddsProvider, MockOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.the_odds_api import LIVE_ODDS_SOURCE
from app.odds.types import Football1x2Selection, OddsSelection, OddsSnapshot
from app.predictions.exceptions import PitFeaturesUnavailableError, TemporalLeakageError
from app.predictions.features import CompositePitFeatureStore, InMemoryPitFeatureStore, PrematchParquetFeatureStore
from app.predictions.models import load_football_1x2_model
from app.predictions.service import FootballPredictionService
from app.predictions.types import CANDIDATE_MODEL_VERSION, PitEloFeatures
from app.schemas import FootballModelPrediction
from app.value_engine.calculator import VALUE_ENGINE_VERSION, expected_value, implied_probability
from app.value_engine.service import FootballValueService
from tests.live_assets import CANDIDATE_ARTEFACT, requires_live_assets

MATCH_ID = "mth_football-sportmonks-19722167"
KICKOFF = datetime(2026, 9, 12, 14, tzinfo=UTC)
HOME_ELO = 1580.0
AWAY_ELO = 1490.0
LIVE_ODDS = {
    Football1x2Selection.HOME: Decimal("1.45"),
    Football1x2Selection.DRAW: Decimal("5.02"),
    Football1x2Selection.AWAY: Decimal("6.69"),
}


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
        home_team_id="tm_football-sportmonks-8",
        away_team_id="tm_football-sportmonks-11",
        home_team="Liverpool",
        away_team="Fulham",
        league="Premier League",
        kickoff_at=KICKOFF,
        data_mode="live",
    )


def _prematch_features() -> PitEloFeatures:
    return PitEloFeatures(
        match_id=MATCH_ID,
        event_at=KICKOFF,
        cutoff_at=KICKOFF,
        cutoff_policy="pre_kickoff",
        dataset_version="football-1x2-history-0.3",
        feature_schema_version="football-1x2-features-0.3",
        data_mode="live",
        home_elo_pre=HOME_ELO,
        away_elo_pre=AWAY_ELO,
        elo_diff=HOME_ELO - AWAY_ELO,
    )


def _live_snapshot() -> OddsSnapshot:
    available = KICKOFF - timedelta(hours=2)
    return OddsSnapshot(
        id="odd_the_odds_api_liverpool_fulham",
        provider_id="evt:pinnacle:1X2:2026-09-12T12:00:00+00:00",
        match_id=MATCH_ID,
        bookmaker="pinnacle",
        market="1X2",
        selections=tuple(
            OddsSelection(selection, price) for selection, price in LIVE_ODDS.items()
        ),
        collected_at=available,
        available_at=available,
        source=LIVE_ODDS_SOURCE,
        data_mode="live",
    )


def _live_odds_service() -> OddsService:
    return OddsService(
        provider=LiveOddsProvider(enable_live=True, snapshots=(_live_snapshot(),)),
        repository=InMemoryOddsRepository(),
    )


def _candidate() -> MatchCandidate:
    identity = _identity()
    return MatchCandidate.from_identity(identity)


def test_prematch_store_rejects_post_cutoff_and_does_not_fabricate_labels(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.table(
        {
            "match_id": [MATCH_ID],
            "event_at": [KICKOFF.isoformat()],
            "cutoff_policy": ["pre_kickoff"],
            "dataset_version": ["football-1x2-history-0.3"],
            "feature_schema_version": ["football-1x2-features-0.3"],
            "data_mode": ["live"],
            "home_elo_pre": [HOME_ELO],
            "away_elo_pre": [AWAY_ELO],
            "elo_diff": [HOME_ELO - AWAY_ELO],
            "elo_available": [1],
            "feature_origin": ["prematch_unlabeled"],
        }
    )
    path = tmp_path / "prematch.parquet"
    pq.write_table(table, path)
    store = PrematchParquetFeatureStore(path)
    snapshot = store.get_pit_features(MATCH_ID, KICKOFF)
    assert snapshot.data_mode == "live"
    assert snapshot.dataset_version == "football-1x2-history-0.3"
    with pytest.raises(TemporalLeakageError):
        store.get_pit_features(MATCH_ID, KICKOFF + timedelta(microseconds=1))


def test_prematch_store_rejects_labeled_parquet(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.table(
        {
            "match_id": [MATCH_ID],
            "event_at": [KICKOFF.isoformat()],
            "cutoff_policy": ["pre_kickoff"],
            "dataset_version": ["football-1x2-history-0.3"],
            "data_mode": ["live"],
            "home_elo_pre": [HOME_ELO],
            "away_elo_pre": [AWAY_ELO],
            "elo_diff": [HOME_ELO - AWAY_ELO],
            "home_win": [1],
        }
    )
    path = tmp_path / "labeled.parquet"
    pq.write_table(table, path)
    with pytest.raises(PitFeaturesUnavailableError, match="unlabeled"):
        PrematchParquetFeatureStore(path)


def test_composite_store_does_not_mask_leakage_with_overlay() -> None:
    history = InMemoryPitFeatureStore([_prematch_features()])
    overlay = InMemoryPitFeatureStore([])
    store = CompositePitFeatureStore([history, overlay])
    with pytest.raises(TemporalLeakageError):
        store.get_pit_features(MATCH_ID, KICKOFF + timedelta(seconds=1))


def test_real_odds_value_uses_candidate_metadata_and_live_source() -> None:
    prediction = FootballModelPrediction(
        match_id=MATCH_ID,
        home_probability=0.62,
        draw_probability=0.21,
        away_probability=0.17,
        model_version=CANDIDATE_MODEL_VERSION,
        dataset_version="football-1x2-history-0.3",
        feature_schema_version="football-1x2-features-0.3",
        model_status="candidate",
        cutoff_at=KICKOFF,
        cutoff_policy="pre_kickoff",
        generated_at=KICKOFF,
    )
    value = FootballValueService(
        clock=Clock(KICKOFF),
        predictions=StaticPredictionService(prediction),
        odds=_live_odds_service(),
    ).evaluate(MATCH_ID, KICKOFF)
    assert value.metadata.model_version == CANDIDATE_MODEL_VERSION
    assert value.metadata.model_status == "candidate"
    assert value.metadata.value_engine_version == VALUE_ENGINE_VERSION
    assert value.metadata.odds_source == LIVE_ODDS_SOURCE
    assert value.metadata.data_mode == "live"
    home_odds = LIVE_ODDS[Football1x2Selection.HOME]
    assert value.value.home.edge == pytest.approx(0.62 - float(implied_probability(home_odds)))
    assert value.value.home.ev == pytest.approx(float(expected_value(Decimal("0.62"), home_odds)))
    assert value.prediction.home_probability == pytest.approx(0.62)


def test_real_odds_ai_picks_consume_value_without_recomputing() -> None:
    prediction = FootballModelPrediction(
        match_id=MATCH_ID,
        home_probability=0.62,
        draw_probability=0.21,
        away_probability=0.17,
        model_version=CANDIDATE_MODEL_VERSION,
        dataset_version="football-1x2-history-0.3",
        feature_schema_version="football-1x2-features-0.3",
        model_status="candidate",
        cutoff_at=KICKOFF,
        cutoff_policy="pre_kickoff",
        generated_at=KICKOFF,
    )
    values = FootballValueService(
        clock=Clock(KICKOFF),
        predictions=StaticPredictionService(prediction),
        odds=_live_odds_service(),
    )
    result = AiPicksEngine(
        values=values,
        candidates=StaticCandidateSource(_candidate()),
        thresholds=AiPicksThresholds(),
    ).list_picks(
        AiPicksQuery(match_date=None, league=None, limit=20, offset=0, minimum_edge=None, minimum_ev=None)
    )
    assert result.metadata.evaluated_matches == 1
    assert {item.odds_source for item in result.items} <= {LIVE_ODDS_SOURCE}
    assert all(item.model_version == CANDIDATE_MODEL_VERSION for item in result.items)
    assert all(item.data_mode == "live" for item in result.items)
    assert all(item.ai_picks_version == "ai-picks-0.1" for item in result.items)
    home_exclusion = next(item for item in result.exclusions if item.selection == "HOME")
    assert home_exclusion.reason.value in {"negative_ev", "negative_edge"}
    away = next(item for item in result.items if item.selection == "AWAY")
    assert away.model_probability == pytest.approx(0.17)
    assert away.odds == pytest.approx(6.69)


def test_real_odds_ai_analyst_consumes_live_context() -> None:
    prediction = FootballModelPrediction(
        match_id=MATCH_ID,
        home_probability=0.62,
        draw_probability=0.21,
        away_probability=0.17,
        model_version=CANDIDATE_MODEL_VERSION,
        dataset_version="football-1x2-history-0.3",
        feature_schema_version="football-1x2-features-0.3",
        model_status="candidate",
        cutoff_at=KICKOFF,
        cutoff_policy="pre_kickoff",
        generated_at=KICKOFF,
    )
    values = FootballValueService(
        clock=Clock(KICKOFF),
        predictions=StaticPredictionService(prediction),
        odds=_live_odds_service(),
    )
    report = FootballAnalystService(
        clock=Clock(KICKOFF),
        identities=StaticIdentityRepository(_identity()),
        predictions=StaticPredictionService(prediction),
        values=values,
    ).explain(MATCH_ID, KICKOFF)
    assert report.prediction.model_version == CANDIDATE_MODEL_VERSION
    assert report.prediction.model_status == "candidate"
    assert report.value.availability == "available"
    assert report.analyst.data_quality.data_mode == "live"
    assert report.analyst.provider == "deterministic-v0.1"
    assert LIVE_ODDS_SOURCE in {factor.source for factor in report.analyst.key_factors}


def test_mock_live_isolation_does_not_fallback() -> None:
    live_odds = _live_odds_service()
    mock_odds = OddsService(
        provider=MockOddsProvider(),
        repository=InMemoryOddsRepository(),
    )
    live = live_odds.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=KICKOFF)
    assert live.source == LIVE_ODDS_SOURCE
    assert live.data_mode == "live"
    with pytest.raises(OddsUnavailableError):
        mock_odds.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=KICKOFF)
    mock = mock_odds.market_at(
        match_id="mth_football-sportmonks-19719892",
        market="1X2",
        cutoff_at=datetime(2026, 7, 7, 16, tzinfo=UTC),
    )
    assert mock.data_mode == "mock"
    assert mock.source != LIVE_ODDS_SOURCE


@requires_live_assets
def test_candidate_model_scores_prematch_features_without_promotion() -> None:
    model = load_football_1x2_model(
        registry_dir=CANDIDATE_ARTEFACT.parent.parent,
        model_version=CANDIDATE_MODEL_VERSION,
    )
    assert model.model_version == CANDIDATE_MODEL_VERSION
    assert model.model_status == "candidate"
    service = FootballPredictionService(
        clock=Clock(KICKOFF),
        features=InMemoryPitFeatureStore([_prematch_features()]),
        model=model,
    )
    prediction = service.predict(MATCH_ID, KICKOFF)
    assert prediction.model_version == CANDIDATE_MODEL_VERSION
    assert prediction.model_status == "candidate"
    total = prediction.home_probability + prediction.draw_probability + prediction.away_probability
    assert total == pytest.approx(1.0, abs=1e-12)
    value = FootballValueService(
        clock=Clock(KICKOFF),
        predictions=service,
        odds=_live_odds_service(),
    ).evaluate(MATCH_ID, KICKOFF)
    assert value.prediction.home_probability == prediction.home_probability
    assert value.metadata.model_status == "candidate"
    assert value.metadata.odds_source == LIVE_ODDS_SOURCE
    assert value.metadata.data_mode == "live"
