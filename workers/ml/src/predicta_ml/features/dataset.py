from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from predicta_ml.constants import (
    CLASS_INDEX,
    CLASS_LABELS,
    CUTOFF_POLICY,
    DATASET_VERSION,
    FEATURE_SCHEMA_VERSION,
    IDENTITY_COLUMNS,
    TARGET_COLUMNS,
)
from predicta_ml.errors import DatasetError
from predicta_ml.features.schema import FEATURE_SCHEMA


@dataclass(frozen=True)
class FootballDataset:
    frame: pd.DataFrame
    path: Path
    sha256: str
    dataset_version: str
    feature_schema_version: str

    def feature_matrix(self, columns: tuple[str, ...] | list[str], index: pd.Index | None = None) -> np.ndarray:
        subset = self.frame if index is None else self.frame.loc[index]
        missing = [name for name in columns if name not in subset.columns]
        if missing:
            raise DatasetError(f"Missing feature columns: {missing}")
        values = subset.loc[:, list(columns)].to_numpy(dtype=np.float64, copy=True)
        if np.isnan(values).any():
            raise DatasetError("Feature matrix contains NaN; dataset 0.3 is expected to have zero nulls.")
        return values

    def labels(self, index: pd.Index | None = None) -> np.ndarray:
        subset = self.frame if index is None else self.frame.loc[index]
        return subset["y"].to_numpy(dtype=np.int64, copy=True)


def load_football_dataset(path: Path) -> FootballDataset:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise DatasetError(f"Dataset parquet not found: {resolved}")
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    table = pq.read_table(resolved)
    frame = table.to_pandas()
    _validate_columns(frame)
    frame["event_at"] = pd.to_datetime(frame["event_at"], utc=True)
    if frame["event_at"].dt.tz is None:
        raise DatasetError("event_at must be timezone-aware UTC.")
    versions = set(frame["dataset_version"].astype(str))
    if versions != {DATASET_VERSION}:
        raise DatasetError(f"Refusing dataset versions {sorted(versions)}; expected {DATASET_VERSION}.")
    modes = set(frame["data_mode"].astype(str))
    if modes != {"live"}:
        raise DatasetError(f"Refusing data_mode={sorted(modes)}; live rows only.")
    policies = set(frame["cutoff_policy"].astype(str))
    if policies != {CUTOFF_POLICY}:
        raise DatasetError(f"Unexpected cutoff_policy={sorted(policies)}.")
    if int(frame["match_id"].duplicated().sum()) != 0:
        raise DatasetError("Duplicate match_id in dataset.")
    if int(frame.isna().to_numpy().sum()) != 0:
        raise DatasetError("Null values present; dataset 0.3 is specified as zero-null.")
    frame = frame.sort_values(["event_at", "match_id"], kind="mergesort").reset_index(drop=True)
    frame["target"] = frame["target"].astype(str)
    unknown = sorted(set(frame["target"]) - set(CLASS_LABELS))
    if unknown:
        raise DatasetError(f"Unknown target labels: {unknown}")
    frame["y"] = frame["target"].map(CLASS_INDEX).astype(np.int64)
    _assert_one_hot(frame)
    return FootballDataset(
        frame=frame,
        path=resolved,
        sha256=digest,
        dataset_version=DATASET_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
    )


def _validate_columns(frame: pd.DataFrame) -> None:
    required = list(IDENTITY_COLUMNS) + list(TARGET_COLUMNS) + list(FEATURE_SCHEMA)
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise DatasetError(f"Parquet is missing required columns: {missing}")


def _assert_one_hot(frame: pd.DataFrame) -> None:
    home = frame["home_win"].to_numpy()
    draw = frame["draw"].to_numpy()
    away = frame["away_win"].to_numpy()
    if not np.array_equal(home + draw + away, np.ones(len(frame), dtype=home.dtype)):
        raise DatasetError("1X2 one-hot rows must sum to 1.")
    mapped = np.column_stack([home, draw, away])
    expected = np.eye(3, dtype=mapped.dtype)[frame["y"].to_numpy()]
    if not np.array_equal(mapped, expected):
        raise DatasetError("target label does not match home_win/draw/away_win.")
