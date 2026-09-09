from collections.abc import Sequence
from decimal import Decimal

FORMULA_VERSION = "value-engine-0.1"
DECIMAL_CONTEXT = Decimal("0.0000000001")


def as_decimal(value: float | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def implied_probability_raw(decimal_odds: Decimal | float) -> Decimal:
    """1 / odds. Odds must be strictly greater than 1."""
    odds = as_decimal(decimal_odds)
    if odds <= 1:
        raise ValueError("Decimal odds must be strictly greater than 1.")
    return (Decimal(1) / odds).quantize(DECIMAL_CONTEXT)


def overround(decimal_odds: Sequence[Decimal | float]) -> Decimal:
    implied_sum = sum((implied_probability_raw(odds) for odds in decimal_odds), Decimal(0))
    result = implied_sum - Decimal(1)
    if result < 0:
        return Decimal("0")
    return result.quantize(DECIMAL_CONTEXT)


def no_vig_probability(decimal_odds: Decimal | float, market_odds: Sequence[Decimal | float]) -> Decimal:
    implied = implied_probability_raw(decimal_odds)
    total = sum((implied_probability_raw(odds) for odds in market_odds), Decimal(0))
    if total <= 0:
        raise ValueError("Market implied probabilities must be positive.")
    return (implied / total).quantize(DECIMAL_CONTEXT)


def edge(model_probability: Decimal | float, implied: Decimal | float) -> Decimal:
    """model_probability - implied_probability."""
    result = as_decimal(model_probability) - as_decimal(implied)
    if result < -1 or result > 1:
        raise ValueError("Edge is outside [-1, 1].")
    return result.quantize(DECIMAL_CONTEXT)


def expected_value(model_probability: Decimal | float, decimal_odds: Decimal | float) -> Decimal:
    """(model_probability × odds) - 1. Minimum -1."""
    result = (as_decimal(model_probability) * as_decimal(decimal_odds)) - Decimal(1)
    if result < -1:
        return Decimal("-1")
    return result.quantize(DECIMAL_CONTEXT)


def to_float(value: Decimal) -> float:
    return float(value)
