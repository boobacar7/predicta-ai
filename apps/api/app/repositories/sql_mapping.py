"""Map canonical PostgreSQL rows onto OpenAPI catalog/match schemas.

Missing related payloads stay unavailable. This module never invents odds,
stats, predictions, standings, injuries, or scores.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.db.models import League as LeagueRow
from app.db.models import Match as MatchRow
from app.db.models import Player as PlayerRow
from app.db.models import Sport as SportRow
from app.db.models import Team as TeamRow
from app.schemas import (
    DataQuality,
    League,
    MatchDetail,
    MatchStatus,
    NamedStat,
    Player,
    Scoreline,
    Sport,
    SportCode,
    Team,
    UnavailableField,
)

CATALOG_UNAVAILABLE_FIELDS: tuple[UnavailableField, ...] = (
    UnavailableField(field="odds", reason="Odds are not published on the catalog read path."),
    UnavailableField(field="prediction", reason="Predictions are not published on the catalog read path."),
    UnavailableField(field="stats", reason="Match statistics are not published in the catalog store."),
    UnavailableField(field="timeline", reason="Match events are not published in the catalog store."),
    UnavailableField(field="form", reason="Team form is not published in the catalog store."),
)

STANDING_UNAVAILABLE = UnavailableField(
    field="standing",
    reason="Standings are not published in the catalog store.",
)
TEAM_STATS_UNAVAILABLE = UnavailableField(
    field="stats",
    reason="Team statistics are not published in the catalog store.",
)
INJURIES_UNAVAILABLE = UnavailableField(
    field="injuries",
    reason="Injuries are never invented when the live store has no injury rows.",
)
PLAYER_STATS_UNAVAILABLE = UnavailableField(
    field="stats",
    reason="Player statistics are not published in the catalog store.",
)
PLAYER_AVAILABILITY_UNAVAILABLE = UnavailableField(
    field="availability",
    reason="Player availability is never invented.",
)


def unavailable_quality(*, note: str) -> DataQuality:
    return DataQuality(
        availability="unavailable",
        source=None,
        observed_at=None,
        freshness=None,
        note=note,
    )


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def as_sport_code(value: str) -> SportCode | None:
    if value == "football" or value == "basketball" or value == "tennis":
        return value
    return None


def as_match_status(value: str) -> MatchStatus | None:
    if value == "scheduled" or value == "live" or value == "finished" or value == "postponed":
        return value
    return None


def map_sport(row: SportRow) -> Sport | None:
    code = as_sport_code(row.code)
    if code is None:
        return None
    return Sport(id=row.id, name=row.name, code=code)


def map_league(row: LeagueRow, sport: SportRow) -> League | None:
    code = as_sport_code(sport.code)
    if code is None or row.tier < 1:
        return None
    return League(
        id=row.id,
        name=row.name,
        sport=code,
        country=row.country,
        season=row.season,
        tier=row.tier,
    )


def map_team(row: TeamRow, sport: SportRow) -> Team | None:
    code = as_sport_code(sport.code)
    if code is None:
        return None
    return Team(
        id=row.id,
        name=row.name,
        short_name=row.short_name,
        sport=code,
        league_id=row.league_id,
        abbreviation=row.abbreviation,
    )


def map_player(row: PlayerRow, sport: SportRow) -> Player | None:
    code = as_sport_code(sport.code)
    if code is None:
        return None
    return Player(
        id=row.id,
        name=row.name,
        sport=code,
        team_id=row.team_id,
        position=row.position,
        country=row.country,
    )


def map_score(row: MatchRow) -> Scoreline:
    if row.home_score is None and row.away_score is None:
        return Scoreline(
            home=None,
            away=None,
            quality=unavailable_quality(note="Score is not published for this match yet."),
        )
    availability = "available" if row.home_score is not None and row.away_score is not None else "partial"
    return Scoreline(
        home=row.home_score,
        away=row.away_score,
        quality=DataQuality(
            availability=availability,
            source=row.source,
            observed_at=as_utc(row.collected_at) if row.collected_at is not None else None,
            freshness=None,
            note=None,
        ),
    )


def map_match(
    row: MatchRow,
    sport: SportRow,
    league: LeagueRow,
    home: TeamRow,
    away: TeamRow,
) -> MatchDetail | None:
    status = as_match_status(row.status)
    mapped_league = map_league(league, sport)
    mapped_home = map_team(home, sport)
    mapped_away = map_team(away, sport)
    sport_code = as_sport_code(sport.code)
    if status is None or mapped_league is None or mapped_home is None or mapped_away is None or sport_code is None:
        return None
    return MatchDetail(
        id=row.id,
        sport=sport_code,
        league=mapped_league,
        home=mapped_home,
        away=mapped_away,
        kickoff_at=as_utc(row.kickoff_at),
        status=status,
        venue=row.venue,
        score=map_score(row),
        prediction_preview=None,
        value_preview=None,
        quality=DataQuality(
            availability="available",
            source=row.source,
            observed_at=as_utc(row.collected_at) if row.collected_at is not None else None,
            freshness=None,
            note="Catalog identity from the live store. Odds, stats and predictions are not inferred.",
        ),
        timeline=[],
        stats=[],
        odds=None,
        prediction=None,
        form=[],
        unavailable_fields=list(CATALOG_UNAVAILABLE_FIELDS),
    )


def unpublished_injury_stat() -> NamedStat:
    return NamedStat(
        key="injuries",
        label="Injuries",
        value=None,
        unit=None,
        quality=unavailable_quality(note="Injuries are never invented when the live store has no injury rows."),
    )
