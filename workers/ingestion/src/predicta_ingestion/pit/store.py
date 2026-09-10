from __future__ import annotations

from datetime import datetime

from predicta_ingestion.canonical.enums import MatchStatus
from predicta_ingestion.canonical.models import Injury, Lineup, Match, OddsSnapshot, StandingSnapshot, TeamStats
from predicta_ingestion.clock import ensure_utc
from predicta_ingestion.errors import DataLeakageError
from predicta_ingestion.persistence.memory import MemoryCanonicalSink


def _before_cutoff(*, available_at: datetime, event_at: datetime | None, cutoff: datetime) -> bool:
    cutoff_utc = ensure_utc(cutoff)
    if ensure_utc(available_at) >= cutoff_utc:
        return False
    if event_at is not None and ensure_utc(event_at) >= cutoff_utc:
        return False
    return True


class PointInTimeStore:
    """Read path for the ML worker. Refuses any fact that is not strictly before cutoff."""

    def __init__(self, sink: MemoryCanonicalSink) -> None:
        self._sink = sink

    def assert_pre_kickoff(self, match: Match, cutoff: datetime) -> None:
        if ensure_utc(cutoff) > ensure_utc(match.kickoff_at):
            raise DataLeakageError("Feature cutoff must be at or before kickoff.")

    def matches_finished_before(self, cutoff: datetime) -> list[Match]:
        selected: list[Match] = []
        for match in self._sink.matches.values():
            if match.status is not MatchStatus.FINISHED:
                continue
            if _before_cutoff(available_at=match.provenance.available_at, event_at=match.kickoff_at, cutoff=cutoff):
                selected.append(match)
        return selected

    def odds_as_of(self, match_id: str, cutoff: datetime) -> OddsSnapshot | None:
        eligible = [
            snapshot
            for snapshot in self._sink.odds.values()
            if snapshot.match_id == match_id and _as_of(snapshot.provenance.available_at, None, cutoff)
        ]
        if not eligible:
            return None
        return max(eligible, key=lambda item: item.provenance.available_at)

    def standings_as_of(self, league_id: str, cutoff: datetime) -> list[StandingSnapshot]:
        return [
            row
            for row in self._sink.standings
            if row.league_id == league_id and _as_of(row.provenance.available_at, row.as_of, cutoff)
        ]

    def team_stats_as_of(self, team_id: str, cutoff: datetime) -> list[TeamStats]:
        return [
            row
            for row in self._sink.team_stats
            if row.team_id == team_id and _as_of(row.provenance.available_at, row.as_of, cutoff)
        ]

    def injuries_as_of(self, team_id: str, cutoff: datetime) -> list[Injury]:
        return [
            row
            for row in self._sink.injuries.values()
            if row.team_id == team_id and _as_of(row.provenance.available_at, row.provenance.event_at, cutoff)
        ]

    def lineups_as_of(self, match_id: str, cutoff: datetime) -> list[Lineup]:
        return [
            row
            for row in self._sink.lineups.values()
            if row.match_id == match_id and _as_of(row.provenance.available_at, row.provenance.event_at, cutoff)
        ]

    def features_for_match(self, match_id: str, cutoff: datetime) -> dict[str, object]:
        match = self._sink.matches[match_id]
        self.assert_pre_kickoff(match, cutoff)
        if match.id in {item.id for item in self.matches_finished_before(cutoff)}:
            raise DataLeakageError("The target match result is not a legal pre-match feature.")
        return {
            "match_id": match.id,
            "cutoff_at": cutoff,
            "prior_matches": [item.id for item in self.matches_finished_before(cutoff)],
            "odds": self.odds_as_of(match.id, cutoff),
            "standings": self.standings_as_of(match.league_id, cutoff),
            "home_stats": self.team_stats_as_of(match.home_team_id or "", cutoff) if match.home_team_id else [],
            "away_stats": self.team_stats_as_of(match.away_team_id or "", cutoff) if match.away_team_id else [],
            "home_injuries": self.injuries_as_of(match.home_team_id or "", cutoff) if match.home_team_id else [],
            "lineups": self.lineups_as_of(match.id, cutoff),
        }


def _as_of(available_at: datetime, event_at: datetime | None, cutoff: datetime) -> bool:
    return _before_cutoff(available_at=available_at, event_at=event_at, cutoff=cutoff)
