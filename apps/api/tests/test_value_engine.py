from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from app.ai_analyst.models import VALUE_SOURCE
from app.core.clock import Clock, parse_rfc3339
from app.core.config import Settings
from app.odds.types import Football1x2Selection
from app.repositories.mock import MockRepositoryBundle
from app.services.catalog import MatchService
from app.services.value_service import opportunities_for_match
from app.value_engine import calculator
from app.value_engine.calculator import VALUE_ENGINE_VERSION

MARKETS = (
    (Decimal("2.00"), Decimal("4.00"), Decimal("5.00")),
    (Decimal("1.90"), Decimal("3.20"), Decimal("4.20")),
    (Decimal("2.10"), Decimal("3.30"), Decimal("3.70")),
)
MODEL = {
    Football1x2Selection.HOME: Decimal("0.60"),
    Football1x2Selection.DRAW: Decimal("0.20"),
    Football1x2Selection.AWAY: Decimal("0.20"),
}


def _odds_map(home: Decimal, draw: Decimal, away: Decimal) -> dict[Football1x2Selection, Decimal]:
    return {
        Football1x2Selection.HOME: home,
        Football1x2Selection.DRAW: draw,
        Football1x2Selection.AWAY: away,
    }


def test_implied_probability() -> None:
    assert calculator.implied_probability(2) == Decimal("0.5")
    assert calculator.implied_probability("2.00") == Decimal(1) / Decimal("2.00")


def test_canonical_markets_share_one_formula() -> None:
    for home, draw, away in MARKETS:
        odds = _odds_map(home, draw, away)
        implied = {selection: calculator.implied_probability(price) for selection, price in odds.items()}
        expected_overround = implied[Football1x2Selection.HOME] + implied[Football1x2Selection.DRAW] + implied[
            Football1x2Selection.AWAY
        ]
        no_vig, overround = calculator.no_vig_probabilities(odds)
        assert overround == expected_overround
        assert overround == calculator.overround((home, draw, away))
        assert overround != expected_overround - Decimal(1)
        for selection, price in odds.items():
            assert calculator.no_vig_probability(price, (home, draw, away)) == implied[selection] / overround
            assert calculator.edge(MODEL[selection], implied[selection]) == MODEL[selection] - implied[selection]
            assert calculator.expected_value(MODEL[selection], price) == MODEL[selection] * price - Decimal(1)
        assert sum(no_vig.values(), Decimal(0)) == Decimal(1)


def test_two_four_five_market_is_the_documented_example() -> None:
    odds = _odds_map(Decimal("2.00"), Decimal("4.00"), Decimal("5.00"))
    no_vig, overround = calculator.no_vig_probabilities(odds)
    assert calculator.implied_probability(Decimal("2.00")) == Decimal("0.5")
    assert calculator.implied_probability(Decimal("4.00")) == Decimal("0.25")
    assert calculator.implied_probability(Decimal("5.00")) == Decimal("0.2")
    assert overround == Decimal("0.95")
    assert no_vig[Football1x2Selection.HOME] == Decimal("0.5") / Decimal("0.95")
    assert calculator.edge(Decimal("0.60"), Decimal("0.5")) == Decimal("0.10")
    assert calculator.expected_value(Decimal("0.60"), Decimal("2.00")) == Decimal("0.20")


def test_incomplete_market_is_refused() -> None:
    with pytest.raises(ValueError, match="complete football 1X2"):
        calculator.no_vig_probabilities(
            {
                Football1x2Selection.HOME: Decimal("2.00"),
                Football1x2Selection.DRAW: Decimal("4.00"),
            }
        )


def test_invalid_odds_are_refused() -> None:
    with pytest.raises(ValueError):
        calculator.implied_probability(1)
    with pytest.raises(ValueError):
        calculator.overround(())
    with pytest.raises(ValueError):
        calculator.overround((Decimal("0.5"),))


def test_invalid_probabilities_are_refused() -> None:
    with pytest.raises(ValueError):
        calculator.probability(0)
    with pytest.raises(ValueError):
        calculator.probability(1)
    with pytest.raises(ValueError):
        calculator.edge(1.2, 0.5)


def test_no_vig_residual_is_absorbed_by_away() -> None:
    odds = _odds_map(Decimal("1.90"), Decimal("3.20"), Decimal("4.20"))
    no_vig, overround = calculator.no_vig_probabilities(odds)
    raw = {selection: calculator.implied_probability(price) / overround for selection, price in odds.items()}
    assert no_vig[Football1x2Selection.HOME] == raw[Football1x2Selection.HOME]
    assert no_vig[Football1x2Selection.DRAW] == raw[Football1x2Selection.DRAW]
    assert sum(no_vig.values(), Decimal(0)) == Decimal(1)
    assert Decimal(0) < no_vig[Football1x2Selection.AWAY] < Decimal(1)


def test_single_value_engine_version() -> None:
    assert VALUE_ENGINE_VERSION == "value-engine-0.1"
    assert Settings().value_formula_version == VALUE_ENGINE_VERSION
    assert VALUE_SOURCE == VALUE_ENGINE_VERSION


def test_catalog_value_service_uses_canonical_calculator() -> None:
    clock = Clock(parse_rfc3339("2026-09-09T18:00:00Z"))
    match = MatchService(MockRepositoryBundle(clock)).get_match("mth_northgate_harbor")
    items = opportunities_for_match(match)
    assert match.odds is not None
    assert match.prediction is not None
    market_odds = [item.decimal_odds for item in match.odds.selections if item.decimal_odds is not None]
    expected_overround = calculator.overround(market_odds)
    assert expected_overround != expected_overround - Decimal(1)
    by_selection = {item.selection: item for item in items}
    for outcome in match.prediction.outcomes:
        selection = next(item for item in match.odds.selections if item.selection == outcome.selection)
        assert selection.decimal_odds is not None
        assert outcome.calibrated_probability is not None
        item = by_selection[outcome.selection]
        implied = calculator.implied_probability(selection.decimal_odds)
        no_vig = calculator.no_vig_probability(selection.decimal_odds, market_odds)
        assert item.implied_probability_raw == pytest.approx(float(implied))
        assert item.no_vig_probability == pytest.approx(float(no_vig))
        assert item.overround == pytest.approx(float(expected_overround))
        assert item.edge_raw == pytest.approx(float(calculator.edge(outcome.calibrated_probability, implied)))
        assert item.expected_value == pytest.approx(
            float(calculator.expected_value(outcome.calibrated_probability, selection.decimal_odds))
        )
        assert item.formula_version == VALUE_ENGINE_VERSION


def test_legacy_domain_module_is_gone() -> None:
    path = Path(__file__).resolve().parents[1] / "app" / "domain" / "value_engine.py"
    assert not path.exists()


def test_no_second_overround_formula() -> None:
    root = Path(__file__).resolve().parents[1] / "app"
    banned = (
        "implied_sum - Decimal(1)",
        "sum(implied) - 1",
        "sum(1 / odds_i) - 1",
        'FORMULA_VERSION = "value-engine-0.1"',
    )
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text()
        for needle in banned:
            if needle in text:
                hits.append(f"{path}:{needle}")
    assert hits == []
