from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from predicta_ml.oos.errors import OosProtocolError
from predicta_ml.oos.odds import OddsQuote
from predicta_ml.oos.predictions import FrozenPrediction
from predicta_ml.oos.protocol import VALUE_ENGINE_VERSION


class ValueCalculator(Protocol):
    """Production Value Engine v0.1. Implementations must wrap the canonical calculator."""

    def implied_probability(self, odds: Decimal) -> Decimal: ...

    def no_vig_probabilities(
        self, odds_by_selection: dict[str, Decimal]
    ) -> tuple[dict[str, Decimal], Decimal]: ...

    def edge(self, model_probability: Decimal, implied: Decimal) -> Decimal: ...

    def expected_value(self, model_probability: Decimal, odds: Decimal) -> Decimal: ...


@dataclass(frozen=True)
class SelectionValue:
    selection: str
    odds: float
    model_probability: float
    implied_probability: float
    no_vig_probability: float
    edge: float
    ev: float


@dataclass(frozen=True)
class MatchValue:
    match_id: str
    overround: float
    value_engine_version: str
    selections: tuple[SelectionValue, ...]


def evaluate_match_value(
    prediction: FrozenPrediction,
    quote: OddsQuote,
    calculator: ValueCalculator,
) -> MatchValue:
    if prediction.match_id != quote.match_id:
        raise OosProtocolError("Value evaluation match_id does not match the odds snapshot.")
    odds_by_selection = {
        "HOME": Decimal(str(quote.home_odds)),
        "DRAW": Decimal(str(quote.draw_odds)),
        "AWAY": Decimal(str(quote.away_odds)),
    }
    probabilities = {
        "HOME": Decimal(str(prediction.home)),
        "DRAW": Decimal(str(prediction.draw)),
        "AWAY": Decimal(str(prediction.away)),
    }
    no_vig, overround = calculator.no_vig_probabilities(odds_by_selection)
    rows: list[SelectionValue] = []
    for selection in ("HOME", "DRAW", "AWAY"):
        odds = odds_by_selection[selection]
        implied = calculator.implied_probability(odds)
        rows.append(
            SelectionValue(
                selection=selection,
                odds=float(odds),
                model_probability=float(probabilities[selection]),
                implied_probability=float(implied),
                no_vig_probability=float(no_vig[selection]),
                edge=float(calculator.edge(probabilities[selection], implied)),
                ev=float(calculator.expected_value(probabilities[selection], odds)),
            )
        )
    return MatchValue(
        match_id=prediction.match_id,
        overround=float(overround),
        value_engine_version=VALUE_ENGINE_VERSION,
        selections=tuple(rows),
    )


def selection_map(value: MatchValue) -> dict[str, SelectionValue]:
    return {item.selection: item for item in value.selections}
