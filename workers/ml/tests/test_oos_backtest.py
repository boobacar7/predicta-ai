from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from predicta_ml.features.dataset import load_football_dataset
from predicta_ml.oos.ai_picks import decide_picks, exclusion_reason
from predicta_ml.oos.dataset import OosMatch, matches_from_frame, select_oos_frame
from predicta_ml.oos.errors import OosIdentityError, OosLeakageError, OosProtocolError
from predicta_ml.oos.leakage import (
    assert_calibration_window,
    assert_feature_observation_pit,
    assert_training_window,
)
from predicta_ml.oos.metrics import pick_metrics, prediction_metrics, settle_pick
from predicta_ml.oos.odds import OddsQuote, select_pit_snapshot
from predicta_ml.oos.outcomes import outcome_for_evaluation
from predicta_ml.oos.predictions import FrozenPrediction
from predicta_ml.oos.protocol import CALIBRATION_CUTOFF, OOS_START, TRAIN_CUTOFF
from predicta_ml.oos.provenance import audit_model_provenance
from predicta_ml.oos.runner import run_oos_backtest
from predicta_ml.oos.value import evaluate_match_value
from tests.support import make_covering_frame, write_frame_parquet
from tests.support_oos import PublishedValueCalculator, make_quote


def _dataset(tmp_path: Path):
    path = tmp_path / "cover.parquet"
    write_frame_parquet(path, make_covering_frame())
    return load_football_dataset(path)


