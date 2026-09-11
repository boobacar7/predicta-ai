from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from app.ai_analyst.deterministic import DeterministicAnalystProvider
from app.ai_analyst.factory import build_analyst_provider, build_llm_client
from app.ai_analyst.llm_client import (
    MOCK_EXPLAINER_MODEL,
    AnalystLLMError,
    MockExplainerClient,
    ScriptedLLMClient,
)
from app.ai_analyst.llm_provider import (
    FORBIDDEN_LLM_FIELDS,
    LLMAnalystProvider,
    build_narration_prompt,
)
from app.ai_analyst.models import ANALYST_PROVIDER_ID, LLM_ANALYST_PROVIDER_ID
from app.ai_analyst.service import FootballAnalystService
from app.core.clock import Clock
from tests.conftest import TestSettings as ApiSettings
from tests.test_ai_analyst_engine import (
    MATCH_ID,
    StaticIdentities,
    StaticPredictionService,
    StaticValueService,
    _analysis,
    _identity,
)
from tests.test_ai_analyst_grounding import CUTOFF, _context

NOW = datetime(2026, 7, 7, 16, tzinfo=UTC)


def _scripted(payload: str | Exception, *, delay_seconds: float = 0) -> LLMAnalystProvider:
    return LLMAnalystProvider(
        ScriptedLLMClient(payload, delay_seconds=delay_seconds),
        timeout_seconds=0.05,
    )


def _statements(*items: tuple[str, list[str]]) -> str:
    return json.dumps(
        {"statements": [{"statement": text, "evidence_ids": ids} for text, ids in items]},
        ensure_ascii=False,
    )


def _valid_home_statement() -> str:
    return _statements(
        (
            "Le modèle estime 41,7 % de probabilité modélisée pour Team A.",
            ["prediction.home_probability", "identity.home_team", "prediction.model_favorite"],
        )
    )


def test_llm_narration_is_grounded_and_does_not_own_business_fields() -> None:
    context = _context()
    provider = LLMAnalystProvider(MockExplainerClient())
    explanation = provider.generate_analysis(context)
    assert provider.last_fallback_reason is None
    assert explanation.provider == LLM_ANALYST_PROVIDER_ID
    assert "41,7 %" in explanation.summary
    assert "data_mode mock" in explanation.summary
    assert "candidate" in explanation.summary
    assert explanation.data_quality.data_mode == "mock"
    assert explanation.confidence.level == "medium"
    assert context.to_prediction_dto().home_probability == 0.417
    again = provider.generate_analysis(context)
    assert again.model_dump() == explanation.model_dump()


def test_probability_hallucination_falls_back() -> None:
    context = _context()
    provider = _scripted(
        _statements(("HOME has 80% probability.", ["prediction.home_probability"]))
    )
    explanation = provider.generate_analysis(context)
    assert provider.last_fallback_reason == "AnalystGroundingError"
    assert explanation.provider == ANALYST_PROVIDER_ID
    assert "80" not in explanation.summary
    assert "41,7 %" in explanation.summary


def test_odds_hallucination_falls_back() -> None:
    provider = _scripted(_statements(("odds = 9.99", ["value.odds"])))
    explanation = provider.generate_analysis(_context())
    assert provider.last_fallback_reason == "AnalystGroundingError"
    assert "9.99" not in explanation.summary
    assert explanation.provider == ANALYST_PROVIDER_ID


def test_ev_hallucination_falls_back() -> None:
    provider = _scripted(_statements(("EV = +56.3", ["value.ev"])))
    explanation = provider.generate_analysis(_context())
    assert provider.last_fallback_reason == "AnalystGroundingError"
    assert "56,3" not in explanation.summary
    assert "56.3" not in explanation.summary


def test_edge_hallucination_falls_back() -> None:
    provider = _scripted(_statements(("edge = +0.990", ["value.edge"])))
    explanation = provider.generate_analysis(_context())
    assert provider.last_fallback_reason == "AnalystGroundingError"
    assert "+0.990" not in explanation.summary


