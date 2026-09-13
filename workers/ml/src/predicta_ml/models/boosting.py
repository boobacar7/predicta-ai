from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier

from predicta_ml.constants import LIGHTGBM_PARAMS, RANDOM_SEED, XGBOOST_PARAMS
from predicta_ml.features.dataset import FootballDataset
from predicta_ml.features.schema import BOOSTING_FEATURES
from predicta_ml.models.base import FootballPredictor


class XGBoostPredictor(FootballPredictor):
    name = "xgboost"
    features: tuple[str, ...] = BOOSTING_FEATURES

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.params: dict[str, Any] = dict(XGBOOST_PARAMS if params is None else params)
        self.model_: XGBClassifier | None = None

    def fit(self, dataset: FootballDataset, index: pd.Index) -> None:
        features = dataset.feature_matrix(self.features, index)
        labels = dataset.labels(index)
        model = XGBClassifier(**self.params)
        model.fit(features, labels)
        self.model_ = model
        self.mark_fitted(dataset, index)

    def predict_proba(self, dataset: FootballDataset, index: pd.Index) -> np.ndarray:
        if self.model_ is None:
            raise RuntimeError("XGBoost model is not fitted.")
        features = dataset.feature_matrix(self.features, index)
        return np.asarray(self.model_.predict_proba(features), dtype=np.float64)

    def hyperparameters(self) -> dict[str, Any]:
        return dict(self.params)


class LightGBMPredictor(FootballPredictor):
    name = "lightgbm"
    features: tuple[str, ...] = BOOSTING_FEATURES

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.params: dict[str, Any] = dict(LIGHTGBM_PARAMS if params is None else params)
        self.model_: LGBMClassifier | None = None

    def fit(self, dataset: FootballDataset, index: pd.Index) -> None:
        features = dataset.feature_matrix(self.features, index)
        labels = dataset.labels(index)
        model = LGBMClassifier(**self.params)
        model.fit(features, labels)
        self.model_ = model
        self.mark_fitted(dataset, index)

    def predict_proba(self, dataset: FootballDataset, index: pd.Index) -> np.ndarray:
        if self.model_ is None:
            raise RuntimeError("LightGBM model is not fitted.")
        features = dataset.feature_matrix(self.features, index)
        return np.asarray(self.model_.predict_proba(features), dtype=np.float64)

    def hyperparameters(self) -> dict[str, Any]:
        return dict(self.params)


def tiny_boosting_params() -> dict[str, Any]:
    """Deterministic tiny trees for unit tests only. Not used in the benchmark."""
    return {
        "xgboost": {
            **XGBOOST_PARAMS,
            "n_estimators": 8,
            "max_depth": 2,
            "learning_rate": 0.3,
            "random_state": RANDOM_SEED,
        },
        "lightgbm": {
            **LIGHTGBM_PARAMS,
            "n_estimators": 8,
            "num_leaves": 4,
            "max_depth": 2,
            "learning_rate": 0.3,
            "random_state": RANDOM_SEED,
            "min_child_samples": 1,
        },
    }
