from __future__ import annotations

import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from predicta_ingestion.canonical.enums import DataMode, MatchStatus
from predicta_ingestion.canonical.models import League, Match
from predicta_ingestion.clock import ensure_utc
from predicta_ingestion.errors import DataLeakageError, ValidationError
from predicta_ingestion.identity.keys import competition_slug
from predicta_ingestion.ml.elo import ELO_PARAMETERS, reconstruct_pre_match_elo
from predicta_ingestion.ml.features import (
    CUTOFF_POLICY_PRE_KICKOFF,
    FEATURE_SCHEMA,
    FEATURE_SCHEMA_VERSION,
    form_features,
    prior_matches_for_features,
)
from predicta_ingestion.ml.targets import Football1X2Target, one_hot_1x2, result_1x2
from predicta_ingestion.persistence.memory import MemoryCanonicalSink
from predicta_ingestion.pit.store import PointInTimeStore
from predicta_ingestion.providers.leagues import normalize_league_slug, resolve_v1_leagues

DATASET_VERSION = "football-1x2-history-0.3"
PACKAGE_VERSION = "0.1.0"
DATASET_SOURCE = "postgresql:sportmonks"


class DatasetRejection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: str
    reason: str
    detail: str


class MlObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: str
    competition_id: str
    competition_name: str
    season_id: str | None
    season: str
    event_at: datetime
    home_team_id: str
    away_team_id: str
    target: Football1X2Target
    home_win: int
    draw: int
    away_win: int
    features: dict[str, float | int | None]
    provider: str
    raw_payload_id: str | None
    data_mode: DataMode
    dataset_version: str
    cutoff_policy: str
    competition: str


class MlDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: str
    feature_schema_version: str
    code_version: str
    cutoff_policy: str
    source: str
    generated_at: datetime
    competition: str | None
    competitions: list[str]
    seasons: list[str]
    standings_available: bool
    feature_schema: list[str]
    elo_parameters: dict[str, float | str]
    observation_count: int
    rejected_count: int
    rejections: list[DatasetRejection]
    period_start: datetime | None
    period_end: datetime | None
    observations: list[MlObservation]

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_version": self.dataset_version,
            "feature_schema_version": self.feature_schema_version,
            "code_version": self.code_version,
            "cutoff_policy": self.cutoff_policy,
            "source": self.source,
            "generated_at": self.generated_at.isoformat(),
            "competition": self.competition,
            "competitions": self.competitions,
            "seasons": self.seasons,
            "standings_available": self.standings_available,
            "feature_schema": self.feature_schema,
            "elo_parameters": self.elo_parameters,
            "observation_count": self.observation_count,
            "rejected_count": self.rejected_count,
            "rejections": [item.model_dump() for item in self.rejections],
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "observations": [item.model_dump(mode="json") for item in self.observations],
        }


def build_ml_dataset(
    store: PointInTimeStore,
    *,
    competition: str | None = None,
    seasons: Sequence[str] | None = None,
    cutoff_policy: str = CUTOFF_POLICY_PRE_KICKOFF,
    live_only: bool = True,
    generated_at: datetime | None = None,
    source: str = DATASET_SOURCE,
) -> MlDataset:
    if cutoff_policy != CUTOFF_POLICY_PRE_KICKOFF:
        raise ValidationError("unknown_cutoff_policy", f"Unsupported cutoff policy '{cutoff_policy}'.")
    sink = store._sink
    if not isinstance(sink, MemoryCanonicalSink):
        raise TypeError("PointInTimeStore must wrap a MemoryCanonicalSink.")
    selected = _select_matches(sink, competition=competition, seasons=seasons)
    rejections: list[DatasetRejection] = []
    candidates: list[Match] = []
    seen_ids: set[str] = set()
    for match in selected:
        rejection = _reject(match, live_only=live_only)
        if rejection is not None:
            rejections.append(rejection)
            continue
        if match.id in seen_ids:
            rejections.append(
                DatasetRejection(match_id=match.id, reason="duplicate_match", detail="Duplicate match_id.")
            )
            continue
        seen_ids.add(match.id)
        candidates.append(match)
    elo_pool = _elo_pool(sink, live_only=live_only)
    elo = reconstruct_pre_match_elo(elo_pool)
    observations: list[MlObservation] = []
    for match in sorted(candidates, key=lambda item: (ensure_utc(item.kickoff_at), item.id)):
        store.assert_pre_kickoff(match, match.kickoff_at)
        prior = prior_matches_for_features(store, match)
        _assert_no_leakage(match, prior)
        league = sink.leagues[match.league_id]
        home_elo, away_elo = elo.get(match.id, (None, None))
        features = form_features(
            match=match,
            prior_matches=prior,
            home_elo=home_elo,
            away_elo=away_elo,
        )
        if match.id in {item.id for item in prior}:
            raise DataLeakageError("The target match cannot appear in its own feature window.")
        target = result_1x2(match)
        home_win, draw, away_win = one_hot_1x2(target)
        competition_id = _league_competition_id(league)
        observations.append(
            MlObservation(
                match_id=match.id,
                competition_id=competition_id,
                competition_name=league.name,
                season_id=league.provider_season_id,
                season=league.season,
                event_at=match.kickoff_at,
                home_team_id=match.home_team_id or "",
                away_team_id=match.away_team_id or "",
                target=target,
                home_win=home_win,
                draw=draw,
                away_win=away_win,
                features=features,
                provider=match.provenance.provider,
                raw_payload_id=match.provenance.raw_payload_id,
                data_mode=match.provenance.data_mode,
                dataset_version=DATASET_VERSION,
                cutoff_policy=cutoff_policy,
                competition=league.name,
            )
        )
    kickoffs = [item.event_at for item in observations]
    return MlDataset(
        dataset_version=DATASET_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        code_version=resolve_code_version(),
        cutoff_policy=cutoff_policy,
        source=source,
        generated_at=ensure_utc(generated_at) if generated_at is not None else datetime.now(UTC),
        competition=_competition_name(competition),
        competitions=sorted({item.competition_id for item in observations}),
        seasons=sorted({item.season for item in observations}),
        standings_available=False,
        feature_schema=list(FEATURE_SCHEMA),
        elo_parameters=dict(ELO_PARAMETERS),
        observation_count=len(observations),
        rejected_count=len(rejections),
        rejections=rejections,
        period_start=min(kickoffs) if kickoffs else None,
        period_end=max(kickoffs) if kickoffs else None,
        observations=observations,
    )


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


