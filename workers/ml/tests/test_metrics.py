from __future__ import annotations

import numpy as np

from predicta_ml.backtesting.metrics import classification_metrics, clip_proba, expected_calibration_error


def test_clip_proba_renormalizes() -> None:
    raw = np.array([[0.9, 0.9, 0.9], [0.0, 0.0, 0.0]], dtype=np.float64)
    clipped = clip_proba(raw)
    assert np.allclose(clipped.sum(axis=1), 1.0)


def test_metrics_on_perfect_predictions() -> None:
    y = np.array([0, 1, 2], dtype=np.int64)
    proba = np.eye(3, dtype=np.float64)
    metrics = classification_metrics(y, proba)
    assert metrics["accuracy"] == 1.0
    assert metrics["log_loss"] < 1e-12
    assert metrics["brier_score"] < 1e-12
    assert expected_calibration_error(y, proba) < 1e-12
    assert metrics["confusion_matrix"] == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
