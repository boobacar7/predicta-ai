from decimal import Decimal

from predicta_ingestion.canonical.enums import Availability, ResourceType, SportCode
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.providers.mock import MockFootballProvider, MockOddsProvider, MockTennisProvider
from predicta_ingestion.providers.protocols import ProviderRequest


def test_football_normalization_maps_status_and_unavailable_stat(
    pipeline: IngestionPipeline, football_provider: MockFootballProvider
) -> None:
    pipeline.run(football_provider, ProviderRequest(resource=ResourceType.FIXTURES))
    match = next(iter(pipeline._sink.matches.values()))
    assert match.status.value == "finished"
    assert match.sport_id.endswith("football")
    shots = [row for row in pipeline._sink.team_stats if row.stat_key == "shots-on-goal"]
    unavailable = [row for row in shots if row.availability is Availability.UNAVAILABLE]
    assert unavailable
    assert unavailable[0].value is None


def test_odds_are_not_converted_to_value_metrics(pipeline: IngestionPipeline, odds_provider: MockOddsProvider) -> None:
    pipeline.run(odds_provider, ProviderRequest(resource=ResourceType.ODDS))
    snapshot = next(iter(pipeline._sink.odds.values()))
    assert snapshot.selections[0].decimal_odds == Decimal("1.85")
    assert snapshot.selections[0].selection == "HOME"
    assert snapshot.market == "1X2"
    assert not hasattr(snapshot, "implied_probability_raw")


def test_tennis_requires_players(pipeline: IngestionPipeline, tennis_provider: MockTennisProvider) -> None:
    pipeline.run(tennis_provider, ProviderRequest(resource=ResourceType.FIXTURES))
    match = next(iter(pipeline._sink.matches.values()))
    assert match.home_player_id is not None
    assert match.away_player_id is not None
    assert match.home_team_id is None
    assert match.surface == "hard"
    assert match.sport_id.endswith(SportCode.TENNIS.value)
