from predicta_ingestion.canonical.enums import ResourceType
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.providers.mock import MockFootballProvider
from predicta_ingestion.providers.protocols import ProviderRequest


def test_football_fixture_parses_teams_and_score(
    pipeline: IngestionPipeline, football_provider: MockFootballProvider
) -> None:
    report = pipeline.run(football_provider, ProviderRequest(resource=ResourceType.FIXTURES))
    assert report.records_read == 1
    match = next(iter(pipeline._sink.matches.values()))
    assert match.home_score == 2
    assert match.away_score == 1
    assert {team.name for team in pipeline._sink.teams.values()} >= {"Helix FC", "Meridian Athletic"}
    assert all(item.provenance.data_mode.value == "mock" for item in pipeline._sink.matches.values())
