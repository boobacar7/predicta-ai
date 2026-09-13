from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from predicta_ml.constants import COMPETITION_ORDER, default_committed_reports_dir
from predicta_ml.features.dataset import FootballDataset, load_football_dataset
from predicta_ml.models.frequency import FrequencyBaseline
from predicta_ml.oos.ai_picks import PickDecision, decide_picks, published_thresholds
from predicta_ml.oos.dataset import OosMatch, coverage_report, matches_from_frame, oos_window_end, select_oos_frame
from predicta_ml.oos.errors import OosProtocolError, OosReproducibilityError
from predicta_ml.oos.leakage import (
    assert_artefact_compatible_with_oos,
    assert_feature_observation_pit,
    assert_prediction_cutoff,
    assert_prediction_does_not_use_outcome,
    audit_match_quotes,
)
from predicta_ml.oos.metrics import frequency_baseline_metrics, pick_metrics, prediction_metrics, settle_pick
from predicta_ml.oos.odds import OddsQuote, select_pit_snapshot
from predicta_ml.oos.outcomes import outcome_for_evaluation
from predicta_ml.oos.predictions import FrozenEloPredictor, FrozenPrediction, frozen_predictor_from_provenance
from predicta_ml.oos.protocol import OOS_START, REJECTED_PERIODS, TRAIN_CUTOFF, frozen_manifest_constants
from predicta_ml.oos.provenance import (
    ModelProvenance,
    audit_model_provenance,
    provenance_summary,
    reject_period_if_invalid,
)
from predicta_ml.oos.value import MatchValue, ValueCalculator, evaluate_match_value
from predicta_ml.robustness.checks import resolve_code_version


@dataclass(frozen=True)
class OosRun:
    provenance: ModelProvenance
    matches: tuple[OosMatch, ...]
    predictions: tuple[FrozenPrediction, ...]
    rows: tuple[dict[str, Any], ...]
    report: dict[str, Any]


def run_oos_backtest(
    dataset: FootballDataset,
    *,
    provenance: ModelProvenance | None = None,
    start: datetime | None = None,
    end_exclusive: datetime | None = None,
    quotes: tuple[OddsQuote, ...] = (),
    calculator: ValueCalculator | None = None,
    now: datetime | None = None,
    artefact_path: Path | None = None,
    extra_feature_observations: dict[str, dict[str, datetime]] | None = None,
    future_quotes: tuple[OddsQuote, ...] = (),
) -> OosRun:
    card = provenance or audit_model_provenance()
    window_start = (start or OOS_START).astimezone(UTC)
    window_end = (end_exclusive or oos_window_end(dataset)).astimezone(UTC)
    assert_artefact_compatible_with_oos(card, window_start)
    if card.train_end_exclusive != TRAIN_CUTOFF:
        raise OosProtocolError("Provenance training cutoff does not match the frozen protocol.")
    frame = select_oos_frame(dataset, provenance=card, start=window_start, end_exclusive=window_end)
    matches = matches_from_frame(frame)
    predictor = frozen_predictor_from_provenance(card, artefact_path=artefact_path)
    clock = now.astimezone(UTC) if now is not None else max(item.kickoff_at for item in matches) + timedelta(seconds=1)
    extras = extra_feature_observations or {}
    first = _evaluate(
        matches,
        provenance=card,
        predictor=predictor,
        quotes=quotes,
        calculator=calculator,
        now=clock,
        extra_feature_observations=extras,
    )
    second = _evaluate(
        matches,
        provenance=card,
        predictor=predictor,
        quotes=quotes + future_quotes,
        calculator=calculator,
        now=clock,
        extra_feature_observations=extras,
    )
    if first["fingerprint"] != second["fingerprint"]:
        raise OosReproducibilityError(
            "Changing future odds or re-running the same cutoff changed an earlier OOS result."
        )
    report = _build_report(
        dataset=dataset,
        provenance=card,
        matches=matches,
        predictions=first["predictions"],
        rows=first["rows"],
        quotes=quotes,
        window_start=window_start,
        window_end=window_end,
        predictor=predictor,
        fingerprint=first["fingerprint"],
    )
    return OosRun(
        provenance=card,
        matches=matches,
        predictions=first["predictions"],
        rows=tuple(first["rows"]),
        report=report,
    )


