from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.ai_analyst.context import (
    AnalystContext,
    AnalystIdentity,
    AnalystPrediction,
    highest_ev_selection,
    value_for_selection,
)
from app.ai_analyst.deterministic import DeterministicAnalystProvider, confidence_from_context, format_percent
from app.ai_analyst.grounding import AnalystGroundingError
from app.ai_analyst.models import ANALYST_VERSION, CONFIDENCE_RULE, FootballAnalystExplanation, FootballAnalystFactor
from app.ai_analyst.service import FootballAnalystService
from app.core.clock import Clock
from app.core.errors import NotFoundError
from app.match_identity.models import MatchIdentity
from app.odds.exceptions import OddsTemporalLeakageError, OddsUnavailableError
from app.odds.providers import MockOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.types import Football1x2Selection, OddsSelection, OddsSnapshot
from app.predictions.exceptions import PitFeaturesUnavailableError, TemporalLeakageError
from app.schemas import FootballModelPrediction
from app.value_engine.calculator import VALUE_ENGINE_VERSION
from app.value_engine.models import FootballValueAnalysis
from app.value_engine.service import FootballValueService

MATCH_ID = "match_ai_analyst"
CUTOFF = datetime(2026, 7, 7, 16, tzinfo=UTC)


class StaticPredictionService:
    def __init__(self, prediction: FootballModelPrediction | None = None) -> None:
        self.prediction = prediction or _prediction()

    def predict(self, match_id: str, cutoff_at: datetime | None) -> FootballModelPrediction:
        return self.prediction.model_copy(
            update={"match_id": match_id, "cutoff_at": cutoff_at or self.prediction.cutoff_at}
        )


class MissingPredictionService:
    def predict(self, match_id: str, cutoff_at: datetime | None) -> FootballModelPrediction:
        raise PitFeaturesUnavailableError("Prediction is absent.")


class StaticValueService:
    def __init__(self, analysis: FootballValueAnalysis) -> None:
        self.analysis = analysis

    def evaluate(self, match_id: str, cutoff_at: datetime | None) -> FootballValueAnalysis:
        return self.analysis.model_copy(update={"match_id": match_id})


class RaisingValueService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def evaluate(self, match_id: str, cutoff_at: datetime | None) -> FootballValueAnalysis:
        raise self.error


class StaticIdentities:
    def __init__(self, identity: MatchIdentity | None) -> None:
        self.identity = identity

    def get(self, match_id: str) -> MatchIdentity | None:
        if self.identity is None or self.identity.match_id != match_id:
            return None
        return self.identity


def _prediction(**overrides: object) -> FootballModelPrediction:
    values: dict[str, object] = {
        "match_id": MATCH_ID,
        "home_probability": 0.612,
        "draw_probability": 0.194,
        "away_probability": 0.194,
        "model_version": "football-elo-v1-candidate",
        "dataset_version": "football-1x2-history-0.3",
        "feature_schema_version": "football-1x2-features-0.3",
        "model_status": "candidate",
        "cutoff_at": CUTOFF,
        "cutoff_policy": "pre_kickoff",
        "generated_at": CUTOFF,
    }
    values.update(overrides)
    return FootballModelPrediction(**values)  # type: ignore[arg-type]


def _identity(*, home: str | None = "Home FC", away: str | None = "Away FC") -> MatchIdentity:
    return MatchIdentity(
        match_id=MATCH_ID,
        home_team_id="tm_home",
        away_team_id="tm_away",
        home_team=home,
        away_team=away,
        league="Test League",
        kickoff_at=CUTOFF,
        data_mode="live",
    )


def _analysis() -> FootballValueAnalysis:
    snapshot = OddsSnapshot(
        id="snapshot",
        provider_id="provider-snapshot",
        match_id=MATCH_ID,
        bookmaker="Fictional Sportsbook",
        market="1X2",
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal("2.00")),
            OddsSelection(Football1x2Selection.DRAW, Decimal("4.00")),
            OddsSelection(Football1x2Selection.AWAY, Decimal("5.00")),
        ),
        collected_at=CUTOFF - timedelta(hours=2),
        available_at=CUTOFF - timedelta(hours=1),
        source="test-mock-odds",
        data_mode="mock",
    )
    provider = MockOddsProvider((snapshot,))
    provider.source = "test-mock-odds"
    return FootballValueService(
        clock=Clock(CUTOFF),
        predictions=StaticPredictionService(),
        odds=OddsService(provider=provider, repository=InMemoryOddsRepository()),
    ).evaluate(MATCH_ID, CUTOFF)


def _context(*, identity: MatchIdentity | None = None, value: bool = True) -> AnalystContext:
    resolved = identity or _identity()
    prediction = AnalystPrediction(
        home_probability=Decimal("0.612"),
        draw_probability=Decimal("0.194"),
        away_probability=Decimal("0.194"),
        model_version="football-elo-v1-candidate",
        model_status="candidate",
        dataset_version="football-1x2-history-0.3",
        cutoff_at=CUTOFF,
    )
    analysis = _analysis() if value else None
    return AnalystContext(
        identity=AnalystIdentity(
            match_id=resolved.match_id,
            home_team=resolved.home_team,
            away_team=resolved.away_team,
            league=resolved.league,
            kickoff_at=resolved.kickoff_at,
        ),
        prediction=prediction,
        value=value_for_selection(analysis, prediction.favorite_selection()) if analysis else None,
        generated_at=CUTOFF,
        data_mode="mock",
        value_selection=highest_ev_selection(analysis) if analysis else None,
    )


def _service(
    *,
    identity: MatchIdentity | None = None,
    predictions: object | None = None,
    values: object | None = None,
) -> FootballAnalystService:
    return FootballAnalystService(
        clock=Clock(CUTOFF),
        identities=StaticIdentities(_identity() if identity is None else identity),
        predictions=predictions or StaticPredictionService(),  # type: ignore[arg-type]
        values=values or StaticValueService(_analysis()),  # type: ignore[arg-type]
    )


def test_complete_context_is_explained_without_choosing_a_bet() -> None:
    report = _service().explain(MATCH_ID, CUTOFF)
    assert report.prediction.model_status == "candidate"
    assert report.prediction.model_version == "football-elo-v1-candidate"
    assert report.model_favorite == "HOME"
    assert report.value.availability == "available"
    assert report.value.selection == "HOME"
    assert report.value.value_selection == "HOME"
    assert report.value.odds == pytest.approx(2.0)
    assert report.value.implied_probability == pytest.approx(0.5)
    assert report.value.edge == pytest.approx(0.112)
    assert report.value.ev == pytest.approx(0.224)
    assert report.value.value_engine_version == VALUE_ENGINE_VERSION
    assert report.analyst.analysis_version == ANALYST_VERSION
    assert report.analyst.analysis_version != VALUE_ENGINE_VERSION
    assert "61,2 %" in report.analyst.summary
    assert "50,0 %" in report.analyst.summary
    assert "pari" not in report.analyst.summary.casefold()


def test_partial_identity_does_not_invent_team_names() -> None:
    report = _service(identity=_identity(home=None, away=None)).explain(MATCH_ID, CUTOFF)
    assert report.home_team is None
    assert report.away_team is None
    assert "home_team" in report.analyst.data_quality.missing
    assert "Away Invented" not in report.analyst.summary
    assert "l'équipe à domicile" in report.analyst.summary


def test_absent_odds_and_value_are_explicit() -> None:
    report = _service(values=RaisingValueService(OddsUnavailableError("No odds."))).explain(MATCH_ID, CUTOFF)
    assert report.value.availability == "unavailable"
    assert report.value.selection is None
    assert report.value.value_selection is None
    assert report.value.odds is None
    assert report.value.edge is None
    assert report.value.ev is None
    assert "value" in report.analyst.data_quality.missing
    assert "aucune probabilité implicite" in report.analyst.summary.casefold()
    assert all(factor.type != "edge" for factor in report.analyst.key_factors)


def test_candidate_confidence_is_metadata_based() -> None:
    complete = confidence_from_context(_context())
    assert complete.level == "medium"
    missing_value = confidence_from_context(_context(value=False))
    assert missing_value.level == "low"
    assert "0.612" not in missing_value.basis


