from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from predicta_ingestion.canonical.enums import DataMode, ResolutionMethod
from predicta_ingestion.canonical.models import CanonicalBatch, OddsSelection, OddsSnapshot, Provenance
from predicta_ingestion.clock import Clock
from predicta_ingestion.identity.aliases import (
    ALIAS_TABLE_VERSION,
    ISOLATED_TEAM_NAMES,
    TEAM_ALIASES,
    AliasTableError,
    ProviderTeamAlias,
    aliased_natural_keys,
    apply_team_name_aliases,
    isolated_team_slugs,
    lookup_team_alias,
    validate_alias_table,
)
from predicta_ingestion.identity.resolver import IdentityResolver
from predicta_ingestion.ids import slugify
from predicta_ingestion.providers.the_odds_api import LIVE_ODDS_PROVIDER


def _odds_snapshot(*, natural_key: str, match_id: str = "mth_odds_unmatched") -> OddsSnapshot:
    now = datetime(2026, 9, 11, 12, tzinfo=UTC)
    return OddsSnapshot(
        id="odd_alias_test",
        match_id=match_id,
        market="1X2",
        bookmaker="pinnacle",
        selections=[
            OddsSelection(selection="HOME", label="Home", decimal_odds=Decimal("1.90")),
            OddsSelection(selection="DRAW", label="Draw", decimal_odds=Decimal("3.60")),
            OddsSelection(selection="AWAY", label="Away", decimal_odds=Decimal("4.20")),
        ],
        match_natural_key=natural_key,
        provenance=Provenance(
            provider=LIVE_ODDS_PROVIDER,
            provider_id="alias-test",
            collected_at=now,
            available_at=now,
            source="the-odds-api-v4",
            data_mode=DataMode.LIVE,
        ),
    )


def test_alias_table_is_versioned_and_one_to_one() -> None:
    assert ALIAS_TABLE_VERSION == "the-odds-api-team-aliases-v1"
    ids = {(item.provider, item.provider_slug) for item in TEAM_ALIASES}
    assert len(ids) == len(TEAM_ALIASES)
    for item in TEAM_ALIASES:
        assert item.provider == LIVE_ODDS_PROVIDER
        assert lookup_team_alias(item.provider, item.provider_team_name) == item
        assert item.canonical_team_id.startswith("tm_football-sportmonks-")
        assert item.provider_slug != item.canonical_slug


def test_demonstrated_name_variants_are_exact_aliases() -> None:
    cases = {
        "Bournemouth": ("tm_football-sportmonks-52", "AFC Bournemouth"),
        "Brighton and Hove Albion": ("tm_football-sportmonks-78", "Brighton & Hove Albion"),
        "Marseille": ("tm_football-sportmonks-44", "Olympique Marseille"),
        "AS Monaco": ("tm_football-sportmonks-6789", "Monaco"),
        "Angers": ("tm_football-sportmonks-776", "Angers SCO"),
        "Lille": ("tm_football-sportmonks-690", "LOSC Lille"),
        "Le Mans FC": ("tm_football-sportmonks-7758", "Le Mans"),
        "RC Lens": ("tm_football-sportmonks-271", "Lens"),
        "Lyon": ("tm_football-sportmonks-79", "Olympique Lyonnais"),
        "Inter Milan": ("tm_football-sportmonks-2930", "Inter"),
        "AS Roma": ("tm_football-sportmonks-37", "Roma"),
        "Atalanta BC": ("tm_football-sportmonks-708", "Atalanta"),
    }
    for provider_name, (canonical_id, canonical_name) in cases.items():
        alias = lookup_team_alias(LIVE_ODDS_PROVIDER, provider_name)
        assert alias is not None
        assert alias.canonical_team_id == canonical_id
        assert alias.canonical_team_name == canonical_name


def test_paris_family_names_stay_strictly_isolated() -> None:
    slugs = isolated_team_slugs()
    assert slugs == {
        "paris",
        "paris-fc",
        "paris-saint-germain",
        "psg",
    }
    for name in ISOLATED_TEAM_NAMES:
        assert lookup_team_alias(LIVE_ODDS_PROVIDER, name) is None
    alias_slugs = {item.provider_slug for item in TEAM_ALIASES} | {item.canonical_slug for item in TEAM_ALIASES}
    assert slugs.isdisjoint(alias_slugs)
    paris_ids = {item.canonical_team_id for item in TEAM_ALIASES if "paris" in item.canonical_slug}
    assert paris_ids == set()
    assert slugify("Paris") != slugify("Paris FC")
    assert slugify("Paris") != slugify("Paris Saint-Germain")
    assert slugify("Paris FC") != slugify("Paris Saint Germain")
    assert slugify("PSG") != slugify("Paris Saint-Germain")
    assert slugify("Paris Saint-Germain") == slugify("Paris Saint Germain")


