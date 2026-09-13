from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from predicta_ml.backtesting.metrics import classification_metrics, core_metrics
from predicta_ml.backtesting.value_metrics import (
    INSUFFICIENT_SAMPLE_N,
    SAMPLE_WARNING,
    SettledBet,
    max_drawdown_units,
    settle_decimal,
    strategy_metrics,
)
from predicta_ml.constants import CLASS_LABELS, COMPETITION_ORDER
from predicta_ml.oos.dataset import OosMatch
from predicta_ml.oos.predictions import FrozenPrediction, probability_matrix
from predicta_ml.oos.protocol import ROBUST_PROFITABILITY_N, SMALL_SAMPLE_N, STAKE_POLICY, STAKE_UNITS


def prediction_metrics(matches: tuple[OosMatch, ...], predictions: tuple[FrozenPrediction, ...]) -> dict[str, Any]:
    if len(matches) != len(predictions):
        raise ValueError("Prediction metrics require aligned matches and predictions.")
    y = np.array([item.y for item in matches], dtype=np.int64)
    proba = probability_matrix(predictions)
    metrics = classification_metrics(y, proba)
    by_competition = _group_prediction(matches, predictions, lambda item: item.competition)
    by_selection = metrics["per_class"]
    return {
        "n": metrics["n"],
        "accuracy": metrics["accuracy"],
        "log_loss": metrics["log_loss"],
        "brier_score": metrics["brier_score"],
        "ece": metrics["ece"],
        "per_class": by_selection,
        "confusion_matrix": metrics["confusion_matrix"],
        "confusion_matrix_labels": metrics["confusion_matrix_labels"],
        "by_competition": by_competition,
        "home_draw_away_calibration": {
            label: {
                "n": by_selection[label]["support"],
                "precision": by_selection[label]["precision"],
                "recall": by_selection[label]["recall"],
                "mean_predicted_probability": by_selection[label]["mean_predicted_probability"],
                "brier": by_selection[label]["brier"],
                "sample_warning": SAMPLE_WARNING if by_selection[label]["support"] < SMALL_SAMPLE_N else None,
            }
            for label in CLASS_LABELS
        },
        "sample_warning": SAMPLE_WARNING if metrics["n"] < SMALL_SAMPLE_N else None,
    }


def frequency_baseline_metrics(
    matches: tuple[OosMatch, ...],
    probabilities: tuple[float, float, float],
) -> dict[str, Any]:
    predictions = tuple(
        FrozenPrediction(
            match_id=item.match_id,
            home=probabilities[0],
            draw=probabilities[1],
            away=probabilities[2],
            model_version="frequency-baseline",
            calibration_method="raw",
            used_artefact=False,
        )
        for item in matches
    )
    return prediction_metrics(matches, predictions)


def pick_metrics(
    bets: Sequence[SettledBet],
    *,
    model_probabilities: Sequence[float] | None = None,
    implied_probabilities: Sequence[float] | None = None,
    no_vig_probabilities: Sequence[float] | None = None,
) -> dict[str, Any]:
    metrics = strategy_metrics(bets)
    ordered = sorted(bets, key=lambda item: (item.kickoff_at, item.match_id, item.selection))
    profits = [item.profit for item in ordered]
    metrics.update(
        {
            "longest_losing_streak": longest_losing_streak(ordered),
            "profit_factor": profit_factor(profits),
            "cumulative_pnl": _cumulative(profits),
            "average_model_probability": _mean(model_probabilities or ()),
            "average_implied_probability": _mean(implied_probabilities or ()),
            "average_no_vig_probability": _mean(no_vig_probabilities or ()),
            "realized_roi": metrics["theoretical_roi"],
            "theoretical_ev_aggregate": _mean(item.ev for item in ordered) if ordered else None,
            "stake": STAKE_UNITS,
            "stake_policy": STAKE_POLICY,
            "robust_profitability": len(ordered) >= ROBUST_PROFITABILITY_N,
            "insufficient_for_profitability_conclusion": len(ordered) < ROBUST_PROFITABILITY_N,
        }
    )
    if metrics["n"] < INSUFFICIENT_SAMPLE_N:
        metrics["sample_warning"] = SAMPLE_WARNING
    return metrics


def longest_losing_streak(bets: Sequence[SettledBet]) -> int:
    streak = 0
    longest = 0
    for item in bets:
        if item.selection == item.outcome:
            streak = 0
        else:
            streak += 1
            longest = max(longest, streak)
    return longest


def profit_factor(profits: Sequence[float]) -> float | None:
    gains = sum(item for item in profits if item > 0)
    losses = sum(-item for item in profits if item < 0)
    if losses == 0:
        return None if gains == 0 else float("inf")
    return float(gains / losses)


def settle_pick(
    *,
    match_id: str,
    selection: str,
    odds: float,
    edge: float,
    ev: float,
    kickoff_at: object,
    outcome: str,
    league: str,
) -> SettledBet:
    return SettledBet(
        match_id=match_id,
        selection=selection,
        odds=odds,
        edge=edge,
        ev=ev,
        kickoff_at=kickoff_at,  # type: ignore[arg-type]
        outcome=outcome,
        league=league,
        profit=settle_decimal(selection=selection, odds=odds, outcome=outcome),
        strategy="ai_picks_value",
    )


def drawdown_units(profits: Sequence[float]) -> float:
    return max_drawdown_units(profits)


def _group_prediction(
    matches: tuple[OosMatch, ...],
    predictions: tuple[FrozenPrediction, ...],
    key_fn: Any,
) -> dict[str, Any]:
    grouped_pred: dict[str, list[FrozenPrediction]] = {}
    grouped_matches: dict[str, list[OosMatch]] = {}
    for match, prediction in zip(matches, predictions, strict=True):
        key = str(key_fn(match))
        grouped_matches.setdefault(key, []).append(match)
        grouped_pred.setdefault(key, []).append(prediction)
    report: dict[str, Any] = {}
    keys = list(COMPETITION_ORDER) + sorted(set(grouped_matches) - set(COMPETITION_ORDER))
    for key in keys:
        items = grouped_matches.get(key)
        if not items:
            continue
        preds = tuple(grouped_pred[key])
        subset = tuple(items)
        y = np.array([item.y for item in subset], dtype=np.int64)
        proba = np.vstack([item.as_array() for item in preds])
        metrics = core_metrics(y, proba)
        report[key] = {
            "n": metrics["n"],
            "accuracy": metrics["accuracy"],
            "log_loss": metrics["log_loss"],
            "brier_score": metrics["brier_score"],
            "ece": metrics["ece"],
            "sample_warning": SAMPLE_WARNING if int(metrics["n"]) < SMALL_SAMPLE_N else None,
        }
    return report


def _cumulative(profits: Sequence[float]) -> list[float]:
    equity = 0.0
    series: list[float] = []
    for profit in profits:
        equity += float(profit)
        series.append(equity)
    return series


def _mean(values: Any) -> float | None:
    items = [float(item) for item in values if item is not None]
    if not items:
        return None
    return float(sum(items) / len(items))
