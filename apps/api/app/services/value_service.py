from app.domain import value_engine as ve
from app.schemas import MatchDetail, OddsSelection, OddsSnapshot, ValueOpportunity, ValuePreview
from app.services.projections import to_match_summary


def value_preview_for_match(match: MatchDetail) -> ValuePreview | None:
    opportunity = best_opportunity(match)
    if opportunity is None:
        return None
    return ValuePreview(
        selection=opportunity.selection,
        edge=opportunity.edge_raw,
        expected_value=opportunity.expected_value,
        formula_version=opportunity.formula_version,
        quality=opportunity.quality,
    )


def opportunities_for_match(match: MatchDetail) -> list[ValueOpportunity]:
    prediction = match.prediction
    odds = match.odds
    if prediction is None or odds is None:
        return []
    if prediction.market != odds.market:
        return []
    items: list[ValueOpportunity] = []
    for outcome in prediction.outcomes:
        selection = _selection_for(odds, outcome.selection)
        if selection is None or outcome.calibrated_probability is None:
            continue
        if selection.decimal_odds is None:
            continue
        implied = ve.implied_probability_raw(selection.decimal_odds)
        market_odds = [item.decimal_odds for item in odds.selections if item.decimal_odds is not None]
        no_vig = ve.no_vig_probability(selection.decimal_odds, market_odds)
        edge_raw = ve.edge(outcome.calibrated_probability, implied)
        edge_no_vig = ve.edge(outcome.calibrated_probability, no_vig)
        expected = ve.expected_value(outcome.calibrated_probability, selection.decimal_odds)
        items.append(
            ValueOpportunity(
                id=f"val_{match.id}_{outcome.selection}",
                match=to_match_summary(match),
                market=prediction.market,
                selection=outcome.selection,
                selection_label=outcome.label,
                calibrated_probability=outcome.calibrated_probability,
                decimal_odds=selection.decimal_odds,
                implied_probability_raw=ve.to_float(implied),
                no_vig_probability=ve.to_float(no_vig),
                overround=odds.overround,
                edge_raw=ve.to_float(edge_raw),
                edge_no_vig=ve.to_float(edge_no_vig),
                expected_value=ve.to_float(expected),
                formula_version=ve.FORMULA_VERSION,
                odds_observed_at=odds.observed_at,
                prediction_cutoff_at=prediction.cutoff_at,
                quality=odds.quality,
            )
        )
    return items


def best_opportunity(match: MatchDetail) -> ValueOpportunity | None:
    items = opportunities_for_match(match)
    if not items:
        return None
    return max(items, key=lambda item: item.edge_raw or -1)


def _selection_for(odds: OddsSnapshot, selection: str) -> OddsSelection | None:
    return next((item for item in odds.selections if item.selection == selection), None)
