from __future__ import annotations

import numpy as np

from predicta_ml.calibration.methods import IsotonicCalibrator, SigmoidCalibrator, isotonic_is_eligible
from predicta_ml.ensemble.average import ProbabilityEnsemble, should_keep_ensemble


def test_sigmoid_calibrator_does_not_use_test_labels() -> None:
    rng = np.random.default_rng(42)
    y_val = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2] * 8)
    logits = np.eye(3)[y_val] * 0.6 + rng.random(y_val.shape + (3,)) * 0.4
    y_test = np.array([2, 2, 2, 1, 1, 0, 0, 1])
    proba_test = rng.random((y_test.size, 3))
    calibrator = SigmoidCalibrator()
    calibrator.fit(logits, y_val)
    out = calibrator.transform(proba_test)
    assert out.shape == proba_test.shape
    assert np.allclose(out.sum(axis=1), 1.0)
    shifted = SigmoidCalibrator()
    shifted.fit(logits, (y_val + 1) % 3)
    other = shifted.transform(proba_test)
    assert not np.allclose(out, other)


def test_isotonic_requires_support() -> None:
    y = np.array([0, 1, 2, 0])
    assert isotonic_is_eligible(y) is False
    y_ok = np.repeat([0, 1, 2], 80)
    assert isotonic_is_eligible(y_ok) is True
    model = IsotonicCalibrator()
    proba = np.eye(3)[y_ok]
    model.fit(proba, y_ok)
    calibrated = model.transform(proba[:9])
    assert np.allclose(calibrated.sum(axis=1), 1.0)


def test_ensemble_kept_only_if_it_improves() -> None:
    assert should_keep_ensemble(ensemble_log_loss=0.90, best_single_log_loss=0.95) is True
    assert should_keep_ensemble(ensemble_log_loss=0.95, best_single_log_loss=0.95) is False
    mix = ProbabilityEnsemble(("a", "b"), np.array([0.5, 0.5]))
    combined = mix.combine(
        {
            "a": np.array([[0.6, 0.2, 0.2]]),
            "b": np.array([[0.2, 0.2, 0.6]]),
        }
    )
    assert np.allclose(combined, np.array([[0.4, 0.2, 0.4]]))