def test_team_hallucination_falls_back() -> None:
    provider = _scripted(
        _statements(("Team C is the model favorite.", ["prediction.model_favorite"]))
    )
    explanation = provider.generate_analysis(_context())
    assert provider.last_fallback_reason == "AnalystGroundingError"
    assert "Team C" not in explanation.summary


def test_unsupported_statistic_falls_back() -> None:
    provider = _scripted(
        _statements(("La possession est de 62 %.", ["prediction.home_probability"]))
    )
    explanation = provider.generate_analysis(_context())
    assert provider.last_fallback_reason == "AnalystGroundingError"
    assert "possession" not in explanation.summary.casefold()


def test_unsupported_injury_falls_back() -> None:
    provider = _scripted(_statements(("There is an injury in the squad.", [])))
    explanation = provider.generate_analysis(_context())
    assert provider.last_fallback_reason == "AnalystGroundingError"
    assert "injury" not in explanation.summary.casefold()


def test_unsupported_lineup_falls_back() -> None:
    provider = _scripted(_statements(("The lineup is unavailable but we invent it.", [])))
    explanation = provider.generate_analysis(_context())
    assert provider.last_fallback_reason == "AnalystGroundingError"
    assert "lineup" not in explanation.summary.casefold()


def test_unsupported_result_falls_back() -> None:
    provider = _scripted(_statements(("Team A a gagné le match.", ["identity.home_team"])))
    explanation = provider.generate_analysis(_context())
    assert provider.last_fallback_reason == "AnalystGroundingError"
    assert "a gagné le match" not in explanation.summary.casefold()


def test_invalid_evidence_id_falls_back() -> None:
    provider = _scripted(
        _statements(("Le modèle estime 41,7 %.", ["prediction.invented"]))
    )
    explanation = provider.generate_analysis(_context())
    assert provider.last_fallback_reason == "AnalystGroundingError"
    assert explanation.provider == ANALYST_PROVIDER_ID


def test_evidence_fact_mismatch_falls_back() -> None:
    provider = _scripted(
        _statements(
            (
                "Le modèle estime 29,2 % de probabilité modélisée.",
                ["prediction.home_probability"],
            )
        )
    )
    explanation = provider.generate_analysis(_context())
    assert provider.last_fallback_reason == "AnalystGroundingError"
    assert explanation.provider == ANALYST_PROVIDER_ID


def test_favorite_value_confusion_falls_back() -> None:
    context = _context()
    assert context.favorite_selection().value == "HOME"
    assert context.value_selection is not None
    assert context.value_selection.value == "AWAY"
    provider = _scripted(
        _statements(
            (
                "Team B is the model favorite.",
                ["value.value_selection", "identity.away_team", "prediction.model_favorite"],
            )
        )
    )
    explanation = provider.generate_analysis(context)
    assert provider.last_fallback_reason == "AnalystGroundingError"
    assert "team b is the model favorite" not in explanation.summary.casefold()
    assert context.to_value_dto().value_selection == "AWAY"
    assert context.to_prediction_dto().model_version == "football-elo-v1-candidate"


def test_candidate_model_cannot_be_promoted() -> None:
    context = _context()
    provider = _scripted(
        _statements(
            (
                "Ce modèle champion estime 41,7 % pour Team A.",
                ["prediction.home_probability", "identity.home_team", "prediction.model_status"],
            )
        )
    )
    explanation = provider.generate_analysis(context)
    assert provider.last_fallback_reason == "AnalystGroundingError"
    assert explanation.confidence.level != "high"
    assert explanation.data_quality.model_status == "candidate"


def test_mock_data_mode_stays_identifiable() -> None:
    context = _context()
    explanation = LLMAnalystProvider(MockExplainerClient()).generate_analysis(context)
    assert explanation.data_quality.data_mode == "mock"
    assert "mock" in explanation.summary.casefold()
    live_attempt = _scripted(
        json.dumps(
            {
                "data_mode": "live",
                "statements": [{"statement": "Live payload.", "evidence_ids": []}],
            }
        )
    )
    fallback = live_attempt.generate_analysis(context)
    assert live_attempt.last_fallback_reason == "AnalystLLMResponseError"
    assert fallback.data_quality.data_mode == "mock"
    assert fallback.provider == ANALYST_PROVIDER_ID


