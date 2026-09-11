from __future__ import annotations

import json
from typing import Protocol

from app.ai_analyst.context import AnalystContext
from app.ai_analyst.deterministic import DeterministicAnalystProvider

MOCK_EXPLAINER_MODEL = "mock-explainer-0.1"
ANALYST_LLM_TEMPERATURE = 0


class AnalystLLMError(RuntimeError):
    """LLM narrator failed. The provider must fall back to deterministic text."""


class AnalystLLMTimeoutError(AnalystLLMError):
    """The narrator exceeded the configured timeout."""


class AnalystLLMResponseError(AnalystLLMError):
    """The narrator returned an unusable payload."""


class AnalystLLMClient(Protocol):
    """Downstream narrator only. It must not compute probabilities, odds, edge or EV."""

    def narrate(self, context: AnalystContext, prompt: str, *, timeout_seconds: float) -> str: ...


class MockExplainerClient:
    """Deterministic stand-in that speaks the LLM JSON schema from AnalystContext."""

    model = MOCK_EXPLAINER_MODEL

    def narrate(self, context: AnalystContext, prompt: str, *, timeout_seconds: float) -> str:
        del prompt, timeout_seconds
        statements = [
            {"statement": item.statement, "evidence_ids": list(item.evidence_ids)}
            for item in DeterministicAnalystProvider().grounded_summary(context)
        ]
        if context.data_mode == "mock":
            statements.append(
                {
                    "statement": (
                        "Ces faits sont servis en data_mode mock et ne doivent pas être présentés comme live."
                    ),
                    "evidence_ids": ["metadata.data_mode"],
                }
            )
        if context.prediction.model_status == "candidate":
            statements.append(
                {
                    "statement": (
                        f"Le modèle {context.prediction.model_version} a le statut candidate, "
                        "pas un statut de production promu."
                    ),
                    "evidence_ids": ["prediction.model_status", "prediction.model_version"],
                }
            )
        return json.dumps({"statements": statements}, ensure_ascii=False)


class ScriptedLLMClient:
    """Test double: returns a canned payload, raises, or times out."""

    def __init__(
        self,
        payload: str | Exception,
        *,
        delay_seconds: float = 0,
    ) -> None:
        self.payload = payload
        self.delay_seconds = delay_seconds
        self.prompts: list[str] = []

    def narrate(self, context: AnalystContext, prompt: str, *, timeout_seconds: float) -> str:
        del context
        self.prompts.append(prompt)
        if self.delay_seconds > timeout_seconds:
            raise AnalystLLMTimeoutError("LLM narrator timed out.")
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload
