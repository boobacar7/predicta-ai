from __future__ import annotations

from dataclasses import dataclass

from predicta_ingestion.errors import ValidationError

MLS_SLUG = "mls"
EUROPEAN_HISTORY_SEASON_LIMIT = 3


@dataclass(frozen=True)
class V1FootballLeague:
    slug: str
    name: str
    country: str
    sportmonks_id: int


# Sportmonks Football API v3 provider ids. These are not PREDICTA canonical ids.
V1_FOOTBALL_LEAGUES: tuple[V1FootballLeague, ...] = (
    V1FootballLeague(MLS_SLUG, "Major League Soccer", "USA", 779),
    V1FootballLeague("premier-league", "Premier League", "England", 8),
    V1FootballLeague("la-liga", "La Liga", "Spain", 564),
    V1FootballLeague("bundesliga", "Bundesliga", "Germany", 82),
    V1FootballLeague("serie-a", "Serie A", "Italy", 384),
    V1FootballLeague("ligue-1", "Ligue 1", "France", 301),
    V1FootballLeague("champions-league", "UEFA Champions League", "Europe", 2),
)

EUROPEAN_V1_LEAGUES: tuple[V1FootballLeague, ...] = tuple(item for item in V1_FOOTBALL_LEAGUES if item.slug != MLS_SLUG)

V1_LEAGUE_BY_SLUG = {item.slug: item for item in V1_FOOTBALL_LEAGUES}
V1_LEAGUE_BY_SPORTMONKS_ID = {item.sportmonks_id: item for item in V1_FOOTBALL_LEAGUES}

LEAGUE_ALIASES = {
    "mls": MLS_SLUG,
    "MLS": MLS_SLUG,
    "major-league-soccer": MLS_SLUG,
    "major league soccer": MLS_SLUG,
    "epl": "premier-league",
    "premier league": "premier-league",
    "laliga": "la-liga",
    "la liga": "la-liga",
    "ucl": "champions-league",
    "champions league": "champions-league",
    "serie a": "serie-a",
    "ligue 1": "ligue-1",
    "ligue1": "ligue-1",
}


def normalize_league_slug(slug: str) -> str:
    return LEAGUE_ALIASES.get(slug, slug)


def resolve_v1_leagues(slug: str | None) -> tuple[V1FootballLeague, ...]:
    if slug in (None, "", "all"):
        return V1_FOOTBALL_LEAGUES
    normalized = normalize_league_slug(slug)
    league = V1_LEAGUE_BY_SLUG.get(normalized)
    if league is None:
        known = ", ".join(item.slug for item in V1_FOOTBALL_LEAGUES)
        raise ValidationError("unknown_league", f"Unknown V1 league '{slug}'. Supported: {known}.")
    return (league,)


def is_mls(league: V1FootballLeague) -> bool:
    return league.slug == MLS_SLUG