def run_from_paths(
    dataset_path: Path,
    *,
    quotes: tuple[OddsQuote, ...] = (),
    calculator: ValueCalculator | None = None,
    artefact_path: Path | None = None,
) -> OosRun:
    provenance = audit_model_provenance()
    dataset = load_football_dataset(dataset_path)
    if dataset.sha256 != provenance.dataset_sha256:
        raise OosProtocolError("Parquet SHA-256 does not match the frozen candidate registry card.")
    return run_oos_backtest(
        dataset,
        provenance=provenance,
        quotes=quotes,
        calculator=calculator,
        artefact_path=artefact_path,
    )


def write_reports(run: OosRun, *, output_dir: Path | None = None) -> dict[str, str]:
    directory = output_dir or default_committed_reports_dir()
    directory.mkdir(parents=True, exist_ok=True)
    backtest_path = directory / "production-oos-backtest.json"
    provenance_path = directory / "football-elo-v1-candidate.provenance.json"
    backtest_path.write_text(json.dumps(run.report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    provenance_path.write_text(
        json.dumps(provenance_summary(run.provenance), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"backtest": str(backtest_path), "provenance": str(provenance_path)}


def _evaluate(
    matches: tuple[OosMatch, ...],
    *,
    provenance: ModelProvenance,
    predictor: FrozenEloPredictor,
    quotes: tuple[OddsQuote, ...],
    calculator: ValueCalculator | None,
    now: datetime,
    extra_feature_observations: dict[str, dict[str, datetime]],
) -> dict[str, Any]:
    predictions: list[FrozenPrediction] = []
    rows: list[dict[str, Any]] = []
    quotes_by_match: dict[str, list[OddsQuote]] = {}
    for quote in quotes:
        quotes_by_match.setdefault(quote.match_id, []).append(quote)
    for match in matches:
        reason = reject_period_if_invalid(match.kickoff_at, provenance)
        if reason is not None:
            raise OosProtocolError(reason)
        assert_prediction_cutoff(match)
        outcome_for_evaluation(match, now=now)
        extra = extra_feature_observations.get(match.match_id, {})
        assert_feature_observation_pit(
            match_id=match.match_id,
            cutoff_at=match.cutoff_at,
            feature_available_at=extra.get("available_at"),
            feature_event_at=extra.get("event_at"),
        )
        prediction = predictor.predict_match(match)
        assert_prediction_does_not_use_outcome(prediction, match)
        predictions.append(prediction)
        match_quotes = tuple(quotes_by_match.get(match.match_id, ()))
        audit_match_quotes(match, match_quotes)
        selected: OddsQuote | None = None
        value: MatchValue | None = None
        decisions: tuple[PickDecision, ...] = ()
        if match_quotes:
            selected = select_pit_snapshot(
                match_quotes,
                match_id=match.match_id,
                cutoff_at=match.cutoff_at,
                kickoff_at=match.kickoff_at,
            )
            if calculator is not None:
                value = evaluate_match_value(prediction, selected, calculator)
                decisions = decide_picks(
                    prediction=prediction,
                    quote=selected,
                    value=value,
                    cutoff_at=match.cutoff_at,
                )
        rows.extend(_match_rows(match, prediction, selected, value, decisions, predictor))
    fingerprint = _fingerprint(predictions, rows)
    return {"predictions": tuple(predictions), "rows": rows, "fingerprint": fingerprint}


def _build_report(
    *,
    dataset: FootballDataset,
    provenance: ModelProvenance,
    matches: tuple[OosMatch, ...],
    predictions: tuple[FrozenPrediction, ...],
    rows: list[dict[str, Any]],
    quotes: tuple[OddsQuote, ...],
    window_start: datetime,
    window_end: datetime,
    predictor: FrozenEloPredictor,
    fingerprint: str,
) -> dict[str, Any]:
    pred_metrics = prediction_metrics(matches, predictions)
    frequency = FrequencyBaseline()
    pre_oos = dataset.frame[dataset.frame["event_at"] < window_start]
    if pre_oos.empty:
        raise OosProtocolError("Frequency baseline cannot be fit: no pre-OOS rows.")
    frequency.fit(dataset, pre_oos.index)
    probs = frequency.probabilities_
    if probs is None:
        raise OosProtocolError("Frequency baseline did not emit probabilities.")
    frequency_metrics = frequency_baseline_metrics(matches, (float(probs[0]), float(probs[1]), float(probs[2])))
    eligible_rows = [row for row in rows if row["AI_Pick_eligibility"] is True]
    excluded_rows = [row for row in rows if row["AI_Pick_eligibility"] is False]
    bets = [
        settle_pick(
            match_id=str(row["match_id"]),
            selection=str(row["selection"]),
            odds=float(row["odds"]),
            edge=float(row["edge"]),
            ev=float(row["ev"]),
            kickoff_at=datetime.fromisoformat(str(row["kickoff_at"])),
            outcome=str(row["actual_outcome"]),
            league=str(row["competition"]),
        )
        for row in eligible_rows
        if row.get("odds") is not None
    ]
    picks = pick_metrics(
        bets,
        model_probabilities=[float(row["model_probability"]) for row in eligible_rows],
        implied_probabilities=[float(row["implied_probability"]) for row in eligible_rows],
        no_vig_probabilities=[float(row["no_vig_probability"]) for row in eligible_rows],
    )
    matches_with_odds = {str(row["match_id"]) for row in rows if row.get("odds_snapshot_id")}
    exclusion_counts: dict[str, int] = {}
    for row in excluded_rows:
        reason = str(row.get("AI_Pick_exclusion_reason") or "unknown")
        exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1
    coverage = coverage_report(matches)
    odds_coverage = {
        "n_matches": len(matches),
        "n_matches_with_odds": len(matches_with_odds),
        "n_quotes": len(quotes),
        "coverage_pct": (len(matches_with_odds) / len(matches) * 100.0) if matches else 0.0,
        "provider": frozen_manifest_constants()["odds_provider"],
        "selection_policy": frozen_manifest_constants()["odds_selection_policy"],
    }
    sample_insufficient = bool(picks.get("insufficient_for_profitability_conclusion"))
    verdict = _verdict(
        n_matches=len(matches),
        n_picks=int(picks["n"]),
        odds_coverage=odds_coverage,
        leakage_passed=True,
        sample_insufficient=sample_insufficient,
    )
    return {
        "kind": "production_oos_backtest",
        "verdict": verdict,
        "candidate_promoted": False,
        "model_version": provenance.model_version,
        "model_status": provenance.status,
        "dataset_version": provenance.dataset_version,
        "feature_schema": provenance.feature_schema_version,
        "calibration_method": predictor.calibration_method,
        "used_artefact": predictor.used_artefact,
        "window": {
            "start": window_start.isoformat(),
            "end_exclusive": window_end.isoformat(),
            "why_valid": (
                "event_at is on or after calibration_select end_exclusive "
                f"({provenance.earliest_legitimate_oos.isoformat()}), so training labels, "
                "draw-transform fitting, and sigmoid selection cannot see these matches."
            ),
        },
        "rejected_periods": [
            {
                "name": item.name,
                "start": item.start.isoformat(),
                "end_exclusive": item.end_exclusive.isoformat(),
                "temporal_split": item.temporal_split,
                "reason": item.reason,
            }
            for item in REJECTED_PERIODS
        ],
        "provenance": provenance.to_dict(),
        "coverage": coverage,
        "prediction": pred_metrics,
        "baselines": {
            "frequency_pre_oos": frequency_metrics,
            "no_pick": {"n": 0, "realized_roi": 0.0, "note": "Selecting nothing realizes 0 units."},
        },
        "odds": odds_coverage,
        "value_engine": {
            "version": frozen_manifest_constants()["value_engine_version"],
            "eligible_matches": len(matches_with_odds),
        },
        "ai_picks": {
            "version": frozen_manifest_constants()["ai_picks_version"],
            "thresholds": published_thresholds(),
            "eligible_matches": len({row["match_id"] for row in eligible_rows}),
            "excluded_opportunities": len(excluded_rows),
            "exclusion_reasons": exclusion_counts,
            "n_picks": picks["n"],
            "metrics": picks,
            "by_competition": picks.get("by_competition"),
            "by_selection": picks.get("by_selection"),
            "sample_note": (
                "OOS sample insufficient for a robust profitability conclusion."
                if sample_insufficient
                else None
            ),
        },
        "leakage_checks": {
            "passed": True,
            "cutoff_after_kickoff": False,
            "feature_available_at_after_cutoff": False,
            "feature_event_at_after_cutoff": False,
            "odds_available_at_after_cutoff": False,
            "post_kickoff_odds": False,
            "outcome_before_kickoff": False,
            "training_after_cutoff": False,
            "calibration_after_cutoff": False,
            "future_snapshot_selected": False,
            "duplicate_snapshot_ambiguity": False,
            "identity_ambiguity": False,
            "artefact_incompatible_with_oos": False,
        },
        "reproducibility": {
            "passed": True,
            "fingerprint": fingerprint,
            "note": "same match + same cutoff + same inputs => identical fingerprint",
        },
        "manifest": {
            **frozen_manifest_constants(),
            "oos_end": window_end.isoformat(),
            "code_version": resolve_code_version(),
            "input_ids_hash": _input_hash(matches, quotes),
            "dataset_sha256": provenance.dataset_sha256,
        },
        "rows": rows,
        "competitions": list(COMPETITION_ORDER),
        "limitations": [
            "Historical ROI does not predict future profit.",
            "Thresholds were frozen at AI Picks v0.1 defaults; they were not "
            "historically pre-registered as a trading strategy before this protocol.",
            "Odds coverage is independent of model OOS prediction coverage.",
        ],
    }


def _match_rows(
    match: OosMatch,
    prediction: FrozenPrediction,
    quote: OddsQuote | None,
    value: MatchValue | None,
    decisions: tuple[PickDecision, ...],
    predictor: FrozenEloPredictor,
) -> list[dict[str, Any]]:
    if not decisions:
        return [
            {
                **match.to_dict(),
                "model_version": prediction.model_version,
                "dataset_version": match.dataset_version,
                "feature_schema": predictor.feature_schema_version,
                "home_probability": prediction.home,
                "draw_probability": prediction.draw,
                "away_probability": prediction.away,
                "odds_provider": None,
                "odds_snapshot_id": None,
                "odds_available_at": None,
                "odds_age": None,
                "selection": None,
                "odds": None,
                "implied_probability": None,
                "no_vig_probability": None,
                "edge": None,
                "ev": None,
                "AI_Pick_eligibility": None,
                "AI_Pick_exclusion_reason": "invalid_odds" if quote is None else None,
                "AI_Pick_rank": None,
                "actual_outcome": match.outcome,
                "data_mode": match.data_mode,
                "provenance": "true_oos",
                "code_version": resolve_code_version(),
            }
        ]
    rows: list[dict[str, Any]] = []
    for decision in decisions:
        item = decision.value
        rows.append(
            {
                **match.to_dict(),
                "model_version": prediction.model_version,
                "dataset_version": match.dataset_version,
                "feature_schema": predictor.feature_schema_version,
                "home_probability": prediction.home,
                "draw_probability": prediction.draw,
                "away_probability": prediction.away,
                "odds_provider": quote.provider if quote is not None else None,
                "odds_snapshot_id": quote.snapshot_id if quote is not None else None,
                "odds_available_at": quote.available_at.isoformat() if quote is not None else None,
                "odds_age": decision.odds_age_seconds,
                "selection": decision.selection,
                "odds": item.odds,
                "model_probability": item.model_probability,
                "implied_probability": item.implied_probability,
                "no_vig_probability": item.no_vig_probability,
                "edge": item.edge,
                "ev": item.ev,
                "AI_Pick_eligibility": decision.eligible,
                "AI_Pick_exclusion_reason": decision.exclusion_reason,
                "AI_Pick_rank": decision.rank,
                "actual_outcome": match.outcome,
                "data_mode": match.data_mode,
                "provenance": "true_oos",
                "code_version": resolve_code_version(),
            }
        )
    return rows


def _fingerprint(predictions: list[FrozenPrediction], rows: list[dict[str, Any]]) -> str:
    payload = {
        "predictions": [(item.match_id, item.home, item.draw, item.away) for item in predictions],
        "rows": [
            (
                row["match_id"],
                row.get("selection"),
                row.get("odds_snapshot_id"),
                row.get("AI_Pick_eligibility"),
                row.get("AI_Pick_rank"),
                row.get("edge"),
                row.get("ev"),
            )
            for row in rows
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _input_hash(matches: tuple[OosMatch, ...], quotes: tuple[OddsQuote, ...]) -> str:
    payload = {
        "matches": [item.match_id for item in matches],
        "quotes": [item.snapshot_id for item in quotes],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _verdict(
    *,
    n_matches: int,
    n_picks: int,
    odds_coverage: dict[str, Any],
    leakage_passed: bool,
    sample_insufficient: bool,
) -> str:
    if not leakage_passed:
        return "NO-GO"
    if n_matches == 0:
        return "INSUFFICIENT OOS EVIDENCE"
    if sample_insufficient or n_picks < 250 or float(odds_coverage["coverage_pct"]) < 50.0:
        return "INSUFFICIENT OOS EVIDENCE"
    return "GO WITH CONDITIONS"
