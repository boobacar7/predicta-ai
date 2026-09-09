from app.core.clock import Clock, parse_rfc3339
from app.schemas import DataQuality

MOCK_SOURCE = "mock.fixtures.v1"
MOCK_NOTE = "Fixture fictive. Ne pas interpréter comme une donnée sportive réelle."


def quality(
    clock: Clock,
    *,
    availability: str = "available",
    source: str | None = MOCK_SOURCE,
    observed_at: str | None = "now",
    freshness: str | None = "fresh",
    note: str | None = MOCK_NOTE,
) -> DataQuality:
    observed = None
    if availability == "unavailable":
        source = None
        freshness = None
        if note == MOCK_NOTE:
            note = "Donnée absente du jeu mock. Ce n'est pas une valeur nulle."
    elif observed_at == "now":
        observed = clock.now()
    elif observed_at is not None:
        observed = parse_rfc3339(observed_at)

    if availability == "stale" and freshness is None:
        freshness = "stale"

    return DataQuality(
        availability=availability,  # type: ignore[arg-type]
        source=source,
        observed_at=observed,
        freshness=freshness,  # type: ignore[arg-type]
        note=note,
    )


def unavailable(clock: Clock) -> DataQuality:
    return quality(clock, availability="unavailable")
