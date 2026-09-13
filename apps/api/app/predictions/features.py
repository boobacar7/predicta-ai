from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.core.clock import parse_rfc3339
from app.predictions.exceptions import PitFeaturesUnavailableError, TemporalLeakageError
from app.predictions.provenance import prediction_envelope_data_mode
from app.predictions.runtime import ensure_ml_on_path
from app.predictions.types import (
    CUTOFF_POLICY_PRE_KICKOFF,
    ELO_FEATURES,
    PitEloFeatures,
)


class PitFeatureStore(Protocol):
    def get_pit_features(self, match_id: str, cutoff_at: datetime | None) -> PitEloFeatures: ...


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise PitFeaturesUnavailableError("Feature timestamps must be timezone-aware UTC.")
    return value.astimezone(UTC)


def validate_elo_snapshot(
    *,
    match_id: str,
    event_at: datetime,
    cutoff_at: datetime | None,
    cutoff_policy: str,
    dataset_version: str,
    feature_schema_version: str,
    data_mode: str,
    home_elo_pre: float,
    away_elo_pre: float,
    elo_diff: float,
    elo_available: int | None = 1,
) -> PitEloFeatures:
    kickoff = ensure_utc(event_at)
    resolved_cutoff = ensure_utc(cutoff_at) if cutoff_at is not None else kickoff
    if cutoff_policy != CUTOFF_POLICY_PRE_KICKOFF:
        raise PitFeaturesUnavailableError("Only the pre_kickoff cutoff policy is supported.")
    data_mode = prediction_envelope_data_mode(data_mode)
    if resolved_cutoff > kickoff:
        raise TemporalLeakageError(
            "cutoff_at is after kickoff; post-match or future-of-cutoff data cannot be used."
        )
    if resolved_cutoff < kickoff:
        raise PitFeaturesUnavailableError(
            "No PIT Elo snapshot exists at the requested cutoff; the candidate only serves the pre-kickoff snapshot."
        )
    if elo_available == 0:
        raise PitFeaturesUnavailableError("Pre-match Elo is unavailable at cutoff for this match.")
    values = (home_elo_pre, away_elo_pre, elo_diff)
    if any(not math.isfinite(item) for item in values):
        raise PitFeaturesUnavailableError("PIT Elo features are missing or non-finite at cutoff.")
    expected_diff = home_elo_pre - away_elo_pre
    if not math.isclose(elo_diff, expected_diff, abs_tol=1e-9, rel_tol=0.0):
        raise PitFeaturesUnavailableError("elo_diff is inconsistent with home_elo_pre and away_elo_pre.")
    return PitEloFeatures(
        match_id=match_id,
        event_at=kickoff,
        cutoff_at=resolved_cutoff,
        cutoff_policy=cutoff_policy,
        dataset_version=dataset_version,
        feature_schema_version=feature_schema_version,
        data_mode=data_mode,
        home_elo_pre=float(home_elo_pre),
        away_elo_pre=float(away_elo_pre),
        elo_diff=float(elo_diff),
    )


class InMemoryPitFeatureStore:
    """Test store over explicit PIT rows. Does not stand in for the candidate artefact."""

    def __init__(self, rows: list[PitEloFeatures]) -> None:
        self._rows = {row.match_id: row for row in rows}

    def get_pit_features(self, match_id: str, cutoff_at: datetime | None) -> PitEloFeatures:
        row = self._rows.get(match_id)
        if row is None:
            raise PitFeaturesUnavailableError(f"No PIT features are available for match '{match_id}'.")
        return validate_elo_snapshot(
            match_id=row.match_id,
            event_at=row.event_at,
            cutoff_at=cutoff_at,
            cutoff_policy=row.cutoff_policy,
            dataset_version=row.dataset_version,
            feature_schema_version=row.feature_schema_version,
            data_mode=row.data_mode,
            home_elo_pre=row.home_elo_pre,
            away_elo_pre=row.away_elo_pre,
            elo_diff=row.elo_diff,
        )


