from __future__ import annotations

from pathlib import Path

import pytest

from predicta_ml.constants import DATASET_VERSION
from predicta_ml.errors import DatasetError
from predicta_ml.features.audit import audit_dataset
from predicta_ml.features.dataset import load_football_dataset
from predicta_ml.features.schema import BOOSTING_FEATURES, FEATURE_SCHEMA, FEATURE_SPECS
from tests.support import make_toy_frame, write_frame_parquet


def test_feature_schema_has_27_named_specs() -> None:
    assert len(FEATURE_SCHEMA) == 27
    assert len(FEATURE_SPECS) == 27
    assert len(set(FEATURE_SCHEMA)) == 27
    assert "elo_available" not in BOOSTING_FEATURES
    assert len(BOOSTING_FEATURES) == 26


def test_load_rejects_wrong_dataset_version(tmp_path: Path) -> None:
    frame = make_toy_frame(12)
    frame["dataset_version"] = "football-1x2-history-0.2"
    path = tmp_path / "wrong.parquet"
    write_frame_parquet(path, frame)
    with pytest.raises(DatasetError, match="Refusing dataset versions"):
        load_football_dataset(path)


def test_audit_reports_zero_nulls_and_used_features(tmp_path: Path) -> None:
    path = tmp_path / "toy.parquet"
    write_frame_parquet(path, make_toy_frame(24))
    dataset = load_football_dataset(path)
    report = audit_dataset(dataset)
    assert report["dataset_version"] == DATASET_VERSION
    assert report["feature_count"] == 27
    assert report["null_rate_total"] == 0.0
    assert report["features_used"]["frequency"] == []
    assert "home_elo_pre" in report["features_used"]["elo"]
    assert report["unused_schema_features"] == ["elo_available"]
