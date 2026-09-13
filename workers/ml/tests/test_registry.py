from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from predicta_ml.constants import MODEL_VERSION, RANDOM_SEED
from predicta_ml.errors import DatasetError
from predicta_ml.features.dataset import load_football_dataset
from predicta_ml.models.frequency import FrequencyBaseline
from predicta_ml.registry.artifact import RegistryCard, load_registry, write_registry
from predicta_ml.robustness.checks import assert_no_target_in_features
from tests.support import make_toy_frame, write_frame_parquet


def test_registry_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "toy.parquet"
    write_frame_parquet(path, make_toy_frame(18))
    dataset = load_football_dataset(path)
    model = FrequencyBaseline()
    model.fit(dataset, dataset.frame.index[:12])
    card = RegistryCard(
        model_version=MODEL_VERSION,
        dataset_version=dataset.dataset_version,
        feature_schema_version=dataset.feature_schema_version,
        training_period={"start": "2024-03-01T00:00:00+00:00", "end": "2025-01-01T00:00:00+00:00"},
        validation_period={"start": "2025-01-01T00:00:00+00:00", "end": "2026-07-01T00:00:00+00:00"},
        test_period={"start": "2026-07-01T00:00:00+00:00", "end": "2026-09-10T02:30:01+00:00"},
        features=[],
        hyperparameters=model.hyperparameters(),
        metrics={"log_loss": 1.0},
        calibration_method="raw",
        random_seed=RANDOM_SEED,
        code_version="0.1.0+test",
        dataset_sha256=dataset.sha256,
        selected_model="frequency",
        ensemble_used=False,
        created_at=datetime(2026, 9, 10, tzinfo=UTC),
        notes=["unit-test"],
    )
    paths = write_registry(tmp_path, card=card, artefact={"predictors": {"frequency": model}})
    reloaded = load_registry(Path(paths["artefact"]))
    holdout = dataset.frame.index[12:]
    original = model.predict_proba(dataset, holdout)
    replay = reloaded["predictors"]["frequency"].predict_proba(dataset, holdout)
    assert np.allclose(original, replay)


def test_features_cannot_include_targets() -> None:
    assert_no_target_in_features(("home_elo_pre", "elo_diff"))
    with pytest.raises(DatasetError, match="Target columns"):
        assert_no_target_in_features(("home_elo_pre", "target"))