def test_ambiguous_alias_is_refused() -> None:
    first = ProviderTeamAlias(
        provider=LIVE_ODDS_PROVIDER,
        provider_team_name="Helix",
        canonical_team_id="tm_football-sportmonks-1",
        canonical_team_name="Helix FC",
        evidence="test",
    )
    second = ProviderTeamAlias(
        provider=LIVE_ODDS_PROVIDER,
        provider_team_name="Helix",
        canonical_team_id="tm_football-sportmonks-2",
        canonical_team_name="Other Helix",
        evidence="test",
    )
    with pytest.raises(AliasTableError, match="maps to both"):
        validate_alias_table((first, second))


def test_alias_rewrites_natural_key_exactly() -> None:
    kickoff = "2026-09-12T14:00:00+00:00"
    raw = f"football|bournemouth|brentford|{kickoff}"
    aliased = apply_team_name_aliases(raw, LIVE_ODDS_PROVIDER)
    assert aliased == f"football|afc-bournemouth|brentford|{kickoff}"
    both = apply_team_name_aliases(f"football|le-mans-fc|rc-lens|{kickoff}", LIVE_ODDS_PROVIDER)
    assert both == f"football|le-mans|lens|{kickoff}"
    serie_a = apply_team_name_aliases(f"football|torino|as-roma|{kickoff}", LIVE_ODDS_PROVIDER)
    assert serie_a == f"football|torino|roma|{kickoff}"
    inter = apply_team_name_aliases(f"football|inter-milan|udinese|{kickoff}", LIVE_ODDS_PROVIDER)
    assert inter == f"football|inter|udinese|{kickoff}"
    atalanta = apply_team_name_aliases(f"football|atalanta-bc|sassuolo|{kickoff}", LIVE_ODDS_PROVIDER)
    assert atalanta == f"football|atalanta|sassuolo|{kickoff}"
    paris = apply_team_name_aliases(f"football|paris-fc|lyon|{kickoff}", LIVE_ODDS_PROVIDER)
    assert paris == f"football|paris-fc|olympique-lyonnais|{kickoff}"
    isolated = apply_team_name_aliases(f"football|paris|paris-saint-germain|{kickoff}", LIVE_ODDS_PROVIDER)
    assert isolated == f"football|paris|paris-saint-germain|{kickoff}"


def test_resolver_links_aliased_odds_and_quarantines_paris_fc(
    clock: Clock,
) -> None:
    resolver = IdentityResolver(clock)
    bournemouth_id = "mth_football-sportmonks-bournemouth"
    paris_id = "mth_football-sportmonks-paris"
    resolver.bind_match_natural_key(
        "football|afc-bournemouth|brentford|2026-09-12T14:00:00+00:00",
        bournemouth_id,
    )
    resolver.bind_match_natural_key(
        "football|paris|olympique-lyonnais|2026-09-12T18:45:00+00:00",
        paris_id,
    )
    linked = CanonicalBatch(
        odds=[
            _odds_snapshot(
                natural_key="football|bournemouth|brentford|2026-09-12T14:00:00+00:00",
            )
        ]
    )
    quarantined = resolver.resolve(linked, data_mode=DataMode.LIVE)
    assert quarantined == []
    assert linked.odds[0].match_id == bournemouth_id
    diagnostic = next(item for item in resolver.diagnostics if item.entity_type == "odds_snapshot")
    assert diagnostic.resolution_method == ResolutionMethod.EXPLICIT_ALIAS.value

    rejected = CanonicalBatch(
        odds=[
            _odds_snapshot(
                natural_key="football|paris-fc|lyon|2026-09-12T18:45:00+00:00",
                match_id="mth_should_not_persist",
            )
        ]
    )
    unmatched = resolver.resolve(rejected, data_mode=DataMode.LIVE)
    assert rejected.odds == []
    assert unmatched[0].reason_code == "unmatched_odds_event"
    assert "paris-fc" in unmatched[0].detail