def test_valid_cutoff_and_cutoff_before_odds_availability() -> None:
    report = _service().explain(MATCH_ID, CUTOFF)
    assert report.prediction.cutoff_at == CUTOFF
    leaked = _analysis().model_copy(
        update={"odds": _analysis().odds.model_copy(update={"available_at": CUTOFF + timedelta(minutes=1)})}
    )
    with pytest.raises(OddsTemporalLeakageError):
        _service(values=StaticValueService(leaked)).explain(MATCH_ID, CUTOFF)


def test_temporal_leakage_from_identity_mismatch() -> None:
    identity = MatchIdentity(
        match_id=MATCH_ID,
        home_team_id="tm_home",
        away_team_id="tm_away",
        home_team="Home FC",
        away_team="Away FC",
        league="Test League",
        kickoff_at=CUTOFF + timedelta(hours=1),
        data_mode="live",
    )
    with pytest.raises(TemporalLeakageError):
        _service(identity=identity).explain(MATCH_ID, CUTOFF)


def test_deterministic_provider_is_pure() -> None:
    context = _context()
    provider = DeterministicAnalystProvider()
    first = provider.generate_analysis(context)
    second = provider.generate_analysis(context)
    assert first.model_dump() == second.model_dump()
    assert first.generated_at == context.generated_at


def test_factual_claims_are_grounded_in_context() -> None:
    context = _context()
    explanation = DeterministicAnalystProvider().generate_analysis(context)
    favorite = context.favorite_selection()
    assert format_percent(context.prediction.probability(favorite)) in explanation.summary
    assert context.value is not None
    assert format_percent(context.value.implied_probability) in explanation.summary
    sources = {factor.source for factor in explanation.key_factors}
    assert sources <= {context.prediction.source, context.value.source, context.value.odds_source}
    serialized = explanation.summary.casefold()
    for term in ("garanti", "blessure", "composition", "gain", "sure win"):
        assert term not in serialized


def test_versioning_and_missing_match() -> None:
    report = _service().explain(MATCH_ID, CUTOFF)
    assert report.analyst.analysis_version == "ai-analyst-0.1"
    assert report.value.value_engine_version == "value-engine-0.1"
    with pytest.raises(NotFoundError):
        _service().explain("mth_unknown", CUTOFF)


def test_prediction_unavailable_is_not_masked() -> None:
    with pytest.raises(PitFeaturesUnavailableError):
        _service(predictions=MissingPredictionService()).explain(MATCH_ID, CUTOFF)


def _divergent_prediction() -> FootballModelPrediction:
    return _prediction(home_probability=0.60, draw_probability=0.15, away_probability=0.25)


def _divergent_analysis() -> FootballValueAnalysis:
    snapshot = OddsSnapshot(
        id="snapshot-divergent",
        provider_id="provider-snapshot-divergent",
        match_id=MATCH_ID,
        bookmaker="Fictional Sportsbook",
        market="1X2",
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal("1.40")),
            OddsSelection(Football1x2Selection.DRAW, Decimal("4.00")),
            OddsSelection(Football1x2Selection.AWAY, Decimal("6.25")),
        ),
        collected_at=CUTOFF - timedelta(hours=2),
        available_at=CUTOFF - timedelta(hours=1),
        source="test-mock-odds",
        data_mode="mock",
    )
    provider = MockOddsProvider((snapshot,))
    provider.source = "test-mock-odds"
    return FootballValueService(
        clock=Clock(CUTOFF),
        predictions=StaticPredictionService(_divergent_prediction()),
        odds=OddsService(provider=provider, repository=InMemoryOddsRepository()),
    ).evaluate(MATCH_ID, CUTOFF)


