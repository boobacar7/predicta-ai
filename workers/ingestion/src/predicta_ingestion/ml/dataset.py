from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from predicta_ingestion.canonical.enums import DataMode, MatchStatus
from predicta_ingestion.canonical.models import Match
from predicta_ingestion.clock import ensure_utc
from predicta_ingestion.errors import DataLeakageError, ValidationError
from predicta_ingestion.ml.elo import reconstruct_pre_match_elo
from predicta_ingestion.ml.features import CUTOFF_POLICY_PRE_KICKOFF, form_features, prior_matches_for_features
from predicta_ingestion.ml.targets import Football1X2Target, result_1x2
from predicta_ingestion.persistence.memory import MemoryCanonicalSink
from predicta_ingestion.pit.store import PointInTimeStore
from predicta_ingestion.providers.leagues import normalize_league_slug, resolve_v1_leagues

DATASET_VERSION = "football-1x2-history-0.1"


class MlObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: str
    event_at: datetime
    home_team_id: str
    away_team_id: str
    target: Football1X2Target
    features: dict[str, float | int | None]
    provider: str
    raw_payload_id: str | None
    data_mode: DataMode
    dataset_version: str
    cutoff_policy: str
    competition: str
    season: str


class MlDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: str
    cutoff_policy: str
    competition: str | None
    seasons: list[str]
    standings_available: bool
    observations: list[MlObservation]

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_version": self.dataset_version,
            "cutoff_policy": self.cutoff_policy,
            "competition": self.competition,
            "seasons": self.seasons,
            "standings_available": self.standings_available,
            "observation_count": len(self.observations),
            "observations": [item.model_dump(mode="json") for item in self.observations],
        }


def build_ml_dataset(
    store: PointInTimeStore,
    *,
    competition: str | None = None,
    seasons: Sequence[str] | None = None,
    cutoff_policy: str = CUTOFF_POLICY_PRE_KICKOFF,
) -> MlDataset:
    if cutoff_policy != CUTOFF_POLICY_PRE_KICKOFF:
        raise ValidationError("unknown_cutoff_policy", f"Unsupported cutoff policy '{cutoff_policy}'.")
    sink = store._sink
    if not isinstance(sink, MemoryCanonicalSink):
        raise TypeError("PointInTimeStore must wrap a MemoryCanonicalSink.")
    selected = _select_matches(sink, competition=competition, seasons=seasons)
    labeled = [
        item
        for item in selected
        if item.status is MatchStatus.FINISHED and item.home_score is not None and item.away_score is not None
    ]
    elo = reconstruct_pre_match_elo(labeled)
    observations: list[MlObservation] = []
    for match in sorted(labeled, key=lambda item: (ensure_utc(item.kickoff_at), item.id)):
        store.assert_pre_kickoff(match, match.kickoff_at)
        prior = prior_matches_for_features(store, match)
        _assert_no_leakage(match, prior)
        league = sink.leagues[match.league_id]
        home_elo, away_elo = elo.get(match.id, (None, None))
        standings = store.standings_as_of(match.league_id, match.kickoff_at)
        features = form_features(
            match=match,
            prior_matches=prior,
            standings=standings,
            home_elo=home_elo,
            away_elo=away_elo,
        )
        if match.id in {item.id for item in prior}:
            raise DataLeakageError("The target match cannot appear in its own feature window.")
        observations.append(
            MlObservation(
                match_id=match.id,
                event_at=match.kickoff_at,
                home_team_id=match.home_team_id or "",
                away_team_id=match.away_team_id or "",
                target=result_1x2(match),
                features=features,
                provider=match.provenance.provider,
                raw_payload_id=match.provenance.raw_payload_id,
                data_mode=match.provenance.data_mode,
                dataset_version=DATASET_VERSION,
                cutoff_policy=cutoff_policy,
                competition=league.name,
                season=league.season,
            )
        )
    return MlDataset(
        dataset_version=DATASET_VERSION,
        cutoff_policy=cutoff_policy,
        competition=_competition_name(competition),
        seasons=sorted({item.season for item in observations}),
        standings_available=bool(sink.standings),
        observations=observations,
    )


def _select_matches(
    sink: MemoryCanonicalSink,
    *,
    competition: str | None,
    seasons: Sequence[str] | None,
) -> list[Match]:
    wanted_names: set[str] | None = None
    if competition:
        leagues = resolve_v1_leagues(normalize_league_slug(competition))
        wanted_names = {item.name for item in leagues}
    selected: list[Match] = []
    for match in sink.matches.values():
        league = sink.leagues.get(match.league_id)
        if league is None:
            continue
        if wanted_names is not None and league.name not in wanted_names:
            continue
        if seasons is not None and league.season not in set(seasons):
            continue
        selected.append(match)
    return selected


def _competition_name(competition: str | None) -> str | None:
    if not competition:
        return None
    return resolve_v1_leagues(normalize_league_slug(competition))[0].name


def _assert_no_leakage(match: Match, prior: Sequence[Match]) -> None:
    cutoff = ensure_utc(match.kickoff_at)
    for item in prior:
        if item.id == match.id:
            raise DataLeakageError("Target match result leaked into features.")
        if ensure_utc(item.kickoff_at) >= cutoff:
            raise DataLeakageError("A feature used a match on or after the target kickoff.")
        if ensure_utc(item.kickoff_at).date() >= cutoff.date():
            raise DataLeakageError("A form feature used a same-day or later match.")
        if ensure_utc(item.provenance.available_at) >= cutoff:
            raise DataLeakageError("A feature used a fact that was not available before kickoff.")
