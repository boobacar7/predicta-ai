from predicta_ingestion.canonical.enums import DataMode, EntityType
from predicta_ingestion.identity.resolver import IdentityResolver


def test_provider_id_maps_to_canonical_and_is_stable(clock) -> None:
    resolver = IdentityResolver(clock)
    from predicta_ingestion.canonical.enums import SportCode
    from predicta_ingestion.canonical.models import CanonicalBatch, Provenance, Sport

    sport = Sport(
        id="spt_football",
        code=SportCode.FOOTBALL,
        name="Football",
        provenance=Provenance(
            provider="mock.api_football",
            provider_id="football",
            collected_at=clock.now(),
            available_at=clock.now(),
            source="mock.api_football",
            data_mode=DataMode.MOCK,
        ),
    )
    batch = CanonicalBatch(sports=[sport])
    resolver.resolve(batch, data_mode=DataMode.MOCK)
    assert resolver.lookup("mock.api_football", EntityType.SPORT, "football") == "spt_football"
    resolver.resolve(batch, data_mode=DataMode.MOCK)
    assert resolver.lookup("mock.api_football", EntityType.SPORT, "football") == "spt_football"


def test_ambiguous_name_is_quarantined(clock) -> None:
    resolver = IdentityResolver(clock)
    first = resolver.bind_explicit(
        provider="mock.a",
        entity_type=EntityType.TEAM,
        provider_entity_id="1",
        canonical_id="tm_helix",
        name_key="helix-fc",
        data_mode=DataMode.MOCK,
    )
    second = resolver.bind_explicit(
        provider="mock.b",
        entity_type=EntityType.TEAM,
        provider_entity_id="2",
        canonical_id="tm_other_helix",
        name_key="helix-fc",
        data_mode=DataMode.MOCK,
    )
    assert first is None
    assert second is not None
    assert second.reason_code == "ambiguous_identity"


def test_odds_match_links_via_natural_key(pipeline, football_provider, odds_provider) -> None:
    from predicta_ingestion.canonical.enums import ResourceType
    from predicta_ingestion.providers.protocols import ProviderRequest

    pipeline.run(football_provider, ProviderRequest(resource=ResourceType.FIXTURES))
    football_match_id = next(iter(pipeline._sink.matches.values())).id
    pipeline.run(odds_provider, ProviderRequest(resource=ResourceType.ODDS))
    snapshot = next(iter(pipeline._sink.odds.values()))
    assert snapshot.match_id == football_match_id
