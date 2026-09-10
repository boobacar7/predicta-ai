from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from app.odds.types import Football1x2Selection, decimal_odds

VALUE_ENGINE_VERSION = "value-engine-0.1"


def probability(value: Decimal | float | str) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Probability must be a finite number in (0, 1).") from exc
    if not result.is_finite() or not Decimal(0) < result < Decimal(1):
        raise ValueError("Probability must be a finite number in (0, 1).")
    return result


def implied_probability(odds: Decimal | float | str) -> Decimal:
    result = Decimal(1) / decimal_odds(odds)
    if not Decimal(0) < result < Decimal(1):
        raise ValueError("Implied probability must be in (0, 1).")
    return result


def no_vig_probabilities(
    odds_by_selection: Mapping[Football1x2Selection, Decimal],
) -> tuple[dict[Football1x2Selection, Decimal], Decimal]:
    if set(odds_by_selection) != set(Football1x2Selection):
        raise ValueError("No-vig calculation requires a complete football 1X2 market.")
    raw = {
        selection: implied_probability(odds)
        for selection, odds in odds_by_selection.items()
    }
    overround = sum(raw.values(), Decimal(0))
    if overround <= 0:
        raise ValueError("Market overround must be positive.")
    normalized = {
        selection: value / overround
        for selection, value in raw.items()
    }
    if sum(normalized.values(), Decimal(0)) != Decimal(1):
        raise ArithmeticError("No-vig probabilities do not sum to 1.")
    return normalized, overround


def edge(model_probability: Decimal | float | str, implied: Decimal | float | str) -> Decimal:
    return probability(model_probability) - probability(implied)


def expected_value(
    model_probability: Decimal | float | str,
    odds: Decimal | float | str,
) -> Decimal:
    return probability(model_probability) * decimal_odds(odds) - Decimal(1)