def _select_matches(
    sink: MemoryCanonicalSink,
    *,
    competition: str | None,
    seasons: Sequence[str] | None,
) -> list[Match]:
    wanted_slugs: set[str] | None = None
    if competition:
        leagues = resolve_v1_leagues(normalize_league_slug(competition))
        wanted_slugs = {item.slug for item in leagues}
    selected: list[Match] = []
    for match in sink.matches.values():
        league = sink.leagues.get(match.league_id)
        if league is None:
            continue
        if wanted_slugs is not None and _league_competition_id(league) not in wanted_slugs:
            continue
        if seasons is not None and league.season not in set(seasons):
            continue
        selected.append(match)
    return selected


def _elo_pool(sink: MemoryCanonicalSink, *, live_only: bool) -> list[Match]:
    pool: list[Match] = []
    for match in sink.matches.values():
        if live_only and match.provenance.data_mode is not DataMode.LIVE:
            continue
        if match.status is not MatchStatus.FINISHED:
            continue
        if match.home_score is None or match.away_score is None:
            continue
        if sink.leagues.get(match.league_id) is None:
            continue
        pool.append(match)
    return pool


def _reject(match: Match, *, live_only: bool) -> DatasetRejection | None:
    if live_only and match.provenance.data_mode is not DataMode.LIVE:
        return DatasetRejection(
            match_id=match.id,
            reason="data_mode_mock",
            detail="Mock rows are excluded from live datasets.",
        )
    if not match.home_team_id:
        return DatasetRejection(match_id=match.id, reason="missing_home_team", detail="Home team is missing.")
    if not match.away_team_id:
        return DatasetRejection(match_id=match.id, reason="missing_away_team", detail="Away team is missing.")
    if match.status is not MatchStatus.FINISHED:
        return DatasetRejection(
            match_id=match.id,
            reason="not_finished",
            detail=f"Status '{match.status.value}' is not a labeled 1X2 result.",
        )
    if match.home_score is None or match.away_score is None:
        return DatasetRejection(
            match_id=match.id,
            reason="missing_score",
            detail="Finished matches without scores are not labeled; scores are never invented.",
        )
    return None


def _competition_name(competition: str | None) -> str | None:
    if not competition:
        return None
    return resolve_v1_leagues(normalize_league_slug(competition))[0].name


def _league_competition_id(league: League) -> str:
    return league.competition_id or competition_slug(league)


def _assert_no_leakage(match: Match, prior: Sequence[Match]) -> None:
    cutoff = ensure_utc(match.kickoff_at)
    for item in prior:
        if item.id == match.id:
            raise DataLeakageError("Target match result leaked into features.")
        if ensure_utc(item.kickoff_at) >= cutoff:
            raise DataLeakageError("A feature used a match on or after the target kickoff.")
        if ensure_utc(item.provenance.available_at) >= cutoff:
            raise DataLeakageError("A feature used a fact that was not available before kickoff.")
        event_at = item.provenance.event_at or item.kickoff_at
        if ensure_utc(event_at) >= cutoff:
            raise DataLeakageError("A feature used an event_at on or after the target kickoff.")
