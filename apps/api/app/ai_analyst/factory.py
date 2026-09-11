from __future__ import annotations

from app.ai_analyst.deterministic import DeterministicAnalystProvider
from app.ai_analyst.llm_client import MOCK_EXPLAINER_MODEL, AnalystLLMClient, MockExplainerClient
from app.ai_analyst.llm_provider import LLMAnalystProvider
from app.ai_analyst.provider import AnalystProvider
from app.core.config import Settings


def build_llm_client(settings: Settings) -> AnalystLLMClient:
    if settings.analyst_llm_model == MOCK_EXPLAINER_MODEL:
        return MockExplainerClient()
    raise ValueError(
        f"Unsupported analyst LLM model '{settings.analyst_llm_model}'. "
        f"Only {MOCK_EXPLAINER_MODEL} is implemented; a real vendor client is out of scope."
    )


def build_analyst_provider(settings: Settings) -> AnalystProvider:
    fallback = DeterministicAnalystProvider()
    if settings.analyst_narrator != "llm":
        return fallback
    try:
        client = build_llm_client(settings)
    except ValueError:
        return fallback
    return LLMAnalystProvider(
        client,
        fallback=fallback,
        timeout_seconds=settings.analyst_llm_timeout_seconds,
        prompt_version=settings.analyst_prompt_version,
    )