def test_valid_oos_window_runs_and_is_reproducible(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    provenance = audit_model_provenance()
    missing = tmp_path / "no-artefact.joblib"
    first = run_oos_backtest(dataset, provenance=provenance, artefact_path=missing)
    second = run_oos_backtest(dataset, provenance=provenance, artefact_path=missing)
    assert first.report["reproducibility"]["fingerprint"] == second.report["reproducibility"]["fingerprint"]
    assert first.report["window"]["start"] == OOS_START.isoformat()
    assert all(item.kickoff_at >= OOS_START for item in first.matches)
    assert first.report["prediction"]["n"] == len(first.matches)
    assert first.report["candidate_promoted"] is False


def test_same_match_same_cutoff_same_inputs_identical_result(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    provenance = audit_model_provenance()
    missing = tmp_path / "no-artefact.joblib"
    frame = select_oos_frame(dataset, provenance=provenance)
    matches = matches_from_frame(frame)
    match = matches[0]
    quote = make_quote(match_id=match.match_id, kickoff=match.kickoff_at)
    calculator = PublishedValueCalculator()
    first = run_oos_backtest(
        dataset,
        provenance=provenance,
        artefact_path=missing,
        quotes=(quote,),
        calculator=calculator,
    )
    second = run_oos_backtest(
        dataset,
        provenance=provenance,
        artefact_path=missing,
        quotes=(quote,),
        calculator=calculator,
    )
    assert first.report["reproducibility"]["fingerprint"] == second.report["reproducibility"]["fingerprint"]
    row = next(item for item in first.rows if item["match_id"] == match.match_id and item["selection"] == "HOME")
    assert row["cutoff_at"] == match.kickoff_at.isoformat()


def test_future_odds_do_not_change_earlier_prediction(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    provenance = audit_model_provenance()
    missing = tmp_path / "no-artefact.joblib"
    matches = matches_from_frame(select_oos_frame(dataset, provenance=provenance))
    match = matches[0]
    quote = make_quote(match_id=match.match_id, kickoff=match.kickoff_at, snapshot_id="pit")
    future = make_quote(
        match_id=match.match_id,
        kickoff=match.kickoff_at,
        snapshot_id="future",
        age_hours=-3.0,
        home=1.2,
        draw=6.0,
        away=8.0,
    )
    calculator = PublishedValueCalculator()
    run = run_oos_backtest(
        dataset,
        provenance=provenance,
        artefact_path=missing,
        quotes=(quote,),
        calculator=calculator,
        future_quotes=(future,),
    )
    selected = next(item for item in run.rows if item["match_id"] == match.match_id and item.get("odds_snapshot_id"))
    assert selected["odds_snapshot_id"] == "pit"
    assert selected["odds"] != 1.2


def test_post_cutoff_feature_event_fails(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    provenance = audit_model_provenance()
    matches = matches_from_frame(select_oos_frame(dataset, provenance=provenance))
    match = matches[0]
    with pytest.raises(OosLeakageError, match="Feature event_at"):
        run_oos_backtest(
            dataset,
            provenance=provenance,
            artefact_path=tmp_path / "missing.joblib",
            extra_feature_observations={
                match.match_id: {"event_at": match.cutoff_at + timedelta(minutes=1)},
            },
        )


def test_prediction_cutoff_after_kickoff_fails(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    provenance = audit_model_provenance()
    frame = select_oos_frame(dataset, provenance=provenance)
    matches = list(matches_from_frame(frame))
    leaked = matches[0]
    object.__setattr__(leaked, "cutoff_at", leaked.kickoff_at + timedelta(minutes=5))
    with pytest.raises(OosLeakageError, match="after kickoff"):
        from predicta_ml.oos.leakage import assert_prediction_cutoff

        assert_prediction_cutoff(leaked)


def test_odds_leakage_and_duplicate_snapshots() -> None:
    kickoff = datetime(2026, 8, 22, 15, tzinfo=UTC)
    pit = make_quote(match_id="m1", kickoff=kickoff, snapshot_id="a")
    future = make_quote(match_id="m1", kickoff=kickoff, snapshot_id="b", age_hours=-1)
    selected = select_pit_snapshot((pit, future), match_id="m1", cutoff_at=kickoff, kickoff_at=kickoff)
    assert selected.snapshot_id == "a"
    with pytest.raises(OosLeakageError, match="post-cutoff"):
        select_pit_snapshot((future,), match_id="m1", cutoff_at=kickoff, kickoff_at=kickoff)
    twin = OddsQuote(
        snapshot_id="c",
        match_id="m1",
        provider="the-odds-api-v4",
        bookmaker="other",
        market="1X2",
        available_at=pit.available_at,
        collected_at=pit.collected_at,
        home_odds=9.0,
        draw_odds=3.0,
        away_odds=2.0,
        data_mode="live",
    )
    with pytest.raises(OosIdentityError, match="Duplicate odds snapshots"):
        select_pit_snapshot((pit, twin), match_id="m1", cutoff_at=kickoff, kickoff_at=kickoff)


def test_training_and_calibration_leakage() -> None:
    provenance = audit_model_provenance()
    assert_training_window(provenance, TRAIN_CUTOFF - timedelta(seconds=1))
    with pytest.raises(OosLeakageError, match="training cutoff"):
        assert_training_window(provenance, TRAIN_CUTOFF)
    assert_calibration_window(provenance, CALIBRATION_CUTOFF - timedelta(seconds=1))
    with pytest.raises(OosLeakageError, match="calibration cutoff"):
        assert_calibration_window(provenance, CALIBRATION_CUTOFF)
    with pytest.raises(OosLeakageError, match="strictly before cutoff"):
        assert_feature_observation_pit(
            match_id="m",
            cutoff_at=OOS_START,
            feature_available_at=OOS_START,
            feature_event_at=None,
        )


def test_outcome_cannot_be_read_before_kickoff(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    provenance = audit_model_provenance()
    match = matches_from_frame(select_oos_frame(dataset, provenance=provenance))[0]
    with pytest.raises(OosLeakageError, match="before kickoff"):
        outcome_for_evaluation(match, now=match.kickoff_at - timedelta(minutes=1))


def test_identity_ambiguity_duplicate_match_id(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    provenance = audit_model_provenance()
    frame = select_oos_frame(dataset, provenance=provenance)
    duplicated = frame.iloc[[0, 0]].copy()
    with pytest.raises(OosIdentityError, match="Duplicate"):
        matches_from_frame(duplicated)


def test_value_and_ai_picks_gates() -> None:
    prediction = FrozenPrediction(
        match_id="m1",
        home=0.45,
        draw=0.25,
        away=0.30,
        model_version="football-elo-v1-candidate",
        calibration_method="raw",
        used_artefact=False,
    )
    kickoff = datetime(2026, 8, 22, 15, tzinfo=UTC)
    quote = make_quote(match_id="m1", kickoff=kickoff, home=2.5, draw=3.5, away=2.8)
    value = evaluate_match_value(prediction, quote, PublishedValueCalculator())
    implied_home = float(PublishedValueCalculator().implied_probability(Decimal("2.5")))
    home = next(item for item in value.selections if item.selection == "HOME")
    assert abs(home.implied_probability - implied_home) < 1e-12
    decisions = decide_picks(prediction=prediction, quote=quote, value=value, cutoff_at=kickoff)
    eligible = [item for item in decisions if item.eligible]
    assert eligible
    stale = exclusion_reason(value=home, odds_age=timedelta(hours=25))
    assert stale == "stale_odds"


def test_metric_calculations() -> None:
    predictions = (
        FrozenPrediction("a", 1.0, 0.0, 0.0, "m", "raw", False),
        FrozenPrediction("b", 0.0, 0.0, 1.0, "m", "raw", False),
    )
    kickoff = datetime(2026, 8, 1, 15, tzinfo=UTC)
    later = kickoff + timedelta(days=1)
    rows = (
        OosMatch(
            match_id="a",
            kickoff_at=kickoff,
            cutoff_at=kickoff,
            competition="premier-league",
            season="2026/2027",
            home_team_id="h",
            away_team_id="a",
            home_elo_pre=1500,
            away_elo_pre=1500,
            elo_diff=0,
            outcome="HOME",
            y=0,
            data_mode="live",
            dataset_version="football-1x2-history-0.3",
            cutoff_policy="pre_kickoff",
            temporal_split="final_test",
        ),
        OosMatch(
            match_id="b",
            kickoff_at=later,
            cutoff_at=later,
            competition="ligue-1",
            season="2026/2027",
            home_team_id="h",
            away_team_id="a",
            home_elo_pre=1500,
            away_elo_pre=1500,
            elo_diff=0,
            outcome="AWAY",
            y=2,
            data_mode="live",
            dataset_version="football-1x2-history-0.3",
            cutoff_policy="pre_kickoff",
            temporal_split="final_test",
        ),
    )
    metrics = prediction_metrics(rows, predictions)
    assert metrics["n"] == 2
    assert metrics["accuracy"] == 1.0
    assert metrics["log_loss"] < 1e-6
    bets = [
        settle_pick(
            match_id="a",
            selection="HOME",
            odds=2.0,
            edge=0.1,
            ev=0.2,
            kickoff_at=kickoff,
            outcome="HOME",
            league="premier-league",
        ),
        settle_pick(
            match_id="b",
            selection="HOME",
            odds=2.0,
            edge=0.1,
            ev=0.2,
            kickoff_at=later,
            outcome="AWAY",
            league="ligue-1",
        ),
    ]
    picks = pick_metrics(bets)
    assert picks["n"] == 2
    assert picks["hits"] == 1
    assert picks["theoretical_profit"] == pytest.approx(0.0)
    assert picks["longest_losing_streak"] == 1


def test_invalid_oos_window_on_dataset(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    provenance = audit_model_provenance()
    with pytest.raises(OosProtocolError, match="before the artefact freeze"):
        select_oos_frame(
            dataset,
            provenance=provenance,
            start=datetime(2024, 8, 16, tzinfo=UTC),
            end_exclusive=datetime(2024, 10, 1, tzinfo=UTC),
        )
