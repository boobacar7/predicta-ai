from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from predicta_ingestion.canonical.enums import SportCode
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.ids import slugify
from predicta_ingestion.providers.the_odds_api import LIVE_ODDS_PROVIDER

ALIAS_TABLE_VERSION = "the-odds-api-team-aliases-v1"

# Names that must never share an alias. Observed as distinct Sportmonks clubs
# and/or distinct Odds API tokens in the 2026-09-11 live validation.
ISOLATED_TEAM_NAMES: tuple[str, ...] = (
    "Paris",
    "Paris FC",
    "Paris Saint-Germain",
    "Paris Saint Germain",
    "PSG",
)


@dataclass(frozen=True)
class ProviderTeamAlias:
    """Exact provider name → one canonical team. Not a similarity score."""

    provider: str
    provider_team_name: str
    canonical_team_id: str
    canonical_team_name: str
    evidence: str

    @property
    def provider_slug(self) -> str:
        return slugify(self.provider_team_name)

    @property
    def canonical_slug(self) -> str:
        return slugify(self.canonical_team_name)


def _alias(
    provider_team_name: str,
    *,
    canonical_team_id: str,
    canonical_team_name: str,
    evidence: str,
) -> ProviderTeamAlias:
    return ProviderTeamAlias(
        provider=LIVE_ODDS_PROVIDER,
        provider_team_name=provider_team_name,
        canonical_team_id=canonical_team_id,
        canonical_team_name=canonical_team_name,
        evidence=evidence,
    )


# Only mappings demonstrated on real The Odds API v4 events vs Sportmonks
# (docs/qa/live-odds-real-validation.md §6, docs/qa/oos-odds-expansion.md,
# staging Serie A ingest 2026-09-14). Paris / Paris FC / PSG are
# intentionally absent: they stay distinct, even when a fixture looks related.
# Inter Milan maps to Inter, never to AC Milan or Inter Miami.
_RAW_TEAM_ALIASES: tuple[ProviderTeamAlias, ...] = (
    _alias(
        "Bournemouth",
        canonical_team_id="tm_football-sportmonks-52",
        canonical_team_name="AFC Bournemouth",
        evidence="2026-09-11 Odds API Bournemouth vs AFC Bournemouth, prefix AFC.",
    ),
    _alias(
        "Brighton and Hove Albion",
        canonical_team_id="tm_football-sportmonks-78",
        canonical_team_name="Brighton & Hove Albion",
        evidence="2026-09-11 Odds API Brighton and Hove Albion vs Brighton & Hove Albion.",
    ),
    _alias(
        "Marseille",
        canonical_team_id="tm_football-sportmonks-44",
        canonical_team_name="Olympique Marseille",
        evidence="2026-09-11 Odds API Marseille vs Olympique Marseille, prefix Olympique.",
    ),
    _alias(
        "AS Monaco",
        canonical_team_id="tm_football-sportmonks-6789",
        canonical_team_name="Monaco",
        evidence="2026-09-11 Odds API AS Monaco vs Sportmonks Monaco, kickoff 2026-09-12T15:15:00Z, prefix AS.",
    ),
    _alias(
        "Angers",
        canonical_team_id="tm_football-sportmonks-776",
        canonical_team_name="Angers SCO",
        evidence="2026-09-11 Odds API Angers vs Sportmonks Angers SCO, kickoff 2026-09-12T18:45:00Z, suffix SCO.",
    ),
    _alias(
        "Lille",
        canonical_team_id="tm_football-sportmonks-690",
        canonical_team_name="LOSC Lille",
        evidence="2026-09-11 Odds API Lille vs Sportmonks LOSC Lille, kickoff 2026-09-13T13:00:00Z, prefix LOSC.",
    ),
    _alias(
        "Le Mans FC",
        canonical_team_id="tm_football-sportmonks-7758",
        canonical_team_name="Le Mans",
        evidence="2026-09-11 Odds API Le Mans FC vs Sportmonks Le Mans, kickoff 2026-09-13T15:15:00Z, suffix FC.",
    ),
    _alias(
        "RC Lens",
        canonical_team_id="tm_football-sportmonks-271",
        canonical_team_name="Lens",
        evidence="2026-09-11 Odds API RC Lens vs Sportmonks Lens, kickoff 2026-09-13T15:15:00Z, prefix RC.",
    ),
    _alias(
        "Lyon",
        canonical_team_id="tm_football-sportmonks-79",
        canonical_team_name="Olympique Lyonnais",
        evidence="2026-09-11 Odds API Lyon vs Olympique Lyonnais, prefix Olympique.",
    ),
    _alias(
        "Inter Milan",
        canonical_team_id="tm_football-sportmonks-2930",
        canonical_team_name="Inter",
        evidence=(
            "Staging Serie A ingest Odds API Inter Milan vs Udinese "
            "football|inter-milan|udinese|2026-09-14T18:45:00+00:00 vs Sportmonks Inter. "
            "OOS uncovered Inter vs Monza mth_football-sportmonks-19713613."
        ),
    ),
    _alias(
        "AS Roma",
        canonical_team_id="tm_football-sportmonks-37",
        canonical_team_name="Roma",
        evidence=(
            "Staging Serie A ingest Odds API Torino vs AS Roma "
            "football|torino|as-roma|2026-09-14T16:30:00+00:00 vs Sportmonks Roma. "
            "OOS uncovered Roma vs Fiorentina mth_football-sportmonks-19713611."
        ),
    ),
    _alias(
        "Atalanta BC",
        canonical_team_id="tm_football-sportmonks-708",
        canonical_team_name="Atalanta",
        evidence=(
            "OOS unmatched Odds API names include Atalanta BC vs Sportmonks Atalanta. "
            "Atalanta vs Sassuolo mth_football-sportmonks-19713617 kickoff 2026-08-23T18:45:00Z."
        ),
    ),
)


