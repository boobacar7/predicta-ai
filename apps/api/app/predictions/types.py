from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

ModelStatus = Literal["candidate", "champion"]
CANDIDATE_MODEL_VERSION = "football-elo-v1-candidate"
CANDIDATE_STATUS: ModelStatus = "candidate"
MARKET_1X2 = "1X2"
SPORT_FOOTBALL = "football"
CUTOFF_POLICY_PRE_KICKOFF = "pre_kickoff"
ELO_FEATURES: tuple[str, str, str] = ("home_elo_pre", "away_elo_pre", "elo_diff")
PROBABILITY_CLIP = 1e-15
SIMPLEX_ATOL = 1e-12


@dataclass(frozen=True, slots=True)
class PitEloFeatures:
    match_id: str
    event_at: datetime
    cutoff_at: datetime
    cutoff_policy: str
    dataset_version: str
    feature_schema_version: str
    data_mode: str
    home_elo_pre: float
    away_elo_pre: float
    elo_diff: float


@dataclass(frozen=True, slots=True)
class OutcomeProbabilities:
    home: float
    draw: float
    away: float

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.home, self.draw, self.away)

    def total(self) -> float:
        return self.home + self.draw + self.away


class Football1x2Model(Protocol):
    """Swap-in interface for a future champion. Public HTTP schema stays stable."""

    @property
    def model_version(self) -> str: ...

    @property
    def model_status(self) -> ModelStatus: ...

    @property
    def dataset_version(self) -> str: ...

    @property
    def feature_schema_version(self) -> str: ...

    def predict_1x2(self, features: PitEloFeatures) -> OutcomeProbabilities: ...
