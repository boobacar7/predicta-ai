import pytest

from predicta_ingestion.canonical.enums import ResourceType
from predicta_ingestion.errors import DataLeakageError
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.pit.store import PointInTimeStore
from predicta_ingestion.providers.mock import MockFootballProvider, MockOddsProvider
from predicta_ingestion.providers.protocols import ProviderRequest


def test_point_in_time_hides_post_match_standings_and_same_match_result(
    pipeline: IngestionPipeline, football_provider: MockFootballProvider, odds_provider: MockOddsProvider
) -> None:
    pipeline.run(football_provider, ProviderRequest(resource=ResourceType.FIXTURES))
    pipeline.run(odds_provider, ProviderRequest(resource=ResourceType.ODDS))
    match = next(iter(pipeline._sink.matches.values()))
    store = PointInTimeStore(pipeline._sink)
    cutoff = match.kickoff_at

    assert store.matches_finished_before(cutoff) == []
    assert store.standings_as_of(match.league_id, cutoff) == []
    odds = store.odds_as_of(match.id, cutoff)
    assert odds is not None
    assert odds.provenance.available_at < cutoff
    lineups = store.lineups_as_of(match.id, cutoff)
    assert lineups
    injuries = store.injuries_as_of(match.away_team_id or "", cutoff)
    assert injuries

    features = store.features_for_match(match.id, cutoff)
    assert match.id not in features["prior_matches"]

    later = store.matches_finished_before(pipeline._clock.now())
    assert [item.id for item in later] == [match.id]


def test_cutoff_after_kickoff_is_rejected(pipeline: IngestionPipeline, football_provider: MockFootballProvider) -> None:
    pipeline.run(football_provider, ProviderRequest(resource=ResourceType.FIXTURES))
    match = next(iter(pipeline._sink.matches.values()))
    store = PointInTimeStore(pipeline._sink)
    with pytest.raises(DataLeakageError):
        store.features_for_match(match.id, pipeline._clock.now())