class AliasTableError(ValidationError):
    def __init__(self, detail: str) -> None:
        super().__init__("ambiguous_alias", detail)


def validate_alias_table(
    aliases: tuple[ProviderTeamAlias, ...] | list[ProviderTeamAlias],
) -> tuple[ProviderTeamAlias, ...]:
    """Refuse ambiguous or incomplete alias rows. Never fuzzy-merges names."""
    by_key: dict[tuple[str, str], ProviderTeamAlias] = {}
    for item in aliases:
        if item.provider != LIVE_ODDS_PROVIDER:
            raise AliasTableError(f"Unsupported alias provider '{item.provider}'.")
        if not item.provider_team_name.strip() or not item.canonical_team_name.strip():
            raise AliasTableError("Alias names must be non-empty.")
        if not item.canonical_team_id.startswith("tm_"):
            raise AliasTableError(f"Alias canonical_team_id '{item.canonical_team_id}' is not a team id.")
        if item.provider_slug == item.canonical_slug:
            raise AliasTableError(
                f"Alias '{item.provider_team_name}' is identical to canonical "
                f"'{item.canonical_team_name}' after slugify; exact keys already match."
            )
        key = (item.provider, item.provider_slug)
        existing = by_key.get(key)
        if existing is not None and existing.canonical_team_id != item.canonical_team_id:
            raise AliasTableError(
                f"Provider name '{item.provider_team_name}' maps to both "
                f"{existing.canonical_team_id} and {item.canonical_team_id}."
            )
        if existing is not None:
            raise AliasTableError(f"Duplicate alias for provider name '{item.provider_team_name}'.")
        by_key[key] = item
    return tuple(by_key.values())


TEAM_ALIASES = validate_alias_table(_RAW_TEAM_ALIASES)
_ALIAS_BY_PROVIDER_SLUG: dict[tuple[str, str], ProviderTeamAlias] = {
    (item.provider, item.provider_slug): item for item in TEAM_ALIASES
}


def lookup_team_alias(provider: str, provider_team_name: str) -> ProviderTeamAlias | None:
    return _ALIAS_BY_PROVIDER_SLUG.get((provider, slugify(provider_team_name)))


def lookup_team_alias_slug(provider: str, provider_slug: str) -> ProviderTeamAlias | None:
    return _ALIAS_BY_PROVIDER_SLUG.get((provider, provider_slug))


def canonical_slug_for_provider_slug(provider: str, provider_slug: str) -> str:
    alias = lookup_team_alias_slug(provider, provider_slug)
    return provider_slug if alias is None else alias.canonical_slug


def apply_team_name_aliases(natural_key: str, provider: str) -> str:
    """Rewrite football|home|away|kickoff using explicit aliases only."""
    parsed = _split_match_key(natural_key)
    if parsed is None:
        return natural_key
    sport, home_slug, away_slug, kickoff = parsed
    aliased_home = canonical_slug_for_provider_slug(provider, home_slug)
    aliased_away = canonical_slug_for_provider_slug(provider, away_slug)
    if aliased_home == home_slug and aliased_away == away_slug:
        return natural_key
    return f"{sport}|{aliased_home}|{aliased_away}|{kickoff}"


def aliased_natural_keys(
    *,
    provider: str,
    home_team_id: str,
    away_team_id: str,
    home_name: str,
    away_name: str,
    kickoff: datetime,
) -> tuple[str, ...]:
    """Extra exact keys created from aliases that point at these canonical teams."""
    original = (
        f"{SportCode.FOOTBALL.value}|{slugify(home_name)}|{slugify(away_name)}|{kickoff.isoformat()}"
    )
    home_slugs = _slugs_for_team(provider, home_team_id, home_name)
    away_slugs = _slugs_for_team(provider, away_team_id, away_name)
    keys: list[str] = []
    seen = {original}
    for home_slug in home_slugs:
        for away_slug in away_slugs:
            key = f"{SportCode.FOOTBALL.value}|{home_slug}|{away_slug}|{kickoff.isoformat()}"
            if key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return tuple(keys)


def isolated_team_slugs() -> frozenset[str]:
    return frozenset(slugify(name) for name in ISOLATED_TEAM_NAMES)


def _slugs_for_team(provider: str, canonical_team_id: str, canonical_name: str) -> tuple[str, ...]:
    slugs = [slugify(canonical_name)]
    for item in TEAM_ALIASES:
        if item.provider == provider and item.canonical_team_id == canonical_team_id:
            if item.provider_slug not in slugs:
                slugs.append(item.provider_slug)
    return tuple(slugs)


def _split_match_key(natural_key: str) -> tuple[str, str, str, str] | None:
    parts = natural_key.split("|")
    if len(parts) < 4:
        return None
    return parts[0], parts[1], parts[2], "|".join(parts[3:])
