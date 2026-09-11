from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pandas as pd

from predicta_ml.constants import CLASS_INDEX, COMPETITION_ORDER, CUTOFF_POLICY, DATASET_VERSION
from predicta_ml.features.dataset import FootballDataset
from predicta_ml.oos.errors import OosIdentityError, OosLeakageError, OosProtocolError
from predicta_ml.oos.protocol import OOS_START, classify_event_at, is_true_oos_event, normalize_competition
from predicta_ml.oos.provenance import ModelProvenance, assert_window_is_oos


@dataclass(frozen=True)
class OosMatch:
    match_id: str
    kickoff_at: datetime
    cutoff_at: datetime
    competition: str
    season: str
    home_team_id: str
    away_team_id: str
    home_elo_pre: float
    away_elo_pre: float
    elo_diff: float
    outcome: str
    y: int
    data_mode: str
    dataset_version: str
    cutoff_policy: str
    temporal_split: str

    def to_dict(self) -> dict[str, object]:
        return {
            "match_id": self.match_id,
            "kickoff_at": self.kickoff_at.isoformat(),
            "cutoff_at": self.cutoff_at.isoformat(),
            "competition": self.competition,
            "season": self.season,
            "home_team_id": self.home_team_id,
            "away_team_id": self.away_team_id,
            "home_elo_pre": self.home_elo_pre,
            "away_elo_pre": self.away_elo_pre,
            "elo_diff": self.elo_diff,
            "outcome": self.outcome,
            "data_mode": self.data_mode,
            "dataset_version": self.dataset_version,
            "cutoff_policy": self.cutoff_policy,
            "temporal_split": self.temporal_split,
        }


def oos_window_end(dataset: FootballDataset) -> datetime:
    latest = pd.Timestamp(dataset.frame["event_at"].max()).tz_convert(UTC).to_pydatetime()
    return latest + timedelta(seconds=1)


def select_oos_frame(
    dataset: FootballDataset,
    *,
    provenance: ModelProvenance,
    start: datetime | None = None,
    end_exclusive: datetime | None = None,
) -> pd.DataFrame:
    window_start = (start or OOS_START).astimezone(UTC)
    window_end = (end_exclusive or oos_window_end(dataset)).astimezone(UTC)
    assert_window_is_oos(start=window_start, end_exclusive=window_end, provenance=provenance)
    frame = dataset.frame
    _assert_identity(frame)
    selected = frame[(frame["event_at"] >= window_start) & (frame["event_at"] < window_end)].copy()
    if selected.empty:
        raise OosProtocolError("True OOS window contains zero finished matches.")
    if pd.Timestamp(selected["event_at"].min()).tz_convert(UTC).to_pydatetime() < provenance.earliest_legitimate_oos:
        raise OosLeakageError("OOS frame includes an event at or before the artefact freeze.")
    if not bool((selected["cutoff_policy"].astype(str) == CUTOFF_POLICY).all()):
        raise OosLeakageError("OOS rows must use the frozen pre_kickoff cutoff policy.")
    if not bool((selected["dataset_version"].astype(str) == DATASET_VERSION).all()):
        raise OosProtocolError("OOS rows are not football-1x2-history-0.3.")
    return selected.sort_values(["event_at", "match_id"], kind="mergesort").reset_index(drop=True)


def matches_from_frame(frame: pd.DataFrame) -> tuple[OosMatch, ...]:
    rows: list[OosMatch] = []
    seen: set[str] = set()
    for _, raw in frame.iterrows():
        match_id = str(raw["match_id"])
        if not match_id:
            raise OosIdentityError("OOS match_id is empty.")
        if match_id in seen:
            raise OosIdentityError(f"Duplicate OOS match_id: {match_id}")
        seen.add(match_id)
        kickoff = _utc(raw["event_at"])
        if not is_true_oos_event(kickoff):
            raise OosLeakageError(
                f"Match {match_id} at {kickoff.isoformat()} is {classify_event_at(kickoff)}, not true OOS."
            )
        outcome = str(raw["target"])
        if outcome not in CLASS_INDEX:
            raise OosProtocolError(f"Unknown outcome for {match_id}: {outcome}")
        elo_diff = float(raw["elo_diff"])
        expected = float(raw["home_elo_pre"]) - float(raw["away_elo_pre"])
        if abs(elo_diff - expected) > 1e-9:
            raise OosLeakageError(f"elo_diff is inconsistent for {match_id}.")
        rows.append(
            OosMatch(
                match_id=match_id,
                kickoff_at=kickoff,
                cutoff_at=kickoff,
                competition=normalize_competition(str(raw["competition"])),
                season=str(raw["season"]),
                home_team_id=str(raw["home_team_id"]),
                away_team_id=str(raw["away_team_id"]),
                home_elo_pre=float(raw["home_elo_pre"]),
                away_elo_pre=float(raw["away_elo_pre"]),
                elo_diff=elo_diff,
                outcome=outcome,
                y=int(CLASS_INDEX[outcome]),
                data_mode=str(raw["data_mode"]),
                dataset_version=str(raw["dataset_version"]),
                cutoff_policy=str(raw["cutoff_policy"]),
                temporal_split="final_test",
            )
        )
    return tuple(rows)


def coverage_report(matches: tuple[OosMatch, ...]) -> dict[str, object]:
    by_competition = {name: 0 for name in COMPETITION_ORDER}
    unknown: dict[str, int] = {}
    for item in matches:
        if item.competition in by_competition:
            by_competition[item.competition] += 1
        else:
            unknown[item.competition] = unknown.get(item.competition, 0) + 1
    kickoffs = [item.kickoff_at for item in matches]
    return {
        "n": len(matches),
        "start": min(kickoffs).isoformat() if kickoffs else None,
        "end_inclusive": max(kickoffs).isoformat() if kickoffs else None,
        "by_competition": by_competition,
        "unknown_competitions": unknown,
        "pit_features": {
            "home_elo_pre": True,
            "away_elo_pre": True,
            "elo_diff": True,
            "n_with_pre_match_elo": len(matches),
        },
    }


def _assert_identity(frame: pd.DataFrame) -> None:
    duplicated = int(frame["match_id"].duplicated().sum())
    if duplicated:
        raise OosIdentityError(f"Dataset contains {duplicated} duplicate match_id values.")
    if int((frame["match_id"].astype(str) == "").sum()):
        raise OosIdentityError("Dataset contains empty match_id values.")


def _utc(value: object) -> datetime:
    stamp = pd.Timestamp(value)  # type: ignore[arg-type]
    if stamp.tzinfo is None:
        raise OosProtocolError("event_at must be timezone-aware UTC.")
    return stamp.tz_convert(UTC).to_pydatetime()
