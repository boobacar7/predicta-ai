from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from predicta_ingestion.canonical.enums import DataMode, MatchStatus
from predicta_ingestion.canonical.models import Match
from predicta_ingestion.clock import ensure_utc
from predicta_ingestion.errors import DataLeakageError, ValidationError
from predicta_ingestion.ml.dataset import (
    DATASET_SOURCE,
    DATASET_VERSION,
    DatasetRejection,
    _assert_no_leakage,
    _elo_pool,
    _league_competition_id,
    _select_matches,
    resolve_code_version,
)
from predicta_ingestion.ml.elo import ELO_PARAMETERS, snapshot_pre_match_elo
from predicta_ingestion.ml.features import (
    CUTOFF_POLICY_PRE_KICKOFF,
    FEATURE_SCHEMA,
    FEATURE_SCHEMA_VERSION,
    form_features,
    prior_matches_for_features,
)
from predicta_ingestion.persistence.memory import MemoryCanonicalSink
from predicta_ingestion.pit.store import PointInTimeStore

PREMATCH_FEATURE_ORIGIN = "prematch_unlabeled"


class PrematchFeatureRow(BaseModel):
    """Unlabeled PIT features for a scheduled match. Scores are never invented."""

    model_config = ConfigDict(extra="forbid")

    match_id: str
    competition_id: str
    competition_name: str
    season_id: str | None
    season: str
    event_at: datetime
    home_team_id: str
    away_team_id: str
    features: dict[str, float | int | None]
    provider: str
    raw_payload_id: str | None
    data_mode: DataMode
    dataset_version: str
    feature_schema_version: str
    cutoff_policy: str
    feature_origin: str
    competition: str


class PrematchFeatureSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: str
    feature_schema_version: str
    code_version: str
    cutoff_policy: str
    source: str
    generated_at: datetime
    feature_origin: str
    feature_schema: list[str]
    elo_parameters: dict[str, float | str]
    observation_count: int
    rejected_count: int
    rejections: list[DatasetRejection]
    observations: list[PrematchFeatureRow]

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_version": self.dataset_version,
            "feature_schema_version": self.feature_schema_version,
            "code_version": self.code_version,
            "cutoff_policy": self.cutoff_policy,
            "source": self.source,
            "generated_at": self.generated_at.isoformat(),
            "feature_origin": self.feature_origin,
            "feature_schema": self.feature_schema,
            "elo_parameters": self.elo_parameters,
            "observation_count": self.observation_count,
            "rejected_count": self.rejected_count,
            "rejections": [item.model_dump() for item in self.rejections],
            "observations": [item.model_dump(mode="json") for item in self.observations],
        }


def build_prematch_features(
    store: PointInTimeStore,
    *,
    competition: str | None = None,
    match_ids: Sequence[str] | None = None,
    cutoff_policy: str = CUTOFF_POLICY_PRE_KICKOFF,
    live_only: bool = True,
    generated_at: datetime | None = None,
    source: str = DATASET_SOURCE,
) -> PrematchFeatureSet:
    """PIT features for scheduled fixtures. Does not label, train, or promote."""
    if cutoff_policy != CUTOFF_POLICY_PRE_KICKOFF:
        raise ValidationError("unknown_cutoff_policy", f"Unsupported cutoff policy '{cutoff_policy}'.")
    sink = store._sink
    if not isinstance(sink, MemoryCanonicalSink):
        raise TypeError("PointInTimeStore must wrap a MemoryCanonicalSink.")
    wanted = None if match_ids is None else set(match_ids)
    selected = _select_matches(sink, competition=competition, seasons=None)
    rejections: list[DatasetRejection] = []
    scheduled: list[Match] = []
    for match in selected:
        if wanted is not None and match.id not in wanted:
            continue
        rejection = _reject_scheduled(match, live_only=live_only)
        if rejection is not None:
            if match.status is MatchStatus.SCHEDULED or (wanted is not None and match.id in wanted):
                rejections.append(rejection)
            continue
        scheduled.append(match)
    elo_pool = _elo_pool(sink, live_only=live_only)
    elo = snapshot_pre_match_elo([*elo_pool, *scheduled])
    observations: list[PrematchFeatureRow] = []
    for match in sorted(scheduled, key=lambda item: (ensure_utc(item.kickoff_at), item.id)):
        cutoff = ensure_utc(match.kickoff_at)
        store.assert_pre_kickoff(match, cutoff)
        prior = prior_matches_for_features(store, match)
        _assert_no_leakage(match, prior)
        if match.id in {item.id for item in prior}:
            raise DataLeakageError("The target match cannot appear in its own feature window.")
        if match.home_score is not None or match.away_score is not None:
            raise DataLeakageError("Scheduled pre-match features cannot use the target score.")
        league = sink.leagues[match.league_id]
        home_elo, away_elo = elo.get(match.id, (None, None))
        features = form_features(
            match=match,
            prior_matches=prior,
            home_elo=home_elo,
            away_elo=away_elo,
        )
        observations.append(
            PrematchFeatureRow(
                match_id=match.id,
                competition_id=_league_competition_id(league),
                competition_name=league.name,
                season_id=league.provider_season_id,
                season=league.season,
                event_at=match.kickoff_at,
                home_team_id=match.home_team_id or "",
                away_team_id=match.away_team_id or "",
                features=features,
                provider=match.provenance.provider,
                raw_payload_id=match.provenance.raw_payload_id,
                data_mode=match.provenance.data_mode,
                dataset_version=DATASET_VERSION,
                feature_schema_version=FEATURE_SCHEMA_VERSION,
                cutoff_policy=cutoff_policy,
                feature_origin=PREMATCH_FEATURE_ORIGIN,
                competition=league.name,
            )
        )
    return PrematchFeatureSet(
        dataset_version=DATASET_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        code_version=resolve_code_version(),
        cutoff_policy=cutoff_policy,
        source=source,
        generated_at=ensure_utc(generated_at) if generated_at is not None else datetime.now(UTC),
        feature_origin=PREMATCH_FEATURE_ORIGIN,
        feature_schema=list(FEATURE_SCHEMA),
        elo_parameters=dict(ELO_PARAMETERS),
        observation_count=len(observations),
        rejected_count=len(rejections),
        rejections=rejections,
        observations=observations,
    )


