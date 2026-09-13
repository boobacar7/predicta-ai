from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from predicta_ml.features.dataset import FootballDataset
from predicta_ml.models.base import FootballPredictor


class FrequencyBaseline(FootballPredictor):
    """Historical 1X2 frequencies estimated on the training window only."""

    name = "frequency"
    features: tuple[str, ...] = ()

    def __init__(self) -> None:
        super().__init__()
        self.probabilities_: np.ndarray | None = None

    def fit(self, dataset: FootballDataset, index: pd.Index) -> None:
        labels = dataset.labels(index)
        counts = np.bincount(labels, minlength=3).astype(np.float64)
        total = counts.sum()
        if total <= 0:
            raise ValueError("Frequency baseline cannot fit an empty training window.")
        self.probabilities_ = counts / total
        self.mark_fitted(dataset, index)

    def predict_proba(self, dataset: FootballDataset, index: pd.Index) -> np.ndarray:
        if self.probabilities_ is None:
            raise RuntimeError("Frequency baseline is not fitted.")
        return np.repeat(self.probabilities_[None, :], len(index), axis=0)

    def hyperparameters(self) -> dict[str, Any]:
        probs = self.probabilities_
        if probs is None:
            return {}
        return {"p_home": float(probs[0]), "p_draw": float(probs[1]), "p_away": float(probs[2])}
