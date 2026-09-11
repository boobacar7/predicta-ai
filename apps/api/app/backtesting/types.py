from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.odds.types import OddsSnapshot
from app.predictions.types import PitEloFeatures

PilotKind = Literal["descriptive_fixture", "live_labeled_weekend"]
MatchDecision = Literal["exact", "alias", "unmatched", "isolated_team", "inverted_home_away"]
ExclusionKind = Literal[
    "unmatched_odds_event",
    "isolated_team",
    "inverted_home_away",
    "missing_timestamp",
    "incomplete_market",
    "prediction_unavailable",
    "odds_unavailable",
    "odds_not_persisted",
    "pit_unavailable",
    "stale_odds",
    "negative_ev",
    "negative_edge",
    "below_minimum_ev",
    "below_minimum_edge",
    "below_minimum_model_probability",
    "invalid_prediction",
    "invalid_value",
    "no_canonical_identity",
]


@dataclass(frozen=True, slots=True)
class CatalogMatch:
    match_id: str
    home_team_id: str
    away_team_id: str
    home_team: str
    away_team: str
    league: str
    kickoff_at: datetime
    outcome: str
    home_elo_pre: float
    away_elo_pre: float
    dataset_version: str = "football-1x2-history-0.3"
    feature_schema_version: str = "football-1x2-features-0.3"
    cutoff_policy: str = "pre_kickoff"
    data_mode: str = "live"

    @property
    def elo_diff(self) -> float:
        return self.home_elo_pre - self.away_elo_pre

    def pit_features(self) -> PitEloFeatures:
        return PitEloFeatures(
            match_id=self.match_id,
            event_at=self.kickoff_at,
            cutoff_at=self.kickoff_at,
            cutoff_policy=self.cutoff_policy,
            dataset_version=self.dataset_version,
            feature_schema_version=self.feature_schema_version,
            data_mode=self.data_mode,
            home_elo_pre=self.home_elo_pre,
            away_elo_pre=self.away_elo_pre,
            elo_diff=self.elo_diff,
        )


@dataclass(frozen=True, slots=True)
class EventDecision:
    event_id: str
    home_team: str
    away_team: str
    kickoff_at: datetime
    natural_key: str
    status: MatchDecision
    match_id: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class QualityExclusion:
    kind: ExclusionKind
    detail: str
    event_id: str | None = None
    match_id: str | None = None
    bookmaker: str | None = None
    selection: str | None = None


@dataclass
class QualityLedger:
    events: int = 0
    matched: int = 0
    exact_matches: int = 0
    alias_matches: int = 0
    rejected: int = 0
    snapshots_accepted: int = 0
    snapshots_rejected: int = 0
    missing_timestamps: int = 0
    incomplete_markets: int = 0
    matches_without_prediction: int = 0
    matches_without_odds: int = 0
    bookmakers_seen: list[str] = field(default_factory=list)
    exclusions: list[QualityExclusion] = field(default_factory=list)

    def add(self, item: QualityExclusion) -> None:
        self.exclusions.append(item)
        if item.kind in {"unmatched_odds_event", "isolated_team", "inverted_home_away"}:
            self.rejected += 1
        elif item.kind == "missing_timestamp":
            self.missing_timestamps += 1
            self.snapshots_rejected += 1
        elif item.kind == "incomplete_market":
            self.incomplete_markets += 1
            self.snapshots_rejected += 1
        elif item.kind == "prediction_unavailable":
            self.matches_without_prediction += 1
        elif item.kind in {"odds_unavailable", "odds_not_persisted"}:
            self.matches_without_odds += 1


@dataclass(frozen=True, slots=True)
class OddsBundle:
    snapshots: tuple[OddsSnapshot, ...]
    decisions: tuple[EventDecision, ...]
    quality: QualityLedger


@dataclass(frozen=True, slots=True)
class BookmakerDescriptiveRow:
    """Not used for selection. Historical EV by book is diagnostic only."""

    match_id: str
    bookmaker: str
    available_at: datetime
    home_ev: float
    draw_ev: float
    away_ev: float
    selected: bool