def test_llm_failure_falls_back_to_deterministic() -> None:
    context = _context()
    provider = _scripted(AnalystLLMError("provider unavailable"))
    explanation = provider.generate_analysis(context)
    expected = DeterministicAnalystProvider().generate_analysis(context)
    assert provider.last_fallback_reason == "AnalystLLMError"
    assert explanation.summary == expected.summary
    assert explanation.provider == ANALYST_PROVIDER_ID


def test_malformed_llm_response_falls_back() -> None:
    provider = _scripted("{not-json")
    explanation = provider.generate_analysis(_context())
    assert provider.last_fallback_reason == "AnalystLLMResponseError"
    assert explanation.provider == ANALYST_PROVIDER_ID


def test_llm_timeout_falls_back() -> None:
    provider = _scripted(_valid_home_statement(), delay_seconds=1.0)
    explanation = provider.generate_analysis(_context())
    assert provider.last_fallback_reason == "AnalystLLMTimeoutError"
    assert explanation.provider == ANALYST_PROVIDER_ID


def test_fallback_deterministic_matches_pure_provider() -> None:
    context = _context()
    provider = _scripted(_statements(("odds = 9.99", ["value.odds"])))
    explanation = provider.generate_analysis(context)
    deterministic = DeterministicAnalystProvider().generate_analysis(context)
    assert explanation.summary == deterministic.summary
    assert explanation.key_factors == deterministic.key_factors
    assert explanation.confidence == deterministic.confidence


def test_llm_cannot_define_or_mutate_business_fields() -> None:
    extras = {field: 0.99 for field in sorted(FORBIDDEN_LLM_FIELDS)}
    extras["statements"] = [{"statement": "Le modèle estime 41,7 %.", "evidence_ids": []}]
    provider = _scripted(json.dumps(extras))
    service = FootballAnalystService(
        clock=Clock(NOW),
        identities=StaticIdentities(_identity(home="Team A", away="Team B")),
        predictions=StaticPredictionService(),
        values=StaticValueService(_analysis()),
        provider=provider,
    )
    report = service.explain(MATCH_ID, CUTOFF)
    assert provider.last_fallback_reason == "AnalystLLMResponseError"
    assert report.prediction.home_probability == 0.612
    assert report.prediction.model_version == "football-elo-v1-candidate"
    assert report.prediction.dataset_version == "football-1x2-history-0.3"
    assert report.prediction.cutoff_at == CUTOFF
    assert report.analyst.data_quality.data_mode == "mock"
    assert report.value.ev == pytest.approx(0.224)
    assert not hasattr(provider, "_predictions")
    assert not hasattr(provider, "_values")


def test_prompt_exposes_only_whitelisted_facts() -> None:
    context = _context()
    prompt = build_narration_prompt(context, prompt_version="analyst-prompt-0.1")
    assert "You are not a source of truth." in prompt
    assert "Do not compute" in prompt
    assert "1 / odds" not in prompt
    assert "calibrated_probability * decimal_odds" not in prompt
    assert "data_mode=mock" in prompt
    assert "model_favorite=HOME" in prompt
    assert "value_selection=AWAY" in prompt
    client = ScriptedLLMClient(_valid_home_statement())
    LLMAnalystProvider(client).generate_analysis(context)
    assert client.prompts
    assert "football-elo-v1-candidate" in client.prompts[0]


def test_factory_keeps_deterministic_default() -> None:
    settings = ApiSettings(
        env="test",
        analyst_narrator="deterministic",
        analyst_llm_model=MOCK_EXPLAINER_MODEL,
    )
    provider = build_analyst_provider(settings)
    assert isinstance(provider, DeterministicAnalystProvider)
    assert isinstance(build_llm_client(settings), MockExplainerClient)
    llm_settings = settings.model_copy(update={"analyst_narrator": "llm"})
    assert isinstance(build_analyst_provider(llm_settings), LLMAnalystProvider)
