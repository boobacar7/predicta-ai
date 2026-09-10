from datetime import timedelta

from predicta_ingestion.canonical.enums import Freshness, ResourceType
from predicta_ingestion.quality.freshness import classify_freshness


def test_prematch_odds_freshness_windows(clock) -> None:
    fresh = classify_freshness(ResourceType.ODDS, available_at=clock.now() - timedelta(minutes=5), clock=clock)
    acceptable = classify_freshness(ResourceType.ODDS, available_at=clock.now() - timedelta(hours=1), clock=clock)
    stale = classify_freshness(ResourceType.ODDS, available_at=clock.now() - timedelta(hours=5), clock=clock)
    assert fresh is Freshness.FRESH
    assert acceptable is Freshness.ACCEPTABLE
    assert stale is Freshness.STALE


def test_finished_facts_are_not_stale(clock) -> None:
    freshness = classify_freshness(
        ResourceType.FIXTURES,
        available_at=clock.now() - timedelta(days=400),
        clock=clock,
        terminal=True,
    )
    assert freshness is Freshness.FRESH
