from __future__ import annotations

from datetime import timedelta

from predicta_ingestion.canonical.enums import Freshness, ResourceType
from predicta_ingestion.clock import Clock, ensure_utc
from predicta_ingestion.raw.envelope import RawEnvelope

FRESH_WINDOWS = {
    ResourceType.ODDS: (timedelta(minutes=15), timedelta(hours=2)),
    ResourceType.LEAGUES: (timedelta(hours=6), timedelta(hours=24)),
    ResourceType.SEASONS: (timedelta(hours=6), timedelta(hours=24)),
    ResourceType.FIXTURES: (timedelta(minutes=5), timedelta(minutes=30)),
    ResourceType.STANDINGS: (timedelta(hours=6), timedelta(hours=24)),
    ResourceType.INJURIES: (timedelta(hours=6), timedelta(hours=24)),
    ResourceType.LINEUPS: (timedelta(minutes=60), timedelta(hours=3)),
    ResourceType.MATCH_EVENTS: (timedelta(minutes=5), timedelta(minutes=30)),
    ResourceType.TEAM_STATS: (timedelta(hours=6), timedelta(hours=24)),
    ResourceType.PLAYER_STATS: (timedelta(hours=6), timedelta(hours=24)),
}


def classify_freshness(
    resource: ResourceType,
    *,
    available_at: object,
    clock: Clock,
    terminal: bool = False,
) -> Freshness:
    """Historical finished facts are not stale. Operational feeds use named windows."""
    if terminal:
        return Freshness.FRESH
    available = ensure_utc(available_at)  # type: ignore[arg-type]
    age = clock.now() - available
    fresh_for, acceptable_for = FRESH_WINDOWS[resource]
    if age <= fresh_for:
        return Freshness.FRESH
    if age <= acceptable_for:
        return Freshness.ACCEPTABLE
    return Freshness.STALE


def envelope_freshness(envelope: RawEnvelope, clock: Clock, *, terminal: bool = False) -> Freshness:
    return classify_freshness(envelope.resource, available_at=envelope.collected_at, clock=clock, terminal=terminal)
