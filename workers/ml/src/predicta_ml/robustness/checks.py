from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from predicta_ml.backtesting.splits import TemporalSplitPlan
from predicta_ml.constants import CUTOFF_POLICY, DATASET_VERSION, FEATURE_SCHEMA_VERSION, PACKAGE_VERSION, RANDOM_SEED
from predicta_ml.errors import DatasetError, TemporalLeakageError
from predicta_ml.features.dataset import FootballDataset
from predicta_ml.features.schema import FEATURE_SCHEMA


def run_robustness_checks(dataset: FootballDataset, plan: TemporalSplitPlan) -> dict[str, Any]:
    frame = dataset.frame
    issues: list[str] = []
    if dataset.dataset_version != DATASET_VERSION:
        issues.append("dataset_version mismatch")
    if dataset.feature_schema_version != FEATURE_SCHEMA_VERSION:
        issues.append("feature_schema_version mismatch")
    if int(frame["match_id"].duplicated().sum()) != 0:
        issues.append("duplicate match_id")
    if int(frame.isna().to_numpy().sum()) != 0:
        issues.append("null values")
    if not bool(frame["event_at"].is_monotonic_increasing):
        issues.append("event_at is not chronological")
    future_looking = [name for name in frame.columns if name.endswith("_post") or name.startswith("future_")]
    if future_looking:
        issues.append(f"future-looking columns: {future_looking}")
    leaked_features = [name for name in FEATURE_SCHEMA if name in {"home_win", "draw", "away_win", "target"}]
    if leaked_features:
        issues.append("target leaked into feature schema")
    _assert_windows(frame, plan)
    if issues:
        raise TemporalLeakageError("; ".join(issues))
    return {
        "ok": True,
        "dataset_version": DATASET_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "cutoff_policy": CUTOFF_POLICY,
        "duplicate_match_ids": 0,
        "nulls": 0,
        "future_looking_columns": [],
        "random_split": False,
        "random_seed": RANDOM_SEED,
        "chronological": True,
        "train_before_validation_before_test": True,
        "elo_available_constant": bool((frame["elo_available"] == 1).all()),
        "code_version": resolve_code_version(),
    }


def assert_no_target_in_features(columns: tuple[str, ...]) -> None:
    forbidden = {"target", "home_win", "draw", "away_win", "y"}
    overlap = forbidden.intersection(columns)
    if overlap:
        raise DatasetError(f"Target columns used as features: {sorted(overlap)}")


def resolve_code_version() -> str:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            try:
                sha = subprocess.check_output(
                    ["git", "-C", str(parent), "rev-parse", "--short", "HEAD"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
            except (OSError, subprocess.CalledProcessError):
                break
            if sha:
                return f"{PACKAGE_VERSION}+{sha}"
            break
    return PACKAGE_VERSION


def _assert_windows(frame: pd.DataFrame, plan: TemporalSplitPlan) -> None:
    pairs = [
        (plan.final_train, plan.calibration_fit),
        (plan.calibration_fit, plan.calibration_select),
        (plan.calibration_select, plan.test),
    ]
    for earlier, later in pairs:
        earlier_max = pd.Timestamp(frame.loc[earlier.index, "event_at"].max())
        later_min = pd.Timestamp(frame.loc[later.index, "event_at"].min())
        if later_min < earlier_max:
            raise TemporalLeakageError(f"{later.name} contains a kickoff before {earlier.name} ended.")
        if set(earlier.index).intersection(later.index):
            raise TemporalLeakageError(f"{earlier.name} and {later.name} share rows.")
    for fold in plan.folds:
        train_max = pd.Timestamp(frame.loc[fold.train.index, "event_at"].max())
        val_min = pd.Timestamp(frame.loc[fold.validation.index, "event_at"].min())
        if val_min < train_max:
            raise TemporalLeakageError(f"{fold.name} validation starts before train ends.")
        if set(fold.train.index).intersection(fold.validation.index):
            raise TemporalLeakageError(f"{fold.name} train/validation overlap.")


def seed_everything(seed: int = RANDOM_SEED) -> None:
    np.random.seed(seed)
