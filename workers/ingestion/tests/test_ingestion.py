from predicta_ingestion.canonical.enums import ResourceType, SportCode
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.providers.mock import MockBasketballProvider, MockFootballProvider
from predicta_ingestion.providers.protocols import ProviderRequest


def test_end_to_end_mock_football_ingestion(
    pipeline: IngestionPipeline, football_provider: MockFootballProvider
) -> None:
    report = pipeline.run(football_provider, ProviderRequest(resource=ResourceType.FIXTURES, sport=SportCode.FOOTBALL))
    assert report.data_mode.value == "mock"
    assert report.records_accepted > 0
    assert pipeline._sink.lineups
    assert pipeline._sink.injuries
    assert pipeline._sink.events
    assert all(item.provenance.raw_payload_id for item in pipeline._sink.matches.values())


def test_end_to_end_mock_basketball_ingestion(
    pipeline: IngestionPipeline, basketball_provider: MockBasketballProvider
) -> None:
    request = ProviderRequest(resource=ResourceType.FIXTURES, sport=SportCode.BASKETBALL)
    report = pipeline.run(basketball_provider, request)
    assert report.records_accepted > 0
    match = next(iter(pipeline._sink.matches.values()))
    assert match.home_score == 108
