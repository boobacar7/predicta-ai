from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.ai_picks.config import AI_PICKS_VERSION
from app.backtesting.fixture_universe import LIVE_COMPETITIONS
from app.backtesting.persisted import (
    _evaluate_persisted,
    _verdict,
    catalog_from_parquet,
)
from app.backtesting.pilot import catalog_identity_exclusions
from app.backtesting.types import CatalogMatch
from app.core.clock import Clock
from app.odds.types import OddsSnapshot
from app.predictions.runtime import ensure_ml_on_path
from app.predictions.service import FootballPredictionService, build_football_prediction_service
from app.predictions.types import CANDIDATE_MODEL_VERSION
from app.value_engine.calculator import VALUE_ENGINE_VERSION

ensure_ml_on_path()
from predicta_ml.backtesting.metrics import classification_metrics  # noqa: E402
from predicta_ml.constants import CLASS_LABELS  # noqa: E402

EXPAND_CLOCK = datetime(2026, 9, 7, tzinfo=UTC)
EXPAND_PICKS_LIMIT = 2000
STAKE_POLICY = "fixed_unit_per_opportunity"
STAKE_NOTE = (
    "ROI uses 1 unit per opportunity/pick. A match with 2 AI Picks contributes 2 units "
    "to the denominator. This is the AI Picks 0.1 convention, not a per-match ROI."
)

EXPAND_WINDOWS: tuple[tuple[str, datetime, datetime], ...] = (
    ("end-2025-26-may", datetime(2026, 5, 1, tzinfo=UTC), datetime(2026, 5, 25, tzinfo=UTC)),
    ("persist-weekend-2026-08-21", datetime(2026, 8, 21, tzinfo=UTC), datetime(2026, 8, 25, tzinfo=UTC)),
    ("2026-27-following-matchweeks", datetime(2026, 8, 28, tzinfo=UTC), datetime(2026, 9, 7, tzinfo=UTC)),
)

# Descriptive analysis bins only. Not selection rules.
ODDS_BINS: tuple[tuple[str, float | None, float | None], ...] = (
    ("<1.50", None, 1.50),
    ("1.50-2", 1.50, 2.0),
    ("2-3", 2.0, 3.0),
    ("3-5", 3.0, 5.0),
    (">5", 5.0, None),
)
EDGE_BINS: tuple[tuple[str, float | None, float | None], ...] = (
    ("<5%", None, 0.05),
    ("5-10%", 0.05, 0.10),
    ("10-20%", 0.10, 0.20),
    ("20-30%", 0.20, 0.30),
    (">30%", 0.30, None),
)
EV_BINS: tuple[tuple[str, float | None, float | None], ...] = (
    ("0-0.15", 0.0, 0.15),
    ("0.15-0.40", 0.15, 0.40),
    ("0.40-1.00", 0.40, 1.0),
    (">=1.00", 1.0, None),
)
PROB_BINS: tuple[tuple[str, float | None, float | None], ...] = (
    ("<20%", None, 0.20),
    ("20-30%", 0.20, 0.30),
    ("30-40%", 0.30, 0.40),
    ("40-50%", 0.40, 0.50),
    (">50%", 0.50, None),
)
AGE_BINS_HOURS: tuple[tuple[str, float | None, float | None], ...] = (
    ("<0.25h", None, 0.25),
    ("0.25-2h", 0.25, 2.0),
    ("2-4h", 2.0, 4.0),
    ("4-24h", 4.0, 24.0),
    (">=24h", 24.0, None),
)


def expanded_catalog_from_parquet(
    dataset_path: Path,
    *,
    names: dict[str, tuple[str, str]] | None = None,
) -> tuple[CatalogMatch, ...]:
    catalog: list[CatalogMatch] = []
    seen: set[str] = set()
    for _name, start, end in EXPAND_WINDOWS:
        for match in catalog_from_parquet(
            dataset_path,
            window_start=start,
            window_end=end,
            names=names,
        ):
            if match.match_id in seen:
                continue
            if match.league not in LIVE_COMPETITIONS:
                continue
            seen.add(match.match_id)
            catalog.append(match)
    return tuple(sorted(catalog, key=lambda item: (item.kickoff_at, item.match_id)))