def test_serie_a_aliases_do_not_collapse_similar_club_names() -> None:
    assert lookup_team_alias(LIVE_ODDS_PROVIDER, "Inter Milan") is not None
    assert lookup_team_alias(LIVE_ODDS_PROVIDER, "Inter") is None
    assert lookup_team_alias(LIVE_ODDS_PROVIDER, "AC Milan") is None
    assert lookup_team_alias(LIVE_ODDS_PROVIDER, "Milan") is None
    assert lookup_team_alias(LIVE_ODDS_PROVIDER, "Inter Miami") is None
    assert lookup_team_alias(LIVE_ODDS_PROVIDER, "Inter Miami CF") is None
    assert lookup_team_alias(LIVE_ODDS_PROVIDER, "Inter Club d'Escaldes") is None
    assert lookup_team_alias(LIVE_ODDS_PROVIDER, "Juventus") is None
    assert lookup_team_alias(LIVE_ODDS_PROVIDER, "Juventude") is None
    assert slugify("Inter Milan") != slugify("Inter")
    assert slugify("Inter Milan") != slugify("AC Milan")
    assert slugify("Inter Milan") != slugify("Milan")
    assert slugify("Inter Milan") != slugify("Inter Miami")
    assert slugify("Juventus") != slugify("Juventude")
    kickoff = "2026-09-14T18:45:00+00:00"
    assert apply_team_name_aliases(f"football|ac-milan|udinese|{kickoff}", LIVE_ODDS_PROVIDER) == (
        f"football|ac-milan|udinese|{kickoff}"
    )
    assert apply_team_name_aliases(f"football|milan|inter|{kickoff}", LIVE_ODDS_PROVIDER) == (
        f"football|milan|inter|{kickoff}"
    )
    assert apply_team_name_aliases(f"football|inter-miami|toronto|{kickoff}", LIVE_ODDS_PROVIDER) == (
        f"football|inter-miami|toronto|{kickoff}"
    )
    assert apply_team_name_aliases(f"football|juventus|como|{kickoff}", LIVE_ODDS_PROVIDER) == (
        f"football|juventus|como|{kickoff}"
    )
    assert apply_team_name_aliases(f"football|juventude|gremio|{kickoff}", LIVE_ODDS_PROVIDER) == (
        f"football|juventude|gremio|{kickoff}"
    )


def test_aliased_natural_keys_cover_odds_api_serie_a_slugs() -> None:
    kickoff = datetime(2026, 9, 14, 18, 45, tzinfo=UTC)
    keys = aliased_natural_keys(
        provider=LIVE_ODDS_PROVIDER,
        home_team_id="tm_football-sportmonks-2930",
        away_team_id="tm_football-sportmonks-85",
        home_name="Inter",
        away_name="Udinese",
        kickoff=kickoff,
    )
    assert f"football|inter-milan|udinese|{kickoff.isoformat()}" in keys
    roma_keys = aliased_natural_keys(
        provider=LIVE_ODDS_PROVIDER,
        home_team_id="tm_football-sportmonks-613",
        away_team_id="tm_football-sportmonks-37",
        home_name="Torino",
        away_name="Roma",
        kickoff=datetime(2026, 9, 14, 16, 30, tzinfo=UTC),
    )
    assert "football|torino|as-roma|2026-09-14T16:30:00+00:00" in roma_keys


