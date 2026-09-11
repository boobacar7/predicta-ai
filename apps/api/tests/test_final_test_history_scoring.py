from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.ai_picks.config import AI_PICKS_VERSION, AiPicksThresholds
from app.backtesting.final_test_history import (
    FINAL_TEST_CLOCK,
    ODDS_BINS,
    SCORING_WINDOWS,
    run_persisted_final_test_history,
)
from app.backtesting.pilot import (
    ISOLATED_PARIS_TEAM_ID,
    WEEKEND_IDENTITY_EXCLUSIONS,
    StubCandidatePredictor,
    catalog_identity_exclusions,
    selected_snapshot_is_pit_safe,
)
from app.backtesting.types import CatalogMatch
from app.core.clock import Clock
from app.odds.the_odds_api import LIVE_ODDS_SOURCE
from app.odds.types import Football1x2Selection, OddsSelection, OddsSnapshot
from app.predictions.features import InMemoryPitFeatureStore
from app.predictions.service import FootballPredictionService
from app.predictions.types import CANDIDATE_MODEL_VERSION
from app.value_engine.calculator import VALUE_ENGINE_VERSION, edge, expected_value, implied_probability

HELIX_ID = "mth_football-sportmonks-helix-final-test"
PARIS_ID = "mth_football-sportmonks-19715629"
WINDOW_01 = datetime(2024, 8, 16, 19, tzinfo=UTC)
WINDOW_02 = datetime(2024, 10, 5, 14, tzinfo=UTC)
EXISTING = datetime(2026, 8, 21, 19, tzinfo=UTC)
NEAR = datetime(2024, 8, 16, 18, 49, tzinfo=UTC)
AFTER = datetime(2024, 8, 16, 19, 5, tzinfo=UTC)

CATALOG = (
    CatalogMatch(
        match_id=HELIX_ID,
        home_team_id="tm_helix",
        away_team_id="tm_meridian",
        home_team="Helix FC",
        away_team="Meridian Athletic",
        league="Premier League",
        kickoff_at=WINDOW_01,
        outcome="HOME",
        home_elo_pre=1680.0,
        away_elo_pre=1500.0,
    ),
    CatalogMatch(
        match_id="mth_autumn_helix",
        home_team_id="tm_helix",
        away_team_id="tm_meridian",
        home_team="Helix FC",
        away_team="Meridian Athletic",
        league="Premier League",
        kickoff_at=WINDOW_02,
        outcome="AWAY",
        home_elo_pre=1600.0,
        away_elo_pre=1580.0,
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
)

PROBS = {
    HELIX_ID: (0.60, 0.20, 0.20),
    "mth_autumn_helix": (0.40, 0.30, 0.30),
    PARIS_ID: (0.34, 0.33, 0.33),
}


def _snapshot(match_id: str, kickoff: datetime, *, available: datetime | None = None) -> OddsSnapshot:
    available_at = available or (kickoff - timedelta(minutes=11))
    stamp = available_at.strftime("%Y%m%dT%H%M%S")
    return OddsSnapshot(
        id=f"odd_{match_id}_{stamp}",
        provider_id=f"{match_id}:pinnacle:1X2:{available_at.isoformat()}",
        match_id=match_id,
        bookmaker="pinnacle",
        market="1X2",
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal("1.80")),
            OddsSelection(Football1x2Selection.DRAW, Decimal("3.70")),
            OddsSelection(Football1x2Selection.AWAY, Decimal("4.40")),
        ),
        collected_at=available_at,
        available_at=available_at,
        source=LIVE_ODDS_SOURCE,
        data_mode="live",
        raw_payload_id="raw_final_test",
    )


def _predictor() -> FootballPredictionService:
    return FootballPredictionService(
        clock=Clock(FINAL_TEST_CLOCK),
        features=InMemoryPitFeatureStore([item.pit_features() for item in CATALOG]),
        model=StubCandidatePredictor(PROBS),
    )


