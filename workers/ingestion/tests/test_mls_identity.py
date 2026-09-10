from predicta_ingestion.canonical.enums import DataMode, EntityType, ResolutionMethod, SportCode
from predicta_ingestion.canonical.models import CanonicalBatch, League, Provenance, Sport, Team
from predicta_ingestion.clock import Clock
from predicta_ingestion.identity.historical import franchise_key
from predicta_ingestion.identity.resolver import IdentityResolver
from predicta_ingestion.ids import stable_entity_id


def _provenance(clock: Clock, provider_id: str) -> Provenance:
    now = clock.now()
    return Provenance(
        provider="sportmonks",
        provider_id=provider_id,
        collected_at=now,
        available_at=now,
        source="sportmonks",
        data_mode=DataMode.LIVE,
    )


def _mls_league(clock: Clock, season: str) -> League:
    sport_id = stable_entity_id("sport", SportCode.FOOTBALL.value)
    return League(
        id=stable_entity_id("league", SportCode.FOOTBALL.value, "sportmonks", "779", season),
        sport_id=sport_id,
        name="Major League Soccer",
        country="USA",
        season=season,
        provenance=_provenance(clock, f"779:{season}"),
    )


def _team(clock: Clock, league: League, provider_id: str, name: str) -> Team:
    return Team(
        id=stable_entity_id("team", SportCode.FOOTBALL.value, "sportmonks", provider_id),
        sport_id=league.sport_id,
        league_id=league.id,
        name=name,
        short_name=name,
        abbreviation=name[:3].upper(),
        provenance=_provenance(clock, provider_id),
    )


def _sport(clock: Clock) -> Sport:
    return Sport(
        id=stable_entity_id("sport", SportCode.FOOTBALL.value),
        code=SportCode.FOOTBALL,
        name="Football",
        provenance=_provenance(clock, "1"),
    )


def test_mls_league_identity_is_scoped_by_season(clock: Clock) -> None:
    resolver = IdentityResolver(clock)
    sport = _sport(clock)
    league_2024 = _mls_league(clock, "2024")
    league_2025 = _mls_league(clock, "2025")
    first = resolver.resolve(CanonicalBatch(sports=[sport], leagues=[league_2024]), data_mode=DataMode.LIVE)
    second = resolver.resolve(CanonicalBatch(sports=[sport], leagues=[league_2025]), data_mode=DataMode.LIVE)
    assert first == []
    assert second == []
    assert resolver.lookup("sportmonks", EntityType.LEAGUE, "779:2024") == league_2024.id
    assert resolver.lookup("sportmonks", EntityType.LEAGUE, "779:2025") == league_2025.id
    assert league_2024.id != league_2025.id


def test_same_sportmonks_team_id_stays_canonical_across_mls_seasons(clock: Clock) -> None:
    resolver = IdentityResolver(clock)
    league_2024 = _mls_league(clock, "2024")
    league_2025 = _mls_league(clock, "2025")
    miami_2024 = _team(clock, league_2024, "1234", "Inter Miami")
    miami_2025 = _team(clock, league_2025, "1234", "Inter Miami CF")
    resolver.resolve(
        CanonicalBatch(sports=[_sport(clock)], leagues=[league_2024], teams=[miami_2024]),
        data_mode=DataMode.LIVE,
    )
    quarantined = resolver.resolve(
        CanonicalBatch(sports=[_sport(clock)], leagues=[league_2025], teams=[miami_2025]),
        data_mode=DataMode.LIVE,
    )
    assert quarantined == []
    assert miami_2025.id == miami_2024.id
    assert resolver.lookup("sportmonks", EntityType.TEAM, "1234") == miami_2024.id
    diagnostics = [item for item in resolver.identity_report() if item.provider_entity_id == "1234"]
    diagnostic = diagnostics[-1]
    assert diagnostic.status == "resolved"
    assert diagnostic.resolution_method == ResolutionMethod.EXACT_ID.value
    assert diagnostic.provider_name == "Inter Miami CF"
    assert diagnostic.canonical_id == miami_2024.id
    assert diagnostic.canonical_name == "Inter Miami"


