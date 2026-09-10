from __future__ import annotations

from pathlib import Path

import numpy as np

from predicta_ml.features.dataset import load_football_dataset
from predicta_ml.models.boosting import LightGBMPredictor, XGBoostPredictor, tiny_boosting_params
from predicta_ml.models.elo import EloBaseline, elo_1x2_probabilities
from predicta_ml.models.frequency import FrequencyBaseline
from predicta_ml.models.poisson import PoissonBaseline, poisson_1x2_from_rates
from tests.support import make_toy_frame, write_frame_parquet


def test_frequency_baseline_uses_train_rates_only(tmp_path: Path) -> None:
    path = tmp_path / "toy.parquet"
    write_frame_parquet(path, make_toy_frame(30))
    dataset = load_football_dataset(path)
    train = dataset.frame.index[:20]
    holdout = dataset.frame.index[20:]
    model = FrequencyBaseline()
    model.fit(dataset, train)
    proba = model.predict_proba(dataset, holdout)
    expected = np.bincount(dataset.labels(train), minlength=3).astype(np.float64)
    expected /= expected.sum()
    assert np.allclose(proba, expected)
    assert np.allclose(proba.sum(axis=1), 1.0)


def test_elo_probabilities_sum_to_one() -> None:
    diffs = np.array([-200.0, 0.0, 80.0, 250.0])
    proba = elo_1x2_probabilities(diffs, home_advantage=80.0, scale=400.0, draw_base=0.25, draw_decay=1.0)
    assert proba.shape == (4, 3)
    assert np.allclose(proba.sum(axis=1), 1.0)
    assert proba[2, 0] > proba[2, 2]


def test_elo_and_poisson_fit_on_train_window(tmp_path: Path) -> None:
    path = tmp_path / "toy.parquet"
    write_frame_parquet(path, make_toy_frame(40))
    dataset = load_football_dataset(path)
    train = dataset.frame.index[:28]
    holdout = dataset.frame.index[28:]
    elo = EloBaseline()
    elo.fit(dataset, train)
    poisson = PoissonBaseline()
    poisson.fit(dataset, train)
    elo_p = elo.predict_clipped(dataset, holdout)
    poi_p = poisson.predict_clipped(dataset, holdout)
    assert np.allclose(elo_p.sum(axis=1), 1.0)
    assert np.allclose(poi_p.sum(axis=1), 1.0)


def test_poisson_matrix_is_valid_simplex() -> None:
    proba = poisson_1x2_from_rates(np.array([1.4, 0.8]), np.array([1.1, 1.6]), max_goals=8)
    assert np.allclose(proba.sum(axis=1), 1.0)
    assert np.all(proba > 0)


def test_boosting_is_deterministic_with_seed(tmp_path: Path) -> None:
    path = tmp_path / "toy.parquet"
    write_frame_parquet(path, make_toy_frame(48))
    dataset = load_football_dataset(path)
    train = dataset.frame.index[:36]
    holdout = dataset.frame.index[36:]
    params = tiny_boosting_params()
    first = XGBoostPredictor(params["xgboost"])
    second = XGBoostPredictor(params["xgboost"])
    first.fit(dataset, train)
    second.fit(dataset, train)
    assert np.allclose(first.predict_proba(dataset, holdout), second.predict_proba(dataset, holdout))
    lgb_a = LightGBMPredictor(params["lightgbm"])
    lgb_b = LightGBMPredictor(params["lightgbm"])
    lgb_a.fit(dataset, train)
    lgb_b.fit(dataset, train)
    assert np.allclose(lgb_a.predict_proba(dataset, holdout), lgb_b.predict_proba(dataset, holdout), atol=1e-10)