def test_scoring_windows_match_predeclared_artefact() -> None:
    ids = [item[0] for item in SCORING_WINDOWS]
    assert ids == [
        "final_test_window_01",
        "final_test_window_02",
        "final_test_window_03",
        "final_test_window_existing",
    ]
    artefact = json.loads(
        (Path(__file__).resolve().parents[3] / "docs" / "qa" / "final-test-windows.json").read_text()
    )
    assert artefact["defined_before_scoring"] is True
    assert [item["window_id"] for item in artefact["windows"]] == ids
    additional = [item for item in artefact["windows"] if item["additional"]]
    assert all(item["elo_temporal_split"] == "final_train" for item in additional)


def test_engines_and_thresholds_unchanged() -> None:
    report = run_persisted_final_test_history(
        catalog=CATALOG,
        snapshots=(
            _snapshot(HELIX_ID, WINDOW_01),
            _snapshot("mth_autumn_helix", WINDOW_02),
        ),
        predictions=_predictor(),
    )
    assert report["kind"] == "expand_final_test_history"
    assert report["model_version"] == CANDIDATE_MODEL_VERSION
    assert report["model_status"] == "candidate"
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
    assert report["verdict"] in {"GO", "GO WITH CONDITIONS", "NO-GO"}
    assert "rentable" not in json.dumps(report).lower()


def test_windows_are_scored_independently_and_keep_identity_rules() -> None:
    report = run_persisted_final_test_history(
        catalog=CATALOG,
        snapshots=(
            _snapshot(HELIX_ID, WINDOW_01),
            _snapshot("mth_autumn_helix", WINDOW_02),
        ),
        predictions=_predictor(),
    )
    by_id = {item["window_id"]: item for item in report["window_reports"]}
    assert by_id["final_test_window_01"]["dataset"]["identity_matched"] == 1
    assert by_id["final_test_window_02"]["dataset"]["identity_matched"] == 1
    assert by_id["final_test_window_01"]["ai_picks_performance"]["n"] >= 1
    # Ranks restart per window; a global ranking would mix 2024-08 with 2024-10.
    assert by_id["final_test_window_01"]["ai_picks_performance"]["n"] != 0
    pick_ids = {row["match_id"] for row in report["analytical_dataset"] if row["AI_Pick_eligibility"]}
    assert PARIS_ID not in pick_ids
    exclusions = catalog_identity_exclusions(CATALOG)
    assert PARIS_ID in exclusions
    assert PARIS_ID in WEEKEND_IDENTITY_EXCLUSIONS
    splits = {row["temporal_split"] for row in report["analytical_dataset"] if row["match_id"] == HELIX_ID}
    assert splits == {"final_train"}
    assert all(row["window_id"] for row in report["analytical_dataset"])
    assert {label for label, _lo, _hi in ODDS_BINS} == {"<2", "2-3", "3-5", "5-10", ">10"}
    ensemble = report["additional_ensemble"]
    assert ensemble["n_windows"] == 2
    assert ensemble["model_performance"]["n"] == 2
    assert ensemble["matches"] == 2


def test_post_cutoff_and_future_snapshots_are_rejected() -> None:
    leaked = _snapshot(HELIX_ID, WINDOW_01, available=AFTER)
    future = _snapshot(HELIX_ID, WINDOW_01, available=WINDOW_01 + timedelta(days=1))
    report = run_persisted_final_test_history(
        catalog=(CATALOG[0],),
        snapshots=(leaked, future, _snapshot(HELIX_ID, WINDOW_01, available=NEAR)),
        predictions=_predictor(),
    )
    window = report["window_reports"][0]
    row = next(item for item in report["analytical_dataset"] if item["match_id"] == HELIX_ID)
    assert row["available_at"] is not None
    available = datetime.fromisoformat(row["available_at"])
    assert selected_snapshot_is_pit_safe(available, WINDOW_01)
    assert available <= WINDOW_01
    assert available != AFTER
    assert available < WINDOW_01 + timedelta(days=1)
    assert window["pit"]["passed"] is True
    implied = implied_probability(Decimal("1.80"))
    assert abs(float(implied) - (1 / 1.80)) < 1e-12
    assert abs(float(edge(Decimal("0.60"), implied)) - (0.60 - (1 / 1.80))) < 1e-12
    assert abs(float(expected_value(Decimal("0.60"), Decimal("1.80"))) - (0.60 * 1.80 - 1)) < 1e-12
