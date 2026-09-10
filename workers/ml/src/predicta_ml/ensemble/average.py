from __future__ import annotations

from typing import Any

import numpy as np

from predicta_ml.backtesting.metrics import clip_proba
from predicta_ml.constants import ENSEMBLE_MIN_LOG_LOSS_GAIN


class ProbabilityEnsemble:
    name = "ensemble"

    def __init__(self, members: tuple[str, ...], weights: np.ndarray) -> None:
        if len(members) != len(weights):
            raise ValueError("Ensemble members and weights must align.")
        total = float(np.sum(weights))
        if total <= 0:
            raise ValueError("Ensemble weights must be positive.")
        self.members = members
        self.weights = weights / total

    def combine(self, member_proba: dict[str, np.ndarray]) -> np.ndarray:
        stacked = np.stack([member_proba[name] for name in self.members], axis=0)
        mixed = np.tensordot(self.weights, stacked, axes=(0, 0))
        return clip_proba(mixed)

    def hyperparameters(self) -> dict[str, Any]:
        return {
            "members": list(self.members),
            "weights": [float(value) for value in self.weights],
            "rule": "inverse_validation_log_loss",
        }


def inverse_log_loss_weights(log_losses: dict[str, float]) -> np.ndarray:
    raw = np.array([1.0 / max(value, 1e-6) for value in log_losses.values()], dtype=np.float64)
    return raw / raw.sum()


def should_keep_ensemble(*, ensemble_log_loss: float, best_single_log_loss: float) -> bool:
    return ensemble_log_loss < (best_single_log_loss - ENSEMBLE_MIN_LOG_LOSS_GAIN)
