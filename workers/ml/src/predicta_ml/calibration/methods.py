from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from predicta_ml.backtesting.metrics import clip_proba
from predicta_ml.constants import ISOTONIC_MIN_PER_CLASS, ISOTONIC_MIN_ROWS, RANDOM_SEED


@dataclass
class CalibrationOutcome:
    method: str
    fitted: bool
    reason: str
    probabilities: np.ndarray


class ProbabilityCalibrator:
    method: str = "raw"

    def fit(self, proba: np.ndarray, y_true: np.ndarray) -> None:
        return None

    def transform(self, proba: np.ndarray) -> np.ndarray:
        return clip_proba(proba)

    def hyperparameters(self) -> dict[str, Any]:
        return {"method": self.method}


class RawCalibrator(ProbabilityCalibrator):
    method = "raw"


class SigmoidCalibrator(ProbabilityCalibrator):
    """One-vs-rest Platt scaling, then L1 renormalization to a 1X2 simplex."""

    method = "sigmoid"

    def __init__(self) -> None:
        self.models_: list[LogisticRegression] = []

    def fit(self, proba: np.ndarray, y_true: np.ndarray) -> None:
        raw = clip_proba(proba)
        models: list[LogisticRegression] = []
        for klass in range(3):
            model = LogisticRegression(solver="lbfgs", random_state=RANDOM_SEED, max_iter=200)
            model.fit(raw[:, klass : klass + 1], (y_true == klass).astype(np.int64))
            models.append(model)
        self.models_ = models

    def transform(self, proba: np.ndarray) -> np.ndarray:
        if not self.models_:
            raise RuntimeError("Sigmoid calibrator is not fitted.")
        raw = clip_proba(proba)
        calibrated = np.column_stack(
            [model.predict_proba(raw[:, index : index + 1])[:, 1] for index, model in enumerate(self.models_)]
        )
        return clip_proba(calibrated)

    def hyperparameters(self) -> dict[str, Any]:
        return {"method": self.method, "strategy": "ovr_platt_then_renormalize"}


class IsotonicCalibrator(ProbabilityCalibrator):
    method = "isotonic"

    def __init__(self) -> None:
        self.models_: list[IsotonicRegression] = []

    def fit(self, proba: np.ndarray, y_true: np.ndarray) -> None:
        if not isotonic_is_eligible(y_true):
            raise ValueError("Not enough rows/class support for isotonic calibration.")
        raw = clip_proba(proba)
        models: list[IsotonicRegression] = []
        for klass in range(3):
            model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            model.fit(raw[:, klass], (y_true == klass).astype(np.float64))
            models.append(model)
        self.models_ = models

    def transform(self, proba: np.ndarray) -> np.ndarray:
        if not self.models_:
            raise RuntimeError("Isotonic calibrator is not fitted.")
        raw = clip_proba(proba)
        calibrated = np.column_stack([model.predict(raw[:, index]) for index, model in enumerate(self.models_)])
        return clip_proba(calibrated)

    def hyperparameters(self) -> dict[str, Any]:
        return {"method": self.method, "strategy": "ovr_isotonic_then_renormalize"}


def isotonic_is_eligible(y_true: np.ndarray) -> bool:
    if y_true.size < ISOTONIC_MIN_ROWS:
        return False
    counts = np.bincount(y_true, minlength=3)
    return bool(np.all(counts >= ISOTONIC_MIN_PER_CLASS))


def make_calibrator(method: str) -> ProbabilityCalibrator:
    if method == "raw":
        return RawCalibrator()
    if method == "sigmoid":
        return SigmoidCalibrator()
    if method == "isotonic":
        return IsotonicCalibrator()
    raise ValueError(f"Unknown calibration method '{method}'.")