def write_prematch_artifacts(features: PrematchFeatureSet, json_path: str | Path) -> dict[str, str]:
    path = Path(json_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(features.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    parquet_path = path.with_suffix(".parquet")
    _write_prematch_parquet(features, parquet_path)
    quality_path = path.with_name(path.stem + ".quality.json")
    quality_path.write_text(
        json.dumps(
            {
                "feature_origin": features.feature_origin,
                "dataset_version": features.dataset_version,
                "feature_schema_version": features.feature_schema_version,
                "observation_count": features.observation_count,
                "rejected_count": features.rejected_count,
                "rejection_reasons": _rejection_reasons(features.rejections),
                "labeled": False,
                "standings_used": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return {"json": str(path), "parquet": str(parquet_path), "quality": str(quality_path)}


def _write_prematch_parquet(features: PrematchFeatureSet, path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    for item in features.observations:
        row: dict[str, Any] = {
            "match_id": item.match_id,
            "event_at": item.event_at.isoformat(),
            "home_team_id": item.home_team_id,
            "away_team_id": item.away_team_id,
            "competition": item.competition,
            "competition_id": item.competition_id,
            "competition_name": item.competition_name,
            "season": item.season,
            "season_id": item.season_id,
            "provider": item.provider,
            "raw_payload_id": item.raw_payload_id,
            "data_mode": item.data_mode.value,
            "dataset_version": item.dataset_version,
            "feature_schema_version": item.feature_schema_version,
            "cutoff_policy": item.cutoff_policy,
            "feature_origin": item.feature_origin,
        }
        row.update(item.features)
        rows.append(row)
    table = pa.Table.from_pylist(rows) if rows else pa.table({})
    pq.write_table(table, path)


def _reject_scheduled(match: Match, *, live_only: bool) -> DatasetRejection | None:
    if live_only and match.provenance.data_mode is not DataMode.LIVE:
        return DatasetRejection(
            match_id=match.id,
            reason="data_mode_mock",
            detail="Mock rows are excluded from live pre-match features.",
        )
    if not match.home_team_id:
        return DatasetRejection(match_id=match.id, reason="missing_home_team", detail="Home team is missing.")
    if not match.away_team_id:
        return DatasetRejection(match_id=match.id, reason="missing_away_team", detail="Away team is missing.")
    if match.status is not MatchStatus.SCHEDULED:
        return DatasetRejection(
            match_id=match.id,
            reason="not_scheduled",
            detail=f"Status '{match.status.value}' is not a pre-match unlabeled fixture.",
        )
    if match.home_score is not None or match.away_score is not None:
        return DatasetRejection(
            match_id=match.id,
            reason="scheduled_has_score",
            detail="Scheduled fixtures with scores are refused; scores are never used as pre-match labels.",
        )
    return None


def _rejection_reasons(rejections: list[DatasetRejection]) -> dict[str, int]:
    reasons: dict[str, int] = {}
    for item in rejections:
        reasons[item.reason] = reasons.get(item.reason, 0) + 1
    return reasons
