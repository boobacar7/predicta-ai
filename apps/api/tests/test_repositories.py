import pytest
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
    assert match.odds is not None
    implied = 1 / values[0].decimal_odds
    assert abs(values[0].implied_probability_raw - implied) < 1e-9
    market_odds = [item.decimal_odds for item in match.odds.selections if item.decimal_odds is not None]
    expected_overround = sum(1 / odds for odds in market_odds)
    assert values[0].overround == pytest.approx(expected_overround)
    assert values[0].overround != pytest.approx(expected_overround - 1)
    assert values[0].formula_version == "value-engine-0.1"
