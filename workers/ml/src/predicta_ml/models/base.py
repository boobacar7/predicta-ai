from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd

from predicta_ml.backtesting.metrics import clip_proba
from predicta_ml.features.dataset import FootballDataset


class FootballPredictor(ABC):
    name: str
    features: tuple[str, ...]

    def __init__(self) -> None:
        self.fitted_ = False
        self.train_period_: dict[str, str] | None = None

    @abstractmethod
    def fit(self, dataset: FootballDataset, index: pd.Index) -> None:
        raise NotImplementedError

    @abstractmethod
    def predict_proba(self, dataset: FootballDataset, index: pd.Index) -> np.ndarray:
        raise NotImplementedError

    def predict_clipped(self, dataset: FootballDataset, index: pd.Index) -> np.ndarray:
        return clip_proba(self.predict_proba(dataset, index))

    def hyperparameters(self) -> dict[str, Any]:
        return {}

    def mark_fitted(self, dataset: FootballDataset, index: pd.Index) -> None:
        times = dataset.frame.loc[index, "event_at"]
        self.fitted_ = True
        self.train_period_ = {
            "start": pd.Timestamp(times.min()).isoformat(),
            "end": pd.Timestamp(times.max()).isoformat(),
            "rows": str(int(len(index))),
        }
