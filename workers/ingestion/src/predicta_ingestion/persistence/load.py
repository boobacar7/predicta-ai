from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from predicta_ingestion.canonical.enums import DataMode, MatchStatus, SportCode
from predicta_ingestion.canonical.models import League, Match, Provenance, Sport, Team
from predicta_ingestion.clock import ensure_utc
from predicta_ingestion.persistence.memory import MemoryCanonicalSink


def load_memory_sink(engine: Engine) -> MemoryCanonicalSink:
    """Load already-ingested canonical rows from PostgreSQL. Does not invent facts."""
    sink = MemoryCanonicalSink()
    with engine.connect() as connection:
        for row in connection.execute(text("SELECT id, code, name, created_at FROM sports")).mappings():
            created = _utc(row["created_at"])
            sink.sports[row["id"]] = Sport(
                id=row["id"],
                code=SportCode(row["code"]),
                name=row["name"],
                provenance=_catalog_provenance(row["id"], created),
            )
        for row in connection.execute(
            text("SELECT id, sport_id, name, country, season, tier, created_at FROM leagues")
        ).mappings():
            created = _utc(row["created_at"])
            sink.leagues[row["id"]] = League(
                id=row["id"],
                sport_id=row["sport_id"],
                name=row["name"],
                country=row["country"],
                season=row["season"],
                tier=row["tier"],
                provenance=_catalog_provenance(row["id"], created),
            )
        for row in connection.execute(
            text("SELECT id, sport_id, league_id, name, short_name, abbreviation, created_at FROM teams")
        ).mappings():
            created = _utc(row["created_at"])
            sink.teams[row["id"]] = Team(
                id=row["id"],
                sport_id=row["sport_id"],
                league_id=row["league_id"],
                name=row["name"],
                short_name=row["short_name"],
                abbreviation=row["abbreviation"],
                provenance=_catalog_provenance(row["id"], created),
            )
        for row in connection.execute(
            text(
                """
                SELECT id, sport_id, league_id, home_team_id, away_team_id, kickoff_at, status,
                       venue, home_score, away_score, source, collected_at, available_at,
                       data_mode, raw_payload_id, created_at
                FROM matches
                """
            )
        ).mappings():
            match = _match_from_row(dict(row))
            sink.matches[match.id] = match
    return sink


def _match_from_row(row: dict[str, Any]) -> Match:
    kickoff = _utc(row["kickoff_at"])
    collected = _utc(row["collected_at"] or row["created_at"] or kickoff)
    available = _utc(row["available_at"] or collected)
    mode = DataMode(row["data_mode"]) if row.get("data_mode") else DataMode.LIVE
    return Match(
        id=row["id"],
        sport_id=row["sport_id"],
        league_id=row["league_id"],
        kickoff_at=kickoff,
        status=MatchStatus(row["status"]),
        home_team_id=row["home_team_id"],
        away_team_id=row["away_team_id"],
        venue=row["venue"],
        home_score=row["home_score"],
        away_score=row["away_score"],
        provenance=Provenance(
            provider=str(row.get("source") or "sportmonks"),
            provider_id=row["id"],
            collected_at=collected,
            available_at=available,
            event_at=kickoff,
            source=str(row.get("source") or "sportmonks"),
            data_mode=mode,
            raw_payload_id=row.get("raw_payload_id"),
        ),
    )


def _catalog_provenance(provider_id: str, created_at: datetime) -> Provenance:
    return Provenance(
        provider="sportmonks",
        provider_id=provider_id,
        collected_at=created_at,
        available_at=created_at,
        source="sportmonks",
        data_mode=DataMode.LIVE,
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return ensure_utc(value)
