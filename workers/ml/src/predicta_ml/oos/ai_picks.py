from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from predicta_ml.oos.errors import OosProtocolError
from predicta_ml.oos.odds import OddsQuote, odds_age_seconds
from predicta_ml.oos.predictions import FrozenPrediction
from predicta_ml.oos.protocol import (
    AI_PICKS_VERSION,
    MAXIMUM_ODDS_AGE,
    MINIMUM_EDGE,
    MINIMUM_EV,
    MINIMUM_MODEL_PROBABILITY,
)
from predicta_ml.oos.value import MatchValue, SelectionValue


@dataclass(frozen=True)
class PickDecision:
    match_id: str
    selection: str
    eligible: bool
    exclusion_reason: str | None
    rank: int | None
    opportunity_score: float | None
    value: SelectionValue
    odds_age_seconds: float
    data_freshness: int
    ai_picks_version: str = AI_PICKS_VERSION


def published_thresholds() -> dict[str, float | int | bool]:
    return {
        "minimum_edge": MINIMUM_EDGE,
        "minimum_ev": MINIMUM_EV,
        "minimum_model_probability": MINIMUM_MODEL_PROBABILITY,
        "maximum_odds_age_seconds": int(MAXIMUM_ODDS_AGE.total_seconds()),
        "optimized_on_oos": False,
    }


def exclusion_reason(
    *,
    value: SelectionValue,
    odds_age: timedelta,
    maximum_odds_age: timedelta = MAXIMUM_ODDS_AGE,
    minimum_edge: float = MINIMUM_EDGE,
    minimum_ev: float = MINIMUM_EV,
    minimum_model_probability: float = MINIMUM_MODEL_PROBABILITY,
) -> str | None:
    """Published AI Picks v0.1 eligibility gates. Production scoring uses AiPicksEngine."""

    if odds_age > maximum_odds_age:
        return "stale_odds"
    if value.model_probability < minimum_model_probability:
        return "below_minimum_model_probability"
    if value.ev < 0:
        return "negative_ev"
    if value.ev < minimum_ev:
        return "below_minimum_ev"
    if value.edge < 0:
        return "negative_edge"
    if value.edge < minimum_edge:
        return "below_minimum_edge"
    return None


def decide_picks(
    *,
    prediction: FrozenPrediction,
    quote: OddsQuote,
    value: MatchValue,
    cutoff_at: datetime,
) -> tuple[PickDecision, ...]:
    if prediction.match_id != quote.match_id or value.match_id != quote.match_id:
        raise OosProtocolError("AI Picks identity does not match prediction/odds.")
    age = timedelta(seconds=odds_age_seconds(quote, cutoff_at))
    freshness = 2 if age <= MAXIMUM_ODDS_AGE / 2 else 1
    decisions: list[PickDecision] = []
    for item in value.selections:
        reason = exclusion_reason(value=item, odds_age=age)
        score = item.ev + item.edge
        decisions.append(
            PickDecision(
                match_id=prediction.match_id,
                selection=item.selection,
                eligible=reason is None,
                exclusion_reason=reason,
                rank=None,
                opportunity_score=score if reason is None else None,
                value=item,
                odds_age_seconds=age.total_seconds(),
                data_freshness=freshness,
            )
        )
    eligible = [item for item in decisions if item.eligible]
    ranked = sorted(
        eligible,
        key=lambda item: (
            -(item.opportunity_score or 0.0),
            -item.value.ev,
            -item.value.edge,
            -item.data_freshness,
            item.match_id,
            item.selection,
        ),
    )
    ranks = {item.selection: index + 1 for index, item in enumerate(ranked)}
    return tuple(
        PickDecision(
            match_id=item.match_id,
            selection=item.selection,
            eligible=item.eligible,
            exclusion_reason=item.exclusion_reason,
            rank=ranks.get(item.selection),
            opportunity_score=item.opportunity_score,
            value=item.value,
            odds_age_seconds=item.odds_age_seconds,
            data_freshness=item.data_freshness,
        )
        for item in decisions
    )