def test_mls_name_change_with_new_provider_id_uses_historical_alias(clock: Clock) -> None:
    resolver = IdentityResolver(clock)
    league_2024 = _mls_league(clock, "2024")
    league_2025 = _mls_league(clock, "2025")
    old = _team(clock, league_2024, "10", "Inter Miami")
    new = _team(clock, league_2025, "99", "Inter Miami CF")
    resolver.resolve(
        CanonicalBatch(sports=[_sport(clock)], leagues=[league_2024], teams=[old]),
        data_mode=DataMode.LIVE,
    )
    quarantined = resolver.resolve(
        CanonicalBatch(sports=[_sport(clock)], leagues=[league_2025], teams=[new]),
        data_mode=DataMode.LIVE,
    )
    assert quarantined == []
    assert new.id == old.id
    binding = next(item for item in resolver.bindings() if item.provider_entity_id == "99")
    assert binding.canonical_id == old.id
    assert binding.method is ResolutionMethod.HISTORICAL_ALIAS
    assert binding.confidence == 1.0


def test_new_mls_expansion_club_is_not_merged(clock: Clock) -> None:
    resolver = IdentityResolver(clock)
    league_2024 = _mls_league(clock, "2024")
    league_2025 = _mls_league(clock, "2025")
    earthquakes = _team(clock, league_2024, "20", "San Jose Earthquakes")
    san_diego = _team(clock, league_2025, "30", "San Diego FC")
    resolver.resolve(
        CanonicalBatch(sports=[_sport(clock)], leagues=[league_2024], teams=[earthquakes]),
        data_mode=DataMode.LIVE,
    )
    resolver.resolve(
        CanonicalBatch(sports=[_sport(clock)], leagues=[league_2025], teams=[san_diego]),
        data_mode=DataMode.LIVE,
    )
    assert san_diego.id != earthquakes.id
    assert resolver.lookup("sportmonks", EntityType.TEAM, "30") == san_diego.id


def test_unique_normalized_name_links_new_provider_id(clock: Clock) -> None:
    resolver = IdentityResolver(clock)
    league_2024 = _mls_league(clock, "2024")
    league_2025 = _mls_league(clock, "2025")
    old = _team(clock, league_2024, "40", "Seattle Sounders")
    new = _team(clock, league_2025, "41", "Seattle Sounders")
    resolver.resolve(
        CanonicalBatch(sports=[_sport(clock)], leagues=[league_2024], teams=[old]),
        data_mode=DataMode.LIVE,
    )
    quarantined = resolver.resolve(
        CanonicalBatch(sports=[_sport(clock)], leagues=[league_2025], teams=[new]),
        data_mode=DataMode.LIVE,
    )
    assert quarantined == []
    assert new.id == old.id
    binding = next(item for item in resolver.bindings() if item.provider_entity_id == "41")
    assert binding.method is ResolutionMethod.NORMALIZED_NAME
    assert binding.confidence == 0.95


def test_two_canonicals_for_the_same_normalized_name_stay_quarantined(clock: Clock) -> None:
    resolver = IdentityResolver(clock)
    first = resolver.bind_explicit(
        provider="sportmonks",
        entity_type=EntityType.TEAM,
        provider_entity_id="1",
        canonical_id="tm_a",
        name_key="spt_football:mls:helix-fc",
        data_mode=DataMode.LIVE,
    )
    second = resolver.bind_explicit(
        provider="sportmonks",
        entity_type=EntityType.TEAM,
        provider_entity_id="2",
        canonical_id="tm_b",
        name_key="spt_football:mls:helix-fc",
        data_mode=DataMode.LIVE,
    )
    assert first is None
    assert second is not None
    assert second.reason_code == "ambiguous_identity"


def test_franchise_key_is_exact_slug_alias_not_fuzzy() -> None:
    key, aliased = franchise_key("mls", "Inter Miami CF")
    assert key == "inter-miami"
    assert aliased is True
    unknown, aliased_unknown = franchise_key("mls", "Imaginary United")
    assert unknown == "imaginary-united"
    assert aliased_unknown is False


def test_identity_diagnostic_does_not_embed_tokens(clock: Clock) -> None:
    resolver = IdentityResolver(clock)
    league = _mls_league(clock, "2025")
    team = _team(clock, league, "55", "Austin FC")
    resolver.resolve(
        CanonicalBatch(sports=[_sport(clock)], leagues=[league], teams=[team]),
        data_mode=DataMode.LIVE,
    )
    dumped = str(resolver.identity_report())
    assert "sm_test_secret_do_not_log" not in dumped
    row = resolver.identity_report()[0]
    assert set(row.to_dict()) >= {
        "provider_entity_id",
        "provider_name",
        "canonical_id",
        "canonical_name",
        "resolution_method",
        "confidence",
    }
    assert row.provider_entity_id == "55"
    assert row.provider_name == "Austin FC"