def run_persisted_expanded_pilot(
    *,
    catalog: tuple[CatalogMatch, ...],
    snapshots: tuple[OddsSnapshot, ...],
    predictions: FootballPredictionService | None = None,
    dataset_path: Path | None = None,
    registry_dir: Path | None = None,
    persist_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score the expanded PL + Ligue 1 historical windows. Does not tune thresholds."""

    clock = Clock(EXPAND_CLOCK)
    predictor = predictions
    if predictor is None:
        if dataset_path is None or registry_dir is None:
            raise ValueError("Expanded scoring needs a predictor or parquet + registry.")
        predictor = build_football_prediction_service(
            clock=clock,
            registry_dir=registry_dir,
            dataset_path=dataset_path,
            model_version=CANDIDATE_MODEL_VERSION,
        )
    exclusions = catalog_identity_exclusions(catalog)
    first = _evaluate_persisted(
        catalog,
        snapshots,
        predictor,
        clock,
        identity_exclusions=exclusions,
        picks_limit=EXPAND_PICKS_LIMIT,
        kind="persisted_live_expanded",
    )
    second = _evaluate_persisted(
        catalog,
        snapshots,
        predictor,
        clock,
        identity_exclusions=exclusions,
        picks_limit=EXPAND_PICKS_LIMIT,
        kind="persisted_live_expanded",
    )
    first["reproducibility"] = {
        "passed": first["fingerprint"] == second["fingerprint"],
        "first": first["fingerprint"],
        "second": second["fingerprint"],
    }
    first["persist"] = persist_meta or {}
    first["windows"] = [
        {"name": name, "start": start.isoformat(), "end": end.isoformat()}
        for name, start, end in EXPAND_WINDOWS
    ]
    first["stake_policy"] = STAKE_POLICY
    first["stake_note"] = STAKE_NOTE
    first["model_version"] = CANDIDATE_MODEL_VERSION
    first["value_engine_version"] = VALUE_ENGINE_VERSION
    first["ai_picks_version"] = AI_PICKS_VERSION
    first["model_performance"] = _enrich_model_performance(first, catalog, exclusions, predictor)
    first["multiple_picks"] = _multiple_picks(first, catalog, exclusions)
    first["descriptive_slices"] = _descriptive_slices(first)
    first["analytical_dataset"] = _analytical_dataset(first, catalog, exclusions)
    first["comparisons"] = _comparisons(first)
    first["verdict"] = _verdict(first)
    return first


def _enrich_model_performance(
    report: dict[str, Any],
    catalog: tuple[CatalogMatch, ...],
    exclusions: dict[str, str],
    predictions: FootballPredictionService,
) -> dict[str, Any]:
    base = dict(report["model_performance"])
    scored = [item for item in catalog if item.match_id not in exclusions]
    if not scored:
        return base
    labels = np.array([CLASS_LABELS.index(item.outcome) for item in scored], dtype=np.int64)
    proba = np.array([_probs(predictions, item) for item in scored], dtype=np.float64)
    metrics = classification_metrics(labels, proba)
    by_league: dict[str, dict[str, Any]] = {}
    for league in sorted({item.league for item in scored}):
        subset = [item for item in scored if item.league == league]
        y = np.array([CLASS_LABELS.index(item.outcome) for item in subset], dtype=np.int64)
        p = np.array([_probs(predictions, item) for item in subset], dtype=np.float64)
        grouped = classification_metrics(y, p)
        by_league[league] = {
            "n": grouped["n"],
            "accuracy": grouped["accuracy"],
            "log_loss": grouped["log_loss"],
            "brier_score": grouped["brier_score"],
            "ece": grouped["ece"],
        }
    predicted = metrics["predicted_distribution"]
    base.update(
        {
            "n": metrics["n"],
            "accuracy": metrics["accuracy"],
            "hit_rate": metrics["accuracy"],
            "hits": int(round(metrics["accuracy"] * metrics["n"])),
            "home": predicted.get("HOME", 0),
            "draw": predicted.get("DRAW", 0),
            "away": predicted.get("AWAY", 0),
            "log_loss": metrics["log_loss"],
            "brier_score": metrics["brier_score"],
            "ece": metrics["ece"],
            "calibration_ece": metrics["ece"],
            "per_class": metrics["per_class"],
            "by_competition": by_league,
            "confusion_matrix": metrics["confusion_matrix"],
            "confusion_matrix_labels": metrics["confusion_matrix_labels"],
            "note": "Model argmax accuracy on identity-matched matches. Not a betting ROI.",
        }
    )
    return base


def _probs(predictions: FootballPredictionService, match: CatalogMatch) -> list[float]:
    prediction = predictions.predict(match.match_id, match.kickoff_at)
    return [prediction.home_probability, prediction.draw_probability, prediction.away_probability]


def _multiple_picks(
    report: dict[str, Any],
    catalog: tuple[CatalogMatch, ...],
    exclusions: dict[str, str],
) -> dict[str, Any]:
    eligible = [item for item in catalog if item.match_id not in exclusions]
    picks_by_match: Counter[str] = Counter()
    for pick in report["fingerprint"]["picks"]:
        picks_by_match[str(pick[0])] += 1
    counts = Counter(picks_by_match.get(item.match_id, 0) for item in eligible)
    return {
        "matches_with_0": int(counts.get(0, 0)),
        "matches_with_1": int(counts.get(1, 0)),
        "matches_with_2": int(counts.get(2, 0)),
        "matches_with_3": int(counts.get(3, 0)),
        "eligible_matches": len(eligible),
        "picks": report["ai_picks_performance"]["n"],
        "stake_policy": STAKE_POLICY,
        "note": STAKE_NOTE,
    }


def _descriptive_slices(report: dict[str, Any]) -> dict[str, Any]:
    picks = _pick_rows(report)
    return {
        "purpose": "Descriptive only. Do not select the best bucket retroactively.",
        "competition": report["ai_picks_performance"].get("by_competition", {}),
        "selection": report["ai_picks_performance"].get("by_selection", {}),
        "odds": _bucket_metrics(picks, lambda row: float(row["odds"]), ODDS_BINS),
        "edge": _bucket_metrics(picks, lambda row: float(row["edge"]), EDGE_BINS),
        "ev": _bucket_metrics(picks, lambda row: float(row["ev"]), EV_BINS),
        "model_probability": _bucket_metrics(picks, lambda row: float(row["model_probability"]), PROB_BINS),
        "odds_age_hours": _bucket_metrics(picks, lambda row: float(row["odds_age_hours"]), AGE_BINS_HOURS),
    }


def _pick_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    by_match = {item["match_id"]: item for item in report["rows"]}
    rows: list[dict[str, Any]] = []
    for match_id, selection, rank in report["fingerprint"]["picks"]:
        match = by_match[match_id]
        key = selection.lower()
        odds = match[f"{key}_odds"]
        edge = match[f"{key}_edge"]
        ev = match[f"{key}_ev"]
        probability = match[f"{key}_probability" if key != "draw" else "draw_probability"]
        if key == "home":
            probability = match["home_probability"]
        elif key == "away":
            probability = match["away_probability"]
        else:
            probability = match["draw_probability"]
        age_seconds = match["odds_age_seconds"] or 0.0
        rows.append(
            {
                "match_id": match_id,
                "selection": selection,
                "rank": rank,
                "odds": odds,
                "edge": edge,
                "ev": ev,
                "model_probability": probability,
                "odds_age_hours": float(age_seconds) / 3600.0,
                "outcome": match["outcome"],
                "league": match["league"],
                "hit": selection == match["outcome"],
            }
        )
    return rows


def _bucket_metrics(
    rows: list[dict[str, Any]],
    value_fn: Any,
    bins: tuple[tuple[str, float | None, float | None], ...],
) -> dict[str, dict[str, Any]]:
    report: dict[str, dict[str, Any]] = {}
    for label, lower, upper in bins:
        items = [row for row in rows if _in_bin(float(value_fn(row)), lower, upper)]
        n = len(items)
        hits = sum(1 for item in items if item["hit"])
        profit = 0.0
        for item in items:
            profit += (float(item["odds"]) - 1.0) if item["hit"] else -1.0
        report[label] = {
            "n": n,
            "hits": hits,
            "hit_rate": None if n == 0 else hits / n,
            "theoretical_roi": None if n == 0 else profit / n,
            "note": "descriptive_only",
        }
    return report


def _in_bin(value: float, lower: float | None, upper: float | None) -> bool:
    if lower is not None and value < lower:
        return False
    if upper is not None and value >= upper:
        return False
    return True


def _analytical_dataset(
    report: dict[str, Any],
    catalog: tuple[CatalogMatch, ...],
    exclusions: dict[str, str],
) -> list[dict[str, Any]]:
    by_id = {item.match_id: item for item in catalog}
    pick_index = {(item[0], item[1]): item[2] for item in report["fingerprint"]["picks"]}
    eligible_ids = {item[0] for item in report["fingerprint"]["picks"]}
    dataset: list[dict[str, Any]] = []
    for row in report["rows"]:
        match = by_id[row["match_id"]]
        argmax = _argmax_from_row(row)
        for selection in ("HOME", "DRAW", "AWAY"):
            key = selection.lower()
            dataset.append(
                {
                    "match_id": match.match_id,
                    "competition": match.league,
                    "kickoff_at": match.kickoff_at.isoformat(),
                    "home_team": match.home_team,
                    "away_team": match.away_team,
                    "result": match.outcome,
                    "prediction": argmax,
                    "model_probability": row[
                        {"HOME": "home_probability", "DRAW": "draw_probability", "AWAY": "away_probability"}[selection]
                    ],
                    "odds": row[f"{key}_odds"],
                    "bookmaker": row["bookmaker"],
                    "provider": report["source"],
                    "snapshot_at": row["available_at"],
                    "odds_age": row["odds_age_seconds"],
                    "implied_probability": row[f"{key}_implied"],
                    "no_vig_probability": row[f"{key}_no_vig"],
                    "edge": row[f"{key}_edge"],
                    "EV": row[f"{key}_ev"],
                    "AI_Pick_eligibility": (match.match_id, selection) in pick_index,
                    "selection": selection,
                    "rank": pick_index.get((match.match_id, selection)),
                    "model_version": CANDIDATE_MODEL_VERSION,
                    "value_engine_version": VALUE_ENGINE_VERSION,
                    "ai_picks_version": AI_PICKS_VERSION,
                    "cutoff_at": match.kickoff_at.isoformat(),
                    "data_mode": "live",
                    "identity_exclusion": exclusions.get(match.match_id),
                    "ai_pick_match": match.match_id in eligible_ids,
                }
            )
    return dataset


def _argmax_from_row(row: dict[str, Any]) -> str | None:
    probs = {
        "HOME": row["home_probability"],
        "DRAW": row["draw_probability"],
        "AWAY": row["away_probability"],
    }
    if any(value is None for value in probs.values()):
        return None
    return max(probs, key=lambda name: (probs[name], name))


def _comparisons(report: dict[str, Any]) -> dict[str, Any]:
    model = report["model_performance"]
    value = report["value_performance"]
    picks = report["ai_picks_performance"]
    naive = report["baselines"]["naive_home"]
    return {
        "note": "MODEL PERFORMANCE ≠ VALUE STRATEGY PERFORMANCE ≠ AI PICKS PERFORMANCE.",
        "elo_argmax": {
            "n": model["n"],
            "hit_rate": model["hit_rate"],
            "roi": None,
            "home": model["home"],
            "draw": model["draw"],
            "away": model["away"],
        },
        "value_elo_argmax_settled": {
            "n": value["n"],
            "hit_rate": value["hit_rate"],
            "roi": value["theoretical_roi"],
            "home": value["home"],
            "draw": value["draw"],
            "away": value["away"],
        },
        "ai_picks": {
            "n": picks["n"],
            "hit_rate": picks["hit_rate"],
            "roi": picks["theoretical_roi"],
            "home": picks["home"],
            "draw": picks["draw"],
            "away": picks["away"],
        },
        "naive_home": {
            "n": naive["n"],
            "hit_rate": naive["hit_rate"],
            "roi": naive["theoretical_roi"],
            "home": naive["n"],
            "draw": 0,
            "away": 0,
        },
        "stake_policy": STAKE_POLICY,
    }
