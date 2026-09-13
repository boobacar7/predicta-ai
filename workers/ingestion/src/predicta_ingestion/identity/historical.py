from __future__ import annotations

from datetime import datetime

from predicta_ingestion.canonical.enums import SportCode
from predicta_ingestion.ids import slugify

MLS_SLUG = "mls"

# Explicit, documented MLS franchise name keys. Keys and values are slugify() output.
# This is not fuzzy matching: only these exact slugs are treated as the same club.
MLS_NAME_ALIASES: dict[str, str] = {
    "atlanta-united": "atlanta-united",
    "atlanta-united-fc": "atlanta-united",
    "austin": "austin-fc",
    "austin-fc": "austin-fc",
    "cf-montreal": "cf-montreal",
    "cf-montreal-impact": "cf-montreal",
    "chicago-fire": "chicago-fire",
    "chicago-fire-fc": "chicago-fire",
    "club-de-foot-montreal": "cf-montreal",
    "colorado-rapids": "colorado-rapids",
    "columbus-crew": "columbus-crew",
    "columbus-crew-sc": "columbus-crew",
    "dc-united": "dc-united",
    "d-c-united": "dc-united",
    "fc-cincinnati": "fc-cincinnati",
    "fc-dallas": "fc-dallas",
    "houston-dynamo": "houston-dynamo",
    "houston-dynamo-fc": "houston-dynamo",
    "inter-miami": "inter-miami",
    "inter-miami-cf": "inter-miami",
    "la-galaxy": "la-galaxy",
    "lafc": "los-angeles-fc",
    "los-angeles-fc": "los-angeles-fc",
    "los-angeles-galaxy": "la-galaxy",
    "minnesota-united": "minnesota-united",
    "minnesota-united-fc": "minnesota-united",
    "montreal-impact": "cf-montreal",
    "nashville": "nashville-sc",
    "nashville-sc": "nashville-sc",
    "new-england-revolution": "new-england-revolution",
    "new-york-city": "new-york-city-fc",
    "new-york-city-fc": "new-york-city-fc",
    "new-york-red-bulls": "new-york-red-bulls",
    "nycfc": "new-york-city-fc",
    "ny-red-bulls": "new-york-red-bulls",
    "orlando-city": "orlando-city",
    "orlando-city-sc": "orlando-city",
    "philadelphia-union": "philadelphia-union",
    "portland-timbers": "portland-timbers",
    "real-salt-lake": "real-salt-lake",
    "red-bull-new-york": "new-york-red-bulls",
    "san-diego": "san-diego-fc",
    "san-diego-fc": "san-diego-fc",
    "san-jose-earthquakes": "san-jose-earthquakes",
    "seattle-sounders": "seattle-sounders",
    "seattle-sounders-fc": "seattle-sounders",
    "sj-earthquakes": "san-jose-earthquakes",
    "sporting-kansas-city": "sporting-kansas-city",
    "st-louis-city": "st-louis-city-sc",
    "st-louis-city-sc": "st-louis-city-sc",
    "toronto-fc": "toronto-fc",
    "vancouver-whitecaps": "vancouver-whitecaps",
    "vancouver-whitecaps-fc": "vancouver-whitecaps",
}

# Optional Sportmonks team id -> franchise key. Empty unless a provider id change is documented.
MLS_PROVIDER_ID_ALIASES: dict[str, str] = {}


def franchise_key(competition_slug: str, name: str) -> tuple[str, bool]:
    """Return (franchise_key, used_explicit_alias). Unknown names keep their own slug."""
    slug = slugify(name)
    if competition_slug != MLS_SLUG:
        return slug, False
    aliased = MLS_NAME_ALIASES.get(slug)
    if aliased is None:
        return slug, False
    return aliased, aliased != slug


def provider_franchise_key(competition_slug: str, provider_team_id: str) -> str | None:
    if competition_slug != MLS_SLUG:
        return None
    return MLS_PROVIDER_ID_ALIASES.get(provider_team_id)


def mls_slugs_for_name(name: str) -> tuple[str, ...]:
    """Exact MLS franchise slug set. Unknown names keep their own slug only."""
    slug = slugify(name)
    franchise, _aliased = franchise_key(MLS_SLUG, name)
    slugs = {slug, franchise}
    for alias_slug, canonical in MLS_NAME_ALIASES.items():
        if canonical == franchise:
            slugs.add(alias_slug)
    return tuple(sorted(slugs))


def mls_franchise_natural_keys(home_name: str, away_name: str, kickoff: datetime) -> tuple[str, ...]:
    """Extra football|home|away|kickoff keys from the existing MLS franchise table."""
    original = f"{SportCode.FOOTBALL.value}|{slugify(home_name)}|{slugify(away_name)}|{kickoff.isoformat()}"
    keys: list[str] = []
    seen = {original}
    for home_slug in mls_slugs_for_name(home_name):
        for away_slug in mls_slugs_for_name(away_name):
            key = f"{SportCode.FOOTBALL.value}|{home_slug}|{away_slug}|{kickoff.isoformat()}"
            if key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return tuple(keys)
