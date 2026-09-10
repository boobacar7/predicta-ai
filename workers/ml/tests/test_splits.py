from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from predicta_ml.backtesting.splits import build_temporal_split_plan
from predicta_ml.constants import FINAL_TEST_START, FINAL_TRAIN_END
from predicta_ml.features.dataset import load_football_dataset
from predicta_ml.robustness.checks import run_robustness_checks
from tests.support import make_covering_frame, write_frame_parquet


def test_walk_forward_never_trains_on_future_rows(tmp_path: Path) -> None:
    path = tmp_path / "cover.parquet"
    write_frame_parquet(path, make_covering_frame())
    dataset = load_football_dataset(path)
    plan = build_temporal_split_plan(dataset)
    assert len(plan.folds) == 3
    for fold in plan.folds:
        train_max = dataset.frame.loc[fold.train.index, "event_at"].max()
        val_min = dataset.frame.loc[fold.validation.index, "event_at"].min()
        assert val_min >= fold.train.end
        assert train_max < val_min
        assert set(fold.train.index).isdisjoint(fold.validation.index)
    test_min = dataset.frame.loc[plan.test.index, "event_at"].min()
    select_max = dataset.frame.loc[plan.calibration_select.index, "event_at"].max()
    assert test_min >= FINAL_TEST_START
    assert select_max < FINAL_TEST_START
    assert dataset.frame.loc[plan.final_train.index, "event_at"].max() < FINAL_TRAIN_END
    robustness = run_robustness_checks(dataset, plan)
    assert robustness["ok"] is True
    assert robustness["random_split"] is False


def test_split_dates_are_documented(tmp_path: Path) -> None:
    path = tmp_path / "cover.parquet"
    write_frame_parquet(path, make_covering_frame())
    plan = build_temporal_split_plan(load_football_dataset(path))
    payload = plan.to_dict()
    assert payload["random_split"] is False
    assert plan.folds[0].train.end == datetime(2025, 1, 1, tzinfo=UTC)
    assert plan.folds[0].validation.end == datetime(2025, 7, 1, tzinfo=UTC)
    assert plan.folds[1].train.end == datetime(2025, 7, 1, tzinfo=UTC)
    assert plan.folds[2].train.end == datetime(2026, 1, 1, tzinfo=UTC)
    assert plan.test.start == datetime(2026, 7, 1, tzinfo=UTC)