def test_resolver_links_serie_a_aliases_and_keeps_kickoff_and_home_away(
    clock: Clock,
) -> None:
    resolver = IdentityResolver(clock)
    torino_roma = "mth_football-sportmonks-torino-roma"
    inter_udinese = "mth_football-sportmonks-inter-udinese"
    atalanta_sassuolo = "mth_football-sportmonks-atalanta-sassuolo"
    ac_milan = "mth_football-sportmonks-ac-milan-udinese"
    inter_miami = "mth_football-sportmonks-inter-miami"
    juventude = "mth_football-sportmonks-juventude"
    resolver.bind_match_natural_key(
        "football|torino|roma|2026-09-14T16:30:00+00:00",
        torino_roma,
    )
    resolver.bind_match_natural_key(
        "football|inter|udinese|2026-09-14T18:45:00+00:00",
        inter_udinese,
    )
    resolver.bind_match_natural_key(
        "football|atalanta|sassuolo|2026-08-23T18:45:00+00:00",
        atalanta_sassuolo,
    )
    resolver.bind_match_natural_key(
        "football|ac-milan|udinese|2026-09-14T18:45:00+00:00",
        ac_milan,
    )
    resolver.bind_match_natural_key(
        "football|inter-miami|toronto|2026-08-22T23:30:00+00:00",
        inter_miami,
    )
    resolver.bind_match_natural_key(
        "football|juventude|gremio|2026-09-14T16:30:00+00:00",
        juventude,
    )

    linked = CanonicalBatch(
        odds=[
            _odds_snapshot(
                natural_key="football|torino|as-roma|2026-09-14T16:30:00+00:00",
                match_id="mth_odds_torino_as_roma",
            )
        ]
    )
    assert resolver.resolve(linked, data_mode=DataMode.LIVE) == []
    assert linked.odds[0].match_id == torino_roma

    linked_inter = CanonicalBatch(
        odds=[
            _odds_snapshot(
                natural_key="football|inter-milan|udinese|2026-09-14T18:45:00+00:00",
                match_id="mth_odds_inter_milan",
            )
        ]
    )
    assert resolver.resolve(linked_inter, data_mode=DataMode.LIVE) == []
    assert linked_inter.odds[0].match_id == inter_udinese

    linked_atalanta = CanonicalBatch(
        odds=[
            _odds_snapshot(
                natural_key="football|atalanta-bc|sassuolo|2026-08-23T18:45:00+00:00",
                match_id="mth_odds_atalanta_bc",
            )
        ]
    )
    assert resolver.resolve(linked_atalanta, data_mode=DataMode.LIVE) == []
    assert linked_atalanta.odds[0].match_id == atalanta_sassuolo

    swapped = CanonicalBatch(
        odds=[
            _odds_snapshot(
                natural_key="football|as-roma|torino|2026-09-14T16:30:00+00:00",
                match_id="mth_should_not_flip",
            )
        ]
    )
    swapped_q = resolver.resolve(swapped, data_mode=DataMode.LIVE)
    assert swapped.odds == []
    assert swapped_q[0].reason_code == "unmatched_odds_event"
    assert "as-roma" in swapped_q[0].detail

    wrong_kickoff = CanonicalBatch(
        odds=[
            _odds_snapshot(
                natural_key="football|torino|as-roma|2026-09-14T18:45:00+00:00",
                match_id="mth_should_not_shift_kickoff",
            )
        ]
    )
    wrong_q = resolver.resolve(wrong_kickoff, data_mode=DataMode.LIVE)
    assert wrong_kickoff.odds == []
    assert wrong_q[0].reason_code == "unmatched_odds_event"

    milan_false = CanonicalBatch(
        odds=[
            _odds_snapshot(
                natural_key="football|inter-milan|udinese|2026-09-14T18:45:00+00:00",
                match_id="mth_should_not_hit_ac_milan",
            )
        ]
    )
    assert resolver.resolve(milan_false, data_mode=DataMode.LIVE) == []
    assert milan_false.odds[0].match_id == inter_udinese
    assert milan_false.odds[0].match_id != ac_milan

    juve = CanonicalBatch(
        odds=[
            _odds_snapshot(
                natural_key="football|juventus|como|2026-09-14T16:30:00+00:00",
                match_id="mth_should_not_hit_juventude",
            )
        ]
    )
    juve_q = resolver.resolve(juve, data_mode=DataMode.LIVE)
    assert juve.odds == []
    assert juve_q[0].reason_code == "unmatched_odds_event"
    assert resolver._by_match_key["football|juventude|gremio|2026-09-14T16:30:00+00:00"] == juventude

    miami = CanonicalBatch(
        odds=[
            _odds_snapshot(
                natural_key="football|inter-milan|toronto|2026-08-22T23:30:00+00:00",
                match_id="mth_should_not_hit_inter_miami",
            )
        ]
    )
    miami_q = resolver.resolve(miami, data_mode=DataMode.LIVE)
    assert miami.odds == []
    assert miami_q[0].reason_code == "unmatched_odds_event"
    assert "never create canonical matches" in miami_q[0].detail
    assert list(resolver._by_match_key.values()).count(inter_miami) == 1
