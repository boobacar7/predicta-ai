from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from predicta_ml.backtesting.metrics import clip_proba
from predicta_ml.constants import ELO_HOME_ADVANTAGE, ELO_K, ELO_SCALE
from predicta_ml.features.dataset import FootballDataset
from predicta_ml.features.schema import ELO_FEATURES
from predicta_ml.models.base import FootballPredictor


class EloBaseline(FootballPredictor):
    """Convert pre-match Elo into 1X2 probabilities.

    Expected home score uses the Data-layer Elo scale (400) and home advantage
    (+80). Draw mass is a two-parameter transform fit on the training window
    only: ``p_draw = clip(base * exp(-decay * |elo_diff| / 400))``. Remaining
    mass is split by the two-way expected score. No test labels are used.
    """

    name = "elo"
    features: tuple[str, ...] = ELO_FEATURES

    def __init__(self, home_advantage: float = ELO_HOME_ADVANTAGE, scale: float = ELO_SCALE) -> None:
        super().__init__()
        self.home_advantage = home_advantage
        self.scale = scale
        self.draw_base_: float = 0.25
        self.draw_decay_: float = 1.0

    def fit(self, dataset: FootballDataset, index: pd.Index) -> None:
        elo_diff = dataset.feature_matrix(("elo_diff",), index)[:, 0]
        self.fit_diffs(elo_diff, dataset.labels(index))
        self.mark_fitted(dataset, index)

    def fit_diffs(self, elo_diff: np.ndarray, y: np.ndarray) -> None:
        def loss(params: np.ndarray) -> float:
            proba = elo_1x2_probabilities(
                elo_diff,
                home_advantage=self.home_advantage,
                scale=self.scale,
                draw_base=float(params[0]),
                draw_decay=float(params[1]),
            )
            return _log_loss(y, proba)

        result = minimize(
            loss,
            x0=np.array([0.26, 0.8], dtype=np.float64),
            method="L-BFGS-B",
            bounds=((0.12, 0.40), (0.0, 4.0)),
        )
        self.draw_base_ = float(result.x[0])
        self.draw_decay_ = float(result.x[1])

    def predict_proba(self, dataset: FootballDataset, index: pd.Index) -> np.ndarray:
        elo_diff = dataset.feature_matrix(("elo_diff",), index)[:, 0]
        return self.predict_diffs(elo_diff)

    def predict_diffs(self, elo_diff: np.ndarray) -> np.ndarray:
        return elo_1x2_probabilities(
            elo_diff,
            home_advantage=self.home_advantage,
            scale=self.scale,
            draw_base=self.draw_base_,
            draw_decay=self.draw_decay_,
        )

    def hyperparameters(self) -> dict[str, Any]:
        return {
            "k": ELO_K,
            "home_advantage": self.home_advantage,
            "scale": self.scale,
            "draw_base": self.draw_base_,
            "draw_decay": self.draw_decay_,
            "source_elo_parameters": "dataset football-1x2-history-0.3 (k=20, initial=1500)",
        }


def elo_1x2_probabilities(
    elo_diff: np.ndarray,
    *,
    home_advantage: float,
    scale: float,
    draw_base: float,
    draw_decay: float,
) -> np.ndarray:
    expected_home = 1.0 / (1.0 + np.power(10.0, -((elo_diff + home_advantage) / scale)))
    draw = np.clip(draw_base * np.exp(-draw_decay * np.abs(elo_diff) / scale), 0.05, 0.42)
    home = (1.0 - draw) * expected_home
    away = (1.0 - draw) * (1.0 - expected_home)
    return clip_proba(np.column_stack([home, draw, away]))


def _log_loss(y: np.ndarray, proba: np.ndarray) -> float:
    clipped = clip_proba(proba)
    rows = np.arange(y.size)
    return float(-np.mean(np.log(clipped[rows, y])))
