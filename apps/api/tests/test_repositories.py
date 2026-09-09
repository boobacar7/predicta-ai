from app.core.clock import Clock, parse_rfc3339
from app.repositories.mock import MockRepositoryBundle
from app.services.catalog import CatalogService, MatchService
from app.services.value_service import opportunities_for_match


def test_mock_repository_and_services() -> None:
    clock = Clock(parse_rfc3339("2026-09-09T18:00:00Z"))
    repos = MockRepositoryBundle(clock)
    catalog = CatalogService(repos)
    matches = MatchService(repos)
    sports = catalog.list_sports()
    assert len(sports) == 3
    match = matches.get_match("mth_helix_meridian")
    values = opportunities_for_match(match)
    assert values
    implied = 1 / values[0].decimal_odds
    assert abs(values[0].implied_probability_raw - implied) < 1e-9
