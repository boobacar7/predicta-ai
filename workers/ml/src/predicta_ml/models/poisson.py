from __future__ import annotations

from math import factorial
from typing import Any

import numpy as np
import pandas as pd

from predicta_ml.backtesting.metrics import clip_proba
from predicta_ml.constants import POISSON_MAX_GOALS
from predicta_ml.features.dataset import FootballDataset
from predicta_ml.features.schema import POISSON_FEATURES
from predicta_ml.models.base import FootballPredictor


class PoissonBaseline(FootballPredictor):
    """Independent Poisson 1X2 from PIT rolling goal rates.

    Target match scores are not in the dataset, so λ is reconstructed from the
    last-5 goals-for / goals-against windows. Unavailable windows fall back to
    the training-window mean rate. A single home-advantage multiplier is fit
    on training 1X2 log-loss. No future rows are used.
    """

    name = "poisson"
    features: tuple[str, ...] = POISSON_FEATURES

    def __init__(self, max_goals: int = POISSON_MAX_GOALS) -> None:
        super().__init__()
        self.max_goals = max_goals
        self.home_advantage_: float = 1.10
        self.fallback_home_for_: float = 1.3
        self.fallback_home_against_: float = 1.3
        self.fallback_away_for_: float = 1.2
        self.fallback_away_against_: float = 1.3

    def fit(self, dataset: FootballDataset, index: pd.Index) -> None:
        rates = self._rates(dataset, index, fitted=False)
        y = dataset.labels(index)
        best_adv = 1.10
        best_loss = float("inf")
        for home_advantage in np.linspace(0.90, 1.35, 19):
            proba = poisson_1x2_from_rates(
                rates["lambda_home"] * float(home_advantage),
                rates["lambda_away"],
                max_goals=self.max_goals,
            )
            loss = _log_loss(y, proba)
            if loss < best_loss:
                best_loss = loss
                best_adv = float(home_advantage)
        self.home_advantage_ = best_adv
        self.fallback_home_for_ = rates["fallback_home_for"]
        self.fallback_home_against_ = rates["fallback_home_against"]
        self.fallback_away_for_ = rates["fallback_away_for"]
        self.fallback_away_against_ = rates["fallback_away_against"]
        self.mark_fitted(dataset, index)

    def predict_proba(self, dataset: FootballDataset, index: pd.Index) -> np.ndarray:
        rates = self._rates(dataset, index, fitted=True)
        return poisson_1x2_from_rates(
            rates["lambda_home"] * self.home_advantage_,
            rates["lambda_away"],
            max_goals=self.max_goals,
        )

    def hyperparameters(self) -> dict[str, Any]:
        return {
            "max_goals": self.max_goals,
            "home_advantage": self.home_advantage_,
            "window": 5,
            "fallback_home_for": self.fallback_home_for_,
            "fallback_home_against": self.fallback_home_against_,
            "fallback_away_for": self.fallback_away_for_,
            "fallback_away_against": self.fallback_away_against_,
        }

    def _rates(self, dataset: FootballDataset, index: pd.Index, *, fitted: bool) -> dict[str, Any]:
        matrix = dataset.feature_matrix(self.features, index)
        home_for = matrix[:, 0]
        home_against = matrix[:, 1]
        away_for = matrix[:, 2]
        away_against = matrix[:, 3]
        home_ok = matrix[:, 4] >= 0.5
        away_ok = matrix[:, 5] >= 0.5
        if fitted:
            fallback_home_for = self.fallback_home_for_
            fallback_home_against = self.fallback_home_against_
            fallback_away_for = self.fallback_away_for_
            fallback_away_against = self.fallback_away_against_
        else:
            fallback_home_for = _mean_rate(home_for, home_ok)
            fallback_home_against = _mean_rate(home_against, home_ok)
            fallback_away_for = _mean_rate(away_for, away_ok)
            fallback_away_against = _mean_rate(away_against, away_ok)
        home_attack = np.where(home_ok, home_for / 5.0, fallback_home_for)
        home_def = np.where(home_ok, home_against / 5.0, fallback_home_against)
        away_attack = np.where(away_ok, away_for / 5.0, fallback_away_for)
        away_def = np.where(away_ok, away_against / 5.0, fallback_away_against)
        lambda_home = np.clip(0.5 * (home_attack + away_def), 0.20, 4.5)
        lambda_away = np.clip(0.5 * (away_attack + home_def), 0.20, 4.5)
        return {
            "lambda_home": lambda_home,
            "lambda_away": lambda_away,
            "fallback_home_for": fallback_home_for,
            "fallback_home_against": fallback_home_against,
            "fallback_away_for": fallback_away_for,
            "fallback_away_against": fallback_away_against,
        }


def poisson_1x2_from_rates(lambda_home: np.ndarray, lambda_away: np.ndarray, *, max_goals: int) -> np.ndarray:
    home_pmf = _poisson_pmf_matrix(lambda_home, max_goals)
    away_pmf = _poisson_pmf_matrix(lambda_away, max_goals)
    joint = home_pmf[:, :, None] * away_pmf[:, None, :]
    home_win = np.tril(np.ones((max_goals + 1, max_goals + 1)), -1)
    draw = np.eye(max_goals + 1)
    away_win = np.triu(np.ones((max_goals + 1, max_goals + 1)), 1)
    p_home = (joint * home_win[None, :, :]).sum(axis=(1, 2))
    p_draw = (joint * draw[None, :, :]).sum(axis=(1, 2))
    p_away = (joint * away_win[None, :, :]).sum(axis=(1, 2))
    return clip_proba(np.column_stack([p_home, p_draw, p_away]))


def _poisson_pmf_matrix(rates: np.ndarray, max_goals: int) -> np.ndarray:
    ks = np.arange(max_goals + 1, dtype=np.float64)
    fact = np.array([factorial(int(k)) for k in ks], dtype=np.float64)
    rates = np.asarray(rates, dtype=np.float64)[:, None]
    pmf = np.exp(-rates) * np.power(rates, ks) / fact
    return np.asarray(pmf, dtype=np.float64)


def _mean_rate(counts: np.ndarray, available: np.ndarray) -> float:
    if not np.any(available):
        return 1.3
    return float(np.mean(counts[available] / 5.0))


def _log_loss(y: np.ndarray, proba: np.ndarray) -> float:
    clipped = clip_proba(proba)
    rows = np.arange(y.size)
    return float(-np.mean(np.log(clipped[rows, y])))
