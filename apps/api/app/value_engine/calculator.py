from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation

from app.odds.types import Football1x2Selection, decimal_odds

VALUE_ENGINE_VERSION = "value-engine-0.1"

# Default Decimal precision is 28 digits. Dividing implied probabilities by the
# overround can therefore leave a rounding residual around 10^-28. A residual
# larger than this bound is a genuine arithmetic failure, not rounding noise.
NO_VIG_RESIDUAL_TOLERANCE = Decimal("1e-18")


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


def overround(odds: Sequence[Decimal | float | str]) -> Decimal:
    """Sum of implied probabilities. This is not the bookmaker margin (sum - 1)."""

    if not odds:
        raise ValueError("Market overround requires at least one decimal odds.")
    return _overround_from_implied(implied_probability(item) for item in odds)


def no_vig_probability(
    odds: Decimal | float | str,
    market_odds: Sequence[Decimal | float | str],
) -> Decimal:
    return implied_probability(odds) / overround(market_odds)


def no_vig_probabilities(
    odds_by_selection: Mapping[Football1x2Selection, Decimal],
) -> tuple[dict[Football1x2Selection, Decimal], Decimal]:
    if set(odds_by_selection) != set(Football1x2Selection):
        raise ValueError("No-vig calculation requires a complete football 1X2 market.")
    raw = {selection: implied_probability(odds) for selection, odds in odds_by_selection.items()}
    market_overround = _overround_from_implied(raw.values())
    normalized = {selection: value / market_overround for selection, value in raw.items()}
    residual = Decimal(1) - sum(normalized.values(), Decimal(0))
    if abs(residual) > NO_VIG_RESIDUAL_TOLERANCE:
        raise ArithmeticError("No-vig probabilities do not form a valid simplex.")

    # Canonical HOME/DRAW/AWAY order. The last selection absorbs the rounding
    # residual so the returned simplex sums to Decimal(1) exactly.
    ordered = tuple(Football1x2Selection)
    simplex = {selection: normalized[selection] for selection in ordered[:-1]}
    simplex[ordered[-1]] = Decimal(1) - sum(simplex.values(), Decimal(0))
    if any(not Decimal(0) < value < Decimal(1) for value in simplex.values()):
        raise ArithmeticError("No-vig probabilities must each lie in (0, 1).")
    if sum(simplex.values(), Decimal(0)) != Decimal(1):
        raise ArithmeticError("No-vig probabilities do not sum to 1.")
    return simplex, market_overround


def edge(model_probability: Decimal | float | str, implied: Decimal | float | str) -> Decimal:
    return probability(model_probability) - probability(implied)


def expected_value(
    model_probability: Decimal | float | str,
    odds: Decimal | float | str,
) -> Decimal:
    return probability(model_probability) * decimal_odds(odds) - Decimal(1)


def _overround_from_implied(values: Iterable[Decimal]) -> Decimal:
    total = sum(values, Decimal(0))
    if total <= 0:
        raise ValueError("Market overround must be positive.")
    return total
