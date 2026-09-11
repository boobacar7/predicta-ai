from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.ai_picks.config import AI_PICKS_VERSION, AiPicksThresholds
from app.backtesting.expanded import (
    EXPAND_WINDOWS,
    STAKE_POLICY,
    run_persisted_expanded_pilot,
)
from app.backtesting.pilot import (
    ISOLATED_PARIS_TEAM_ID,
    WEEKEND_IDENTITY_EXCLUSIONS,
    StubCandidatePredictor,
    catalog_identity_exclusions,
)
from app.backtesting.types import CatalogMatch
from app.core.clock import Clock
from app.odds.the_odds_api import LIVE_ODDS_SOURCE
from app.odds.types import Football1x2Selection, OddsSelection, OddsSnapshot
from app.predictions.features import InMemoryPitFeatureStore
from app.predictions.service import FootballPredictionService
from app.predictions.types import CANDIDATE_MODEL_VERSION, CANDIDATE_STATUS
from app.value_engine.calculator import VALUE_ENGINE_VERSION

HELIX_ID = "mth_football-sportmonks-helix-expand"
PARIS_ID = "mth_football-sportmonks-19715629"
MAY_PARIS_ID = "mth_football-sportmonks-may-paris"
KICKOFF = datetime(2026, 8, 21, 19, tzinfo=UTC)
NEAR = datetime(2026, 8, 21, 18, 49, tzinfo=UTC)

CATALOG = (
    CatalogMatch(
        match_id=HELIX_ID,
        home_team_id="tm_helix",
        away_team_id="tm_meridian",
        home_team="Helix FC",
        away_team="Meridian Athletic",
        league="Premier League",
        kickoff_at=KICKOFF,
        outcome="HOME",
        home_elo_pre=1680.0,
        away_elo_pre=1500.0,
    ),
    CatalogMatch(
        match_id=PARIS_ID,
        home_team_id="tm_troyes",
        away_team_id=ISOLATED_PARIS_TEAM_ID,
        home_team="Troyes",
        away_team="Paris",
        league="Ligue 1",
        kickoff_at=datetime(2026, 8, 22, 18, 45, tzinfo=UTC),
        outcome="DRAW",
        home_elo_pre=1500.0,
        away_elo_pre=1500.0,
    ),
    CatalogMatch(
        match_id=MAY_PARIS_ID,
        home_team_id=ISOLATED_PARIS_TEAM_ID,
        away_team_id="tm_brest",
        home_team="Paris",
        away_team="Brest",
        league="Ligue 1",
        kickoff_at=datetime(2026, 5, 3, 15, 15, tzinfo=UTC),
        outcome="HOME",
        home_elo_pre=1500.0,
        away_elo_pre=1480.0,
    ),
)

PROBS = {
    HELIX_ID: (0.60, 0.20, 0.20),
    PARIS_ID: (0.34, 0.33, 0.33),
    MAY_PARIS_ID: (0.40, 0.30, 0.30),
}


def _snapshot() -> OddsSnapshot:
    return OddsSnapshot(
        id="odd_helix_near",
        provider_id=f"odd_helix_near:pinnacle:1X2:{NEAR.isoformat()}",
        match_id=HELIX_ID,
        bookmaker="pinnacle",
        market="1X2",
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal("1.80")),
            OddsSelection(Football1x2Selection.DRAW, Decimal("3.70")),
            OddsSelection(Football1x2Selection.AWAY, Decimal("4.40")),
        ),
        collected_at=NEAR,
        available_at=NEAR,
        source=LIVE_ODDS_SOURCE,
        data_mode="live",
        raw_payload_id="raw_expand_pilot",
    )


def _predictor() -> FootballPredictionService:
    return FootballPredictionService(
        clock=Clock(KICKOFF),
        features=InMemoryPitFeatureStore([item.pit_features() for item in CATALOG]),
        model=StubCandidatePredictor(PROBS),
    )


def test_expanded_windows_are_pl_l1_and_defined_before_scoring() -> None:
    names = {item[0] for item in EXPAND_WINDOWS}
    assert names == {
        "end-2025-26-may",
        "persist-weekend-2026-08-21",
        "2026-27-following-matchweeks",
    }
    ends = [item[2] for item in EXPAND_WINDOWS]
    assert max(ends) == datetime(2026, 9, 7, tzinfo=UTC)


def test_paris_isolation_extends_beyond_the_labeled_weekend() -> None:
    exclusions = catalog_identity_exclusions(CATALOG)
    assert PARIS_ID in exclusions
    assert MAY_PARIS_ID in exclusions
    assert exclusions[MAY_PARIS_ID].startswith("isolated_team")
    assert PARIS_ID in WEEKEND_IDENTITY_EXCLUSIONS
    assert HELIX_ID not in exclusions


def test_expanded_scoring_keeps_engines_and_thresholds() -> None:
    report = run_persisted_expanded_pilot(
        catalog=CATALOG,
        snapshots=(_snapshot(),),
        predictions=_predictor(),
    )
    assert report["kind"] == "persisted_live_expanded"
    assert report["model_version"] == CANDIDATE_MODEL_VERSION
    assert report["model_status"] == CANDIDATE_STATUS
    assert report["value_engine_version"] == VALUE_ENGINE_VERSION
    assert report["ai_picks_version"] == AI_PICKS_VERSION
    assert report["candidate_promoted"] is False
    assert report["thresholds"]["optimized_on_test"] is False
    assert report["thresholds"]["minimum_edge"] == 0.0
    assert report["thresholds"]["minimum_ev"] == 0.0
    assert report["thresholds"]["maximum_odds_age_seconds"] == 24 * 3600
    assert AiPicksThresholds().maximum_odds_age == timedelta(hours=24)
    assert report["pit"]["passed"] is True
    assert report["value_parity"]["passed"] is True
    assert report["ai_picks_parity"]["passed"] is True
    assert report["reproducibility"]["passed"] is True
    assert report["stake_policy"] == STAKE_POLICY
    pick_ids = {item[0] for item in report["fingerprint"]["picks"]}
    assert PARIS_ID not in pick_ids
    assert MAY_PARIS_ID not in pick_ids
    assert report["dataset"]["matches_with_odds"] == 1
    assert report["model_performance"]["log_loss"] is not None
    assert "by_competition" in report["model_performance"]
    assert report["multiple_picks"]["eligible_matches"] == 1
    dataset_match_ids = {item["match_id"] for item in report["analytical_dataset"]}
    assert HELIX_ID in dataset_match_ids
    assert all(item["model_version"] == CANDIDATE_MODEL_VERSION for item in report["analytical_dataset"])
    assert all(item["data_mode"] == "live" for item in report["analytical_dataset"])
    assert report["descriptive_slices"]["purpose"].startswith("Descriptive")
    assert "MODEL PERFORMANCE" in report["comparisons"]["note"]
    kinds = {item["kind"] for item in report["quality"]["exclusions"]}
    assert "isolated_team" in kinds
