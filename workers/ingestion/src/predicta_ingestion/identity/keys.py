from __future__ import annotations

from predicta_ingestion.canonical.models import League, Team
from predicta_ingestion.identity.historical import franchise_key
from predicta_ingestion.ids import slugify
from predicta_ingestion.providers.leagues import V1_LEAGUE_BY_SPORTMONKS_ID


def league_provider_key(league_provider_id: str, season: str) -> str:
    if ":" in league_provider_id:
        return league_provider_id
    return f"{league_provider_id}:{season}"


def competition_slug(league: League | None) -> str:
    if league is None:
        return "unknown"
    raw_id = league.provenance.provider_id.split(":", 1)[0]
    try:
        catalog = V1_LEAGUE_BY_SPORTMONKS_ID.get(int(raw_id))
    except ValueError:
        catalog = None
    if catalog is not None:
        return catalog.slug
    return slugify(league.name)


def team_name_key(team: Team, league: League | None) -> tuple[str, bool]:
    competition = competition_slug(league)
    franchise, aliased = franchise_key(competition, team.name)
    return f"{team.sport_id}:{competition}:{franchise}", aliased