def test_model_favorite_is_distinct_from_best_ev() -> None:
    report = _service(
        predictions=StaticPredictionService(_divergent_prediction()),
        values=StaticValueService(_divergent_analysis()),
    ).explain(MATCH_ID, CUTOFF)
    assert report.model_favorite == "HOME"
    assert report.value.selection == "HOME"
    assert report.prediction.home_probability == pytest.approx(0.60)
    assert report.value.odds == pytest.approx(1.40)
    assert report.value.ev == pytest.approx(-0.16)
    assert report.value.value_selection == "AWAY"
    assert report.model_favorite != report.value.value_selection
    serialized = report.model_dump_json().casefold()
    for term in ("bet", "pick", "recommended bet", "pari"):
        assert term not in serialized


def _prediction_facts(
    *,
    home: str = "0.90",
    status: str = "candidate",
) -> AnalystPrediction:
    return AnalystPrediction(
        home_probability=Decimal(home),
        draw_probability=Decimal("0.05"),
        away_probability=Decimal("0.05"),
        model_version="football-elo-v1-candidate",
        model_status=status,  # type: ignore[arg-type]
        dataset_version="football-1x2-history-0.3",
        cutoff_at=CUTOFF,
    )


def test_confidence_rule_matches_canonical_http_behavior() -> None:
    mock_complete = confidence_from_context(_context())
    assert mock_complete.level == "medium"
    assert mock_complete.rule == CONFIDENCE_RULE
    assert "including mock" in mock_complete.rule
    candidate = confidence_from_context(
        AnalystContext(
            identity=_context().identity,
            prediction=_prediction_facts(),
            value=_context().value,
            generated_at=CUTOFF,
            data_mode="mock",
            value_selection=_context().value_selection,
        )
    )
    assert candidate.level == "medium"
    assert candidate.level != "high"
    assert confidence_from_context(_context(value=False)).level == "low"
    assert confidence_from_context(_context(identity=_identity(home=None, away=None))).level == "low"


def test_candidate_never_emits_high() -> None:
    baseline = _context()
    live_champion = AnalystContext(
        identity=baseline.identity,
        prediction=_prediction_facts(status="champion"),
        value=baseline.value,
        generated_at=CUTOFF,
        data_mode="live",
        value_selection=baseline.value_selection,
    )
    assert confidence_from_context(live_champion).level == "high"
    candidate = AnalystContext(
        identity=baseline.identity,
        prediction=_prediction_facts(status="candidate"),
        value=baseline.value,
        generated_at=CUTOFF,
        data_mode="live",
        value_selection=baseline.value_selection,
    )
    assert confidence_from_context(candidate).level == "medium"


class _PassthroughProvider:
    def generate_analysis(self, context: AnalystContext) -> FootballAnalystExplanation:
        return DeterministicAnalystProvider().generate_analysis(context)


class _InventingProvider:
    def generate_analysis(self, context: AnalystContext) -> FootballAnalystExplanation:
        explanation = DeterministicAnalystProvider().generate_analysis(context)
        invented = FootballAnalystFactor(
            type="ev",
            label="Invented EV",
            value=0.99,
            direction="away",
            source="llm-hallucination",
        )
        return explanation.model_copy(update={"key_factors": [*explanation.key_factors, invented]})


def test_future_llm_cannot_mutate_numeric_context() -> None:
    service = FootballAnalystService(
        clock=Clock(CUTOFF),
        identities=StaticIdentities(_identity()),
        predictions=StaticPredictionService(),
        values=StaticValueService(_analysis()),
        provider=_PassthroughProvider(),
    )
    report = service.explain(MATCH_ID, CUTOFF)
    context_prediction = _context().to_prediction_dto()
    assert report.prediction.home_probability == context_prediction.home_probability
    assert report.prediction.model_version == "football-elo-v1-candidate"
    assert report.prediction.cutoff_at == CUTOFF
    assert report.value.ev == pytest.approx(0.224)
    assert report.analyst.data_quality.data_mode == "mock"


def test_future_llm_ungrounded_factor_is_rejected() -> None:
    service = FootballAnalystService(
        clock=Clock(CUTOFF),
        identities=StaticIdentities(_identity()),
        predictions=StaticPredictionService(),
        values=StaticValueService(_analysis()),
        provider=_InventingProvider(),
    )
    with pytest.raises(AnalystGroundingError):
        service.explain(MATCH_ID, CUTOFF)