class ParquetPitFeatureStore:
    """Reads frozen football-1x2-history-0.3 rows. Never fabricates Elo or uses labels."""

    def __init__(self, path: Path) -> None:
        ensure_ml_on_path()
        from predicta_ml.features.dataset import load_football_dataset

        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            raise PitFeaturesUnavailableError(f"PIT dataset parquet was not found: {resolved}")
        self._dataset = load_football_dataset(resolved)
        frame = self._dataset.frame
        self._index = {str(match_id): position for position, match_id in enumerate(frame["match_id"].tolist())}

    def get_pit_features(self, match_id: str, cutoff_at: datetime | None) -> PitEloFeatures:
        position = self._index.get(match_id)
        if position is None:
            raise PitFeaturesUnavailableError(f"No PIT features are available for match '{match_id}'.")
        row = self._dataset.frame.iloc[position]
        for name in ELO_FEATURES:
            if name not in row.index:
                raise PitFeaturesUnavailableError(f"Required PIT feature '{name}' is missing at cutoff.")
        event_at = row["event_at"]
        if hasattr(event_at, "to_pydatetime"):
            event_at = event_at.to_pydatetime()
        elo_available = int(row["elo_available"]) if "elo_available" in row.index else 1
        parsed_event: datetime
        if isinstance(event_at, datetime):
            parsed_event = event_at
        else:
            parsed_event = parse_rfc3339(str(event_at))
        return validate_elo_snapshot(
            match_id=str(row["match_id"]),
            event_at=parsed_event,
            cutoff_at=cutoff_at,
            cutoff_policy=str(row["cutoff_policy"]),
            dataset_version=str(row["dataset_version"]),
            feature_schema_version=self._dataset.feature_schema_version,
            data_mode=str(row["data_mode"]),
            home_elo_pre=float(row["home_elo_pre"]),
            away_elo_pre=float(row["away_elo_pre"]),
            elo_diff=float(row["elo_diff"]),
            elo_available=elo_available,
        )


class PrematchParquetFeatureStore:
    """Reads unlabeled scheduled PIT rows. Never invents labels or Elo."""

    def __init__(self, path: Path) -> None:
        import pyarrow.parquet as pq

        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            raise PitFeaturesUnavailableError(f"Prematch PIT parquet was not found: {resolved}")
        frame = pq.read_table(resolved).to_pandas()
        required = (
            "match_id",
            "event_at",
            "cutoff_policy",
            "dataset_version",
            "data_mode",
            "home_elo_pre",
            "away_elo_pre",
            "elo_diff",
        )
        missing = [name for name in required if name not in frame.columns]
        if missing:
            raise PitFeaturesUnavailableError(f"Prematch PIT parquet is missing columns: {missing}")
        if "home_win" in frame.columns or "away_win" in frame.columns or "draw" in frame.columns:
            raise PitFeaturesUnavailableError(
                "Prematch PIT parquet must remain unlabeled; refuse files that contain 1X2 labels."
            )
        self._feature_schema_version = (
            str(frame["feature_schema_version"].iloc[0])
            if "feature_schema_version" in frame.columns and len(frame.index)
            else "football-1x2-features-0.3"
        )
        self._index = {str(match_id): position for position, match_id in enumerate(frame["match_id"].tolist())}
        self._frame = frame

    def get_pit_features(self, match_id: str, cutoff_at: datetime | None) -> PitEloFeatures:
        position = self._index.get(match_id)
        if position is None:
            raise PitFeaturesUnavailableError(f"No PIT features are available for match '{match_id}'.")
        row = self._frame.iloc[position]
        event_at = row["event_at"]
        if hasattr(event_at, "to_pydatetime"):
            event_at = event_at.to_pydatetime()
        elo_available = int(row["elo_available"]) if "elo_available" in row.index else 1
        parsed_event: datetime
        if isinstance(event_at, datetime):
            parsed_event = event_at
        else:
            parsed_event = parse_rfc3339(str(event_at))
        schema_version = (
            str(row["feature_schema_version"])
            if "feature_schema_version" in row.index
            else self._feature_schema_version
        )
        return validate_elo_snapshot(
            match_id=str(row["match_id"]),
            event_at=parsed_event,
            cutoff_at=cutoff_at,
            cutoff_policy=str(row["cutoff_policy"]),
            dataset_version=str(row["dataset_version"]),
            feature_schema_version=schema_version,
            data_mode=str(row["data_mode"]),
            home_elo_pre=float(row["home_elo_pre"]),
            away_elo_pre=float(row["away_elo_pre"]),
            elo_diff=float(row["elo_diff"]),
            elo_available=elo_available,
        )


class CompositePitFeatureStore:
    """History parquet first, then unlabeled pre-match overlay. Leakage errors propagate."""

    def __init__(self, stores: list[PitFeatureStore]) -> None:
        if not stores:
            raise PitFeaturesUnavailableError("No PIT feature stores are configured.")
        self._stores = stores

    def get_pit_features(self, match_id: str, cutoff_at: datetime | None) -> PitEloFeatures:
        last_missing: PitFeaturesUnavailableError | None = None
        for store in self._stores:
            try:
                return store.get_pit_features(match_id, cutoff_at)
            except PitFeaturesUnavailableError as exc:
                last_missing = exc
        raise last_missing or PitFeaturesUnavailableError(f"No PIT features are available for match '{match_id}'.")
