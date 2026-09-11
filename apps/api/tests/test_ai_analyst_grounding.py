from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.ai_analyst.context import (
    AnalystContext,
    AnalystIdentity,
    AnalystPrediction,
    AnalystValue,
)
from app.ai_analyst.deterministic import DeterministicAnalystProvider
from app.ai_analyst.grounding import AnalystGroundingError, assert_grounded
from app.ai_analyst.models import FootballAnalystExplanation
from app.ai_analyst.service import FootballAnalystService
from app.core.clock import Clock
from app.match_identity.models import MatchIdentity
from app.odds.types import Football1x2Selection
from tests.test_ai_analyst_engine import StaticIdentities, StaticPredictionService, StaticValueService, _analysis

CUTOFF = datetime(2026, 7, 7, 16, tzinfo=UTC)
HOME_PROBABILITY = Decimal("0.417")


def _identity(*, home: str = "Team A", away: str = "Team B") -> AnalystIdentity:
    return AnalystIdentity(
        match_id="match_grounding",
        home_team=home,
        away_team=away,
        league="Test League",
        kickoff_at=CUTOFF,
    )


def _prediction() -> AnalystPrediction:
    return AnalystPrediction(
        home_probability=HOME_PROBABILITY,
        draw_probability=Decimal("0.291"),
        away_probability=Decimal("0.292"),
        model_version="football-elo-v1-candidate",
        model_status="candidate",
        dataset_version="football-1x2-history-0.3",
        cutoff_at=CUTOFF,
    )


def _value(*, ev: Decimal = Decimal("-0.167")) -> AnalystValue:
    return AnalystValue(
        selection=Football1x2Selection.HOME,
        odds=Decimal("2.00"),
        implied_probability=Decimal("0.500"),
        no_vig_probability=Decimal("0.450"),
        edge=Decimal("-0.083"),
        ev=ev,
        value_engine_version="value-engine-0.1",
        odds_available_at=CUTOFF - timedelta(hours=1),
        odds_source="test-mock-odds",
        data_mode="mock",
    )


def _context(*, value: AnalystValue | None = None, include_value: bool = True) -> AnalystContext:
    return AnalystContext(
        identity=_identity(),
        prediction=_prediction(),
        value=_value() if include_value and value is None else value,
        generated_at=CUTOFF,
        data_mode="mock",
        value_selection=Football1x2Selection.AWAY if include_value else None,
    )


def _with_summary(context: AnalystContext, summary: str) -> FootballAnalystExplanation:
    explanation = DeterministicAnalystProvider().generate_analysis(context)
    return explanation.model_copy(update={"summary": summary})


class _SummaryProvider:
    def __init__(self, summary: str) -> None:
        self.summary = summary

    def generate_analysis(self, context: AnalystContext) -> FootballAnalystExplanation:
        return _with_summary(context, self.summary)


def test_invented_home_probability_in_summary_is_rejected() -> None:
    context = _context()
    with pytest.raises(AnalystGroundingError, match="80"):
        assert_grounded(context, _with_summary(context, "HOME has 80% probability."))


def test_grounded_home_probability_in_summary_is_accepted() -> None:
    context = _context()
    explanation = _with_summary(context, "HOME = 41.7%")
    assert_grounded(context, explanation)


def test_odds_claim_rejected_when_odds_are_absent() -> None:
    context = _context(include_value=False)
    with pytest.raises(AnalystGroundingError, match="Odds"):
        assert_grounded(context, _with_summary(context, "odds = 1.80"))


def test_invented_home_ev_is_rejected() -> None:
    context = _context(value=_value(ev=Decimal("-0.167")))
    with pytest.raises(AnalystGroundingError, match="56"):
        assert_grounded(context, _with_summary(context, "EV = +56.3%"))


def test_invented_team_token_is_rejected() -> None:
    context = _context()
    with pytest.raises(AnalystGroundingError, match="Team C"):
        assert_grounded(context, _with_summary(context, "Team C is the model favorite."))


def test_ungrounded_factual_summary_is_rejected() -> None:
    context = _context()
    with pytest.raises(AnalystGroundingError):
        assert_grounded(
            context,
            _with_summary(context, "Real Madrid est favori avec une cote de 9.99."),
        )


def test_qualitative_summary_without_new_facts_is_accepted() -> None:
    context = _context()
    explanation = _with_summary(
        context,
        "Le match paraît ouvert. L'incertitude reste élevée et le texte reste interprétatif.",
    )
    assert_grounded(context, explanation)


def test_same_context_yields_the_same_grounded_summary() -> None:
    context = _context()
    provider = DeterministicAnalystProvider()
    first = provider.generate_analysis(context)
    second = provider.generate_analysis(context)
    assert first.summary == second.summary
    assert first.model_dump() == second.model_dump()


def test_service_rejects_summary_only_hallucination() -> None:
    identity = MatchIdentity(
        match_id="match_ai_analyst",
        home_team_id="tm_home",
        away_team_id="tm_away",
        home_team="Team A",
        away_team="Team B",
        league="Test League",
        kickoff_at=CUTOFF,
        data_mode="live",
    )
    service = FootballAnalystService(
        clock=Clock(CUTOFF),
        identities=StaticIdentities(identity),
        predictions=StaticPredictionService(),
        values=StaticValueService(_analysis()),
        provider=_SummaryProvider("HOME has 80% probability."),
    )
    with pytest.raises(AnalystGroundingError, match="80"):
        service.explain("match_ai_analyst", CUTOFF)
