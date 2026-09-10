from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pandas as pd

from predicta_ml.constants import (
    CALIBRATION_FIT_END,
    FINAL_TEST_START,
    FINAL_TRAIN_END,
    WALK_FORWARD_BOUNDS,
)
from predicta_ml.errors import TemporalLeakageError
from predicta_ml.features.dataset import FootballDataset


@dataclass(frozen=True)
class TemporalWindow:
    name: str
    start: datetime
    end: datetime
    index: pd.Index

    @property
    def size(self) -> int:
        return int(len(self.index))

    def to_dict(self) -> dict[str, str | int]:
        return {
            "name": self.name,
            "start": _iso(self.start),
            "end_exclusive": _iso(self.end),
            "rows": self.size,
        }


@dataclass(frozen=True)
class WalkForwardFold:
    name: str
    train: TemporalWindow
    validation: TemporalWindow

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "train": self.train.to_dict(), "validation": self.validation.to_dict()}


@dataclass(frozen=True)
class TemporalSplitPlan:
    folds: tuple[WalkForwardFold, ...]
    final_train: TemporalWindow
    calibration_fit: TemporalWindow
    calibration_select: TemporalWindow
    test: TemporalWindow

    def to_dict(self) -> dict[str, object]:
        return {
            "protocol": "expanding_walk_forward_plus_held_out_temporal_test",
            "random_split": False,
            "folds": [fold.to_dict() for fold in self.folds],
            "final_train": self.final_train.to_dict(),
            "calibration_fit": self.calibration_fit.to_dict(),
            "calibration_select": self.calibration_select.to_dict(),
            "test": self.test.to_dict(),
        }


def build_temporal_split_plan(dataset: FootballDataset) -> TemporalSplitPlan:
    frame = dataset.frame
    event_at = frame["event_at"]
    folds: list[WalkForwardFold] = []
    for name, train_start, train_end, val_end in WALK_FORWARD_BOUNDS:
        train = _window(frame, event_at, name=f"{name}_train", start=train_start, end=train_end)
        validation = _window(frame, event_at, name=f"{name}_validation", start=train_end, end=val_end)
        _assert_forward(train, validation)
        folds.append(WalkForwardFold(name=name, train=train, validation=validation))
    final_train = _window(frame, event_at, name="final_train", start=_min_start(frame), end=FINAL_TRAIN_END)
    calibration_fit = _window(
        frame,
        event_at,
        name="calibration_fit",
        start=FINAL_TRAIN_END,
        end=CALIBRATION_FIT_END,
    )
    calibration_select = _window(
        frame,
        event_at,
        name="calibration_select",
        start=CALIBRATION_FIT_END,
        end=FINAL_TEST_START,
    )
    test = _window(
        frame,
        event_at,
        name="final_test",
        start=FINAL_TEST_START,
        end=_max_end(frame),
    )
    _assert_forward(final_train, calibration_fit)
    _assert_forward(calibration_fit, calibration_select)
    _assert_forward(calibration_select, test)
    disjoint = (
        set(final_train.index)
        | set(calibration_fit.index)
        | set(calibration_select.index)
        | set(test.index)
    )
    if len(disjoint) != len(frame):
        raise TemporalLeakageError("Temporal partitions do not cover the dataset disjointly.")
    return TemporalSplitPlan(
        folds=tuple(folds),
        final_train=final_train,
        calibration_fit=calibration_fit,
        calibration_select=calibration_select,
        test=test,
    )


def _window(frame: pd.DataFrame, event_at: pd.Series, *, name: str, start: datetime, end: datetime) -> TemporalWindow:
    mask = (event_at >= start) & (event_at < end)
    index = frame.index[mask]
    if index.size == 0:
        raise TemporalLeakageError(f"Window '{name}' is empty.")
    window_times = event_at.loc[index]
    if window_times.min() < start or window_times.max() >= end:
        raise TemporalLeakageError(f"Window '{name}' leaked rows outside [{start.isoformat()}, {end.isoformat()}).")
    return TemporalWindow(name=name, start=start, end=end, index=index)


def _assert_forward(earlier: TemporalWindow, later: TemporalWindow) -> None:
    if earlier.size == 0 or later.size == 0:
        raise TemporalLeakageError("A temporal window is empty.")
    earlier_max = earlier.end
    if later.start < earlier_max and later.start != earlier.end:
        raise TemporalLeakageError(f"{later.name} overlaps {earlier.name}.")
    later_min_ts = later.start
    if later_min_ts < earlier.end:
        raise TemporalLeakageError(f"{later.name} starts before {earlier.name} ends.")


def _min_start(frame: pd.DataFrame) -> datetime:
    value = pd.Timestamp(frame["event_at"].min()).tz_convert(UTC).to_pydatetime()
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def _max_end(frame: pd.DataFrame) -> datetime:
    value = pd.Timestamp(frame["event_at"].max()).tz_convert(UTC).to_pydatetime()
    return value + timedelta(seconds=1)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()
