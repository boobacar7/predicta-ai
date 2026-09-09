from decimal import Decimal

import pytest
from app.domain import value_engine as ve


def test_implied_probability() -> None:
    assert ve.implied_probability_raw(2) == Decimal("0.5000000000")


def test_edge_and_ev_formulas() -> None:
    implied = ve.implied_probability_raw(2.2)
    edge = ve.edge(0.47, implied)
    expected = ve.expected_value(0.47, 2.2)
    assert edge == (Decimal("0.47") - implied).quantize(ve.DECIMAL_CONTEXT)
    assert expected == (Decimal("0.47") * Decimal("2.2") - 1).quantize(ve.DECIMAL_CONTEXT)
    assert Decimal("-1") <= edge <= Decimal("1")
    assert expected >= Decimal("-1")


def test_no_vig_and_overround() -> None:
    odds = [2.2, 3.4, 3.5]
    overround = ve.overround(odds)
    no_vig = ve.no_vig_probability(2.2, odds)
    assert overround >= 0
    assert Decimal("0") <= no_vig <= Decimal("1")


def test_odds_must_be_greater_than_one() -> None:
    with pytest.raises(ValueError):
        ve.implied_probability_raw(1)
