from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from predicta_ingestion.canonical.enums import MatchStatus
from predicta_ingestion.canonical.models import (
    CanonicalBatch,
    Injury,
    League,
    Lineup,
    Match,
    MatchEvent,
    OddsSnapshot,
    Player,
    PlayerStats,
    Sport,
    StandingSnapshot,
    Team,
    TeamStats,
)
from predicta_ingestion.quality.quarantine import QuarantineItem


@dataclass
class PersistResult:
    inserted: int = 0
    duplicates: int = 0
    quarantined: list[QuarantineItem] = field(default_factory=list)


T = TypeVar("T")


class CanonicalSink(Protocol):
    def persist(self, batch: CanonicalBatch) -> PersistResult: ...


class MemoryCanonicalSink:
    """In-memory canonical store used by tests and the ML PIT reader."""

    def __init__(self) -> None:
        self.sports: dict[str, Sport] = {}
        self.leagues: dict[str, League] = {}
        self.teams: dict[str, Team] = {}
        self.players: dict[str, Player] = {}
        self.matches: dict[str, Match] = {}
        self.events: dict[str, MatchEvent] = {}
        self.team_stats: list[TeamStats] = []
        self.player_stats: list[PlayerStats] = []
        self.odds: dict[str, OddsSnapshot] = {}
        self.standings: list[StandingSnapshot] = []
        self.injuries: dict[str, Injury] = {}
        self.lineups: dict[str, Lineup] = {}
        self.raw_checksums: set[str] = set()

    def persist(self, batch: CanonicalBatch) -> PersistResult:
        result = PersistResult()
        result.inserted += self._upsert_map(self.sports, {item.id: item for item in batch.sports})
        result.inserted += self._upsert_map(self.leagues, {item.id: item for item in batch.leagues})
        result.inserted += self._upsert_map(self.teams, {item.id: item for item in batch.teams})
        result.inserted += self._upsert_map(self.players, {item.id: item for item in batch.players})
        result.inserted += self._upsert_map(self.matches, {item.id: item for item in batch.matches})
        result.inserted += self._upsert_map(self.events, {item.id: item for item in batch.events})
        result.inserted += self._upsert_map(self.injuries, {item.id: item for item in batch.injuries})
        result.inserted += self._upsert_map(self.lineups, {item.id: item for item in batch.lineups})
        for snapshot in batch.odds:
            if snapshot.id in self.odds:
                result.duplicates += 1
                continue
            self.odds[snapshot.id] = snapshot
            result.inserted += 1
        self.team_stats.extend(self._dedupe_stats(self.team_stats, batch.team_stats, result))
        self.player_stats.extend(self._dedupe_player_stats(batch.player_stats, result))
        self.standings.extend(self._dedupe_standings(batch.standings, result))
        return result

    def remember_checksum(self, checksum: str) -> bool:
        if checksum in self.raw_checksums:
            return True
        self.raw_checksums.add(checksum)
        return False

    def finished_matches(self) -> list[Match]:
        return [match for match in self.matches.values() if match.status is MatchStatus.FINISHED]

    def _upsert_map(self, target: dict[str, T], incoming: dict[str, T]) -> int:
        inserted = 0
        for key, value in incoming.items():
            if key in target:
                continue
            target[key] = value
            inserted += 1
        return inserted

    def _dedupe_stats(
        self, existing: list[TeamStats], incoming: list[TeamStats], result: PersistResult
    ) -> list[TeamStats]:
        seen = {(item.team_id, item.season, item.stat_key, item.as_of, item.provenance.provider) for item in existing}
        accepted: list[TeamStats] = []
        for item in incoming:
            key = (item.team_id, item.season, item.stat_key, item.as_of, item.provenance.provider)
            if key in seen:
                result.duplicates += 1
                continue
            seen.add(key)
            accepted.append(item)
            result.inserted += 1
        return accepted

    def _dedupe_player_stats(self, incoming: list[PlayerStats], result: PersistResult) -> list[PlayerStats]:
        seen = {
            (item.player_id, item.season, item.stat_key, item.as_of, item.provenance.provider)
            for item in self.player_stats
        }
        accepted: list[PlayerStats] = []
        for item in incoming:
            key = (item.player_id, item.season, item.stat_key, item.as_of, item.provenance.provider)
            if key in seen:
                result.duplicates += 1
                continue
            seen.add(key)
            accepted.append(item)
            result.inserted += 1
        return accepted

    def _dedupe_standings(self, incoming: list[StandingSnapshot], result: PersistResult) -> list[StandingSnapshot]:
        seen = {
            (item.league_id, item.season, item.team_id, item.as_of, item.provenance.provider)
            for item in self.standings
        }
        accepted: list[StandingSnapshot] = []
        for item in incoming:
            key = (item.league_id, item.season, item.team_id, item.as_of, item.provenance.provider)
            if key in seen:
                result.duplicates += 1
                continue
            seen.add(key)
            accepted.append(item)
            result.inserted += 1
        return accepted
