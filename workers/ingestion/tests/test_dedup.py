from predicta_ingestion.canonical.enums import ResourceType
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.providers.mock import MockFootballProvider, MockOddsProvider
from predicta_ingestion.providers.protocols import ProviderRequest


def test_raw_checksum_deduplicates(pipeline: IngestionPipeline, football_provider: MockFootballProvider) -> None:
    first = pipeline.run(football_provider, ProviderRequest(resource=ResourceType.FIXTURES))
    second = pipeline.run(football_provider, ProviderRequest(resource=ResourceType.FIXTURES))
    assert first.duplicates == 0
    assert second.duplicates == 1
    assert len(pipeline._sink.matches) == 1


def test_odds_snapshot_natural_key_deduplicates(
    pipeline: IngestionPipeline, odds_provider: MockOddsProvider
) -> None:
    pipeline.run(odds_provider, ProviderRequest(resource=ResourceType.ODDS))
    pipeline.run(odds_provider, ProviderRequest(resource=ResourceType.ODDS))
    assert len(pipeline._sink.odds) == 1
