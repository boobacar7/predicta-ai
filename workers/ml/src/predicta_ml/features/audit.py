from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from predicta_ml.constants import CLASS_LABELS, FEATURE_SCHEMA_VERSION
from predicta_ml.features.dataset import FootballDataset
from predicta_ml.features.schema import BOOSTING_FEATURES, ELO_FEATURES, FEATURE_SCHEMA, FEATURE_SPECS, POISSON_FEATURES


def audit_dataset(dataset: FootballDataset) -> dict[str, Any]:
    frame = dataset.frame
    feature_block = frame.loc[:, list(FEATURE_SCHEMA)]
    distributions: dict[str, Any] = {}
    for spec in FEATURE_SPECS:
        series = feature_block[spec.name]
        values = series.to_numpy(dtype=np.float64)
        distributions[spec.name] = {
            "dtype": str(series.dtype),
            "parquet_dtype": spec.dtype,
            "source": spec.source,
            "pit_available": spec.pit_available,
            "used_by": list(spec.used_by),
            "notes": spec.notes,
            "null_rate": float(series.isna().mean()),
            "nunique": int(series.nunique(dropna=False)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "p50": float(np.quantile(values, 0.50)),
        }
    target_counts = {label: int((frame["target"] == label).sum()) for label in CLASS_LABELS}
    n = len(frame)
    return {
        "path": str(dataset.path),
        "sha256": dataset.sha256,
        "dataset_version": dataset.dataset_version,
        "feature_schema_version": dataset.feature_schema_version,
        "pinned_feature_schema_version": FEATURE_SCHEMA_VERSION,
        "rows": n,
        "parquet_columns": list(frame.columns),
        "identity_or_target_columns": [name for name in frame.columns if name not in FEATURE_SCHEMA and name != "y"],
        "feature_schema": list(FEATURE_SCHEMA),
        "feature_count": len(FEATURE_SCHEMA),
        "schema_matches_specification": list(FEATURE_SCHEMA) == [
            "home_elo_pre",
            "away_elo_pre",
            "elo_diff",
            "elo_available",
            "home_form_5",
            "away_form_5",
            "home_form_10",
            "away_form_10",
            "home_form_5_available",
            "away_form_5_available",
            "home_form_10_available",
            "away_form_10_available",
            "home_goals_for_5",
            "home_goals_against_5",
            "home_goals_for_10",
            "home_goals_against_10",
            "away_goals_for_5",
            "away_goals_against_5",
            "away_goals_for_10",
            "away_goals_against_10",
            "h2h_home_wins",
            "h2h_draws",
            "h2h_away_wins",
            "h2h_available",
            "h2h_matches",
            "home_matches_played",
            "away_matches_played",
        ],
        "schema_notes": [
            "Parquet stores event_at as ISO-8601 string; it is parsed to UTC datetime on load.",
            "elo_available is constant 1 and is not used by any estimator.",
            "Null rate is 0 because cold-start windows are encoded as 0 plus availability flags.",
            "Identity columns (ids, competition, season, timestamps) are not in the 27-feature schema.",
            "No odds, scores of the target match, standings, or future-looking columns are present.",
        ],
        "null_rate_total": float(feature_block.isna().to_numpy().mean()) if n else 0.0,
        "duplicate_match_ids": int(frame["match_id"].duplicated().sum()),
        "chronological": bool(frame["event_at"].is_monotonic_increasing),
        "period_start": _ts(frame["event_at"].min()),
        "period_end": _ts(frame["event_at"].max()),
        "competitions": sorted(frame["competition_id"].astype(str).unique().tolist()),
        "seasons": sorted(frame["season"].astype(str).unique().tolist()),
        "target_counts": target_counts,
        "target_rates": {label: (target_counts[label] / n if n else 0.0) for label in CLASS_LABELS},
        "competition_counts": _value_counts(frame["competition_id"]),
        "season_counts": _value_counts(frame["season"]),
        "features": distributions,
        "features_used": {
            "frequency": [],
            "elo": list(ELO_FEATURES),
            "poisson": list(POISSON_FEATURES),
            "xgboost": list(BOOSTING_FEATURES),
            "lightgbm": list(BOOSTING_FEATURES),
        },
        "unused_schema_features": ["elo_available"],
    }


def _value_counts(series: pd.Series) -> dict[str, int]:
    counts = series.astype(str).value_counts()
    return {str(key): int(value) for key, value in counts.items()}


def _ts(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).tz_convert("UTC").isoformat()
