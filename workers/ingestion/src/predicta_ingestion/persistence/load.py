from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from predicta_ingestion.canonical.enums import DataMode, EntityType, Freshness, MatchStatus, ResolutionMethod, SportCode
from predicta_ingestion.canonical.models import League, Match, OddsSelection, OddsSnapshot, Provenance, Sport, Team
from predicta_ingestion.clock import ensure_utc
from predicta_ingestion.identity.aliases import aliased_natural_keys
from predicta_ingestion.identity.keys import team_name_key
from predicta_ingestion.identity.resolver import IdentityBinding, IdentityResolver
from predicta_ingestion.ids import slugify
from predicta_ingestion.persistence.memory import MemoryCanonicalSink
from predicta_ingestion.providers.the_odds_api import LIVE_ODDS_PROVIDER


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
            text(
                """
                SELECT id, sport_id, name, country, season, tier, slug, provider_season_id, created_at
                FROM leagues
                """
            )
        ).mappings():
            created = _utc(row["created_at"])
            sink.leagues[row["id"]] = League(
                id=row["id"],
                sport_id=row["sport_id"],
                name=row["name"],
                country=row["country"],
                season=row["season"],
                tier=row["tier"],
                competition_id=row["slug"],
                provider_season_id=row["provider_season_id"],
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
        _load_odds(connection, sink)
    return sink


def hydrate_resolver_from_sql(resolver: IdentityResolver, engine: Engine) -> int:
    """Load provider_entity_maps so sequential competition ingest reuses canonical ids."""
    bindings: list[IdentityBinding] = []
    with engine.connect() as connection:
        teams = {
            row["id"]: Team(
                id=row["id"],
                sport_id=row["sport_id"],
                league_id=row["league_id"],
                name=row["name"],
                short_name=row["short_name"],
                abbreviation=row["abbreviation"],
                provenance=_catalog_provenance(row["id"], _utc(row["created_at"])),
            )
            for row in connection.execute(
                text("SELECT id, sport_id, league_id, name, short_name, abbreviation, created_at FROM teams")
            ).mappings()
        }
        leagues = {
            row["id"]: League(
                id=row["id"],
                sport_id=row["sport_id"],
                name=row["name"],
                country=row["country"],
                season=row["season"],
                tier=row["tier"],
                competition_id=row["slug"] if "slug" in row else None,
                provider_season_id=row["provider_season_id"] if "provider_season_id" in row else None,
                provenance=_catalog_provenance(row["id"], _utc(row["created_at"])),
            )
            for row in connection.execute(
                text(
                    """
                    SELECT id, sport_id, name, country, season, tier, slug, provider_season_id, created_at
                    FROM leagues
                    """
                )
            ).mappings()
        }
        for row in connection.execute(
            text(
                """
                SELECT provider, entity_type, provider_entity_id, canonical_id,
                       resolution_method, confidence
                FROM provider_entity_maps
                """
            )
        ).mappings():
            entity_type = EntityType(row["entity_type"])
            method_raw = row["resolution_method"] or ResolutionMethod.EXACT_ID.value
            try:
                method = ResolutionMethod(method_raw)
            except ValueError:
                method = ResolutionMethod.EXACT_ID
            name_key = None
            display_name = None
            if entity_type is EntityType.TEAM:
                team = teams.get(row["canonical_id"])
                if team is not None:
                    name_key, _aliased = team_name_key(team, leagues.get(team.league_id))
                    display_name = team.name
            bindings.append(
                IdentityBinding(
                    provider=row["provider"],
                    entity_type=entity_type,
                    provider_entity_id=row["provider_entity_id"],
                    canonical_id=row["canonical_id"],
                    method=method,
                    confidence=float(row["confidence"] or 1.0),
                    name_key=name_key,
                    display_name=display_name,
                )
            )
    resolver.hydrate(bindings)
    return len(bindings)


def hydrate_match_keys_from_sql(resolver: IdentityResolver, engine: Engine) -> int:
    """Rebuild football|home|away|kickoff keys from persisted matches. Names are never guessed."""
    count = 0
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT m.id, m.kickoff_at, m.home_team_id, m.away_team_id,
                       ht.name AS home_name, at.name AS away_name
                FROM matches m
                JOIN teams ht ON ht.id = m.home_team_id
                JOIN teams at ON at.id = m.away_team_id
                """
            )
        ).mappings()
        for row in rows:
            kickoff = _utc(row["kickoff_at"])
            natural_key = (
                f"{SportCode.FOOTBALL.value}|{slugify(row['home_name'])}|"
                f"{slugify(row['away_name'])}|{kickoff.isoformat()}"
            )
            resolver.bind_match_natural_key(natural_key, row["id"])
            for aliased_key in aliased_natural_keys(
                provider=LIVE_ODDS_PROVIDER,
                home_team_id=str(row["home_team_id"]),
                away_team_id=str(row["away_team_id"]),
                home_name=str(row["home_name"]),
                away_name=str(row["away_name"]),
                kickoff=kickoff,
            ):
                resolver.bind_match_natural_key(aliased_key, row["id"])
            count += 1
    return count


def _load_odds(connection: Any, sink: MemoryCanonicalSink) -> None:
    selections_by_snapshot: dict[str, list[OddsSelection]] = {}
    for row in connection.execute(
        text(
            """
            SELECT snapshot_id, selection, label, decimal_odds
            FROM odds_selections
            ORDER BY snapshot_id, selection
            """
        )
    ).mappings():
        if row["decimal_odds"] is None:
            continue
        selections_by_snapshot.setdefault(row["snapshot_id"], []).append(
            OddsSelection(
                selection=row["selection"],
                label=row["label"],
                decimal_odds=Decimal(str(row["decimal_odds"])),
            )
        )
    for row in connection.execute(
        text(
            """
            SELECT id, provider_id, match_id, market, bookmaker, provider,
                   available_at, collected_at, source, freshness, data_mode, raw_payload_id
            FROM odds_snapshots
            """
        )
    ).mappings():
        selections = selections_by_snapshot.get(row["id"], [])
        if not selections:
            continue
        freshness = None
        if row["freshness"]:
            try:
                freshness = Freshness(row["freshness"])
            except ValueError:
                freshness = None
        sink.odds[row["id"]] = OddsSnapshot(
            id=row["id"],
            match_id=row["match_id"],
            market=row["market"],
            bookmaker=row["bookmaker"],
            selections=selections,
            provenance=Provenance(
                provider=row["provider"],
                provider_id=row["provider_id"],
                collected_at=_utc(row["collected_at"]),
                available_at=_utc(row["available_at"]),
                source=row["source"],
                data_mode=DataMode(row["data_mode"]),
                freshness=freshness,
                raw_payload_id=row["raw_payload_id"],
            ),
        )


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
