from __future__ import annotations

import json
from typing import Protocol

from app.ai_analyst.context import AnalystContext

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
        return json.dumps(
            {
                "narrative": "The match appears open.",
                "claims": _claims_from_context(context),
            },
            ensure_ascii=False,
        )


def _claims_from_context(context: AnalystContext) -> list[dict[str, object]]:
    favorite = context.favorite_selection()
    field = {
        "HOME": "prediction.home_probability",
        "DRAW": "prediction.draw_probability",
        "AWAY": "prediction.away_probability",
    }[favorite.value]
    claims: list[dict[str, object]] = [
        {
            "claim_type": "model_probability",
            "subject": favorite.value,
            "value": float(context.prediction.probability(favorite)),
            "evidence_ids": [field],
        },
        {
            "claim_type": "model_favorite",
            "subject": favorite.value,
            "evidence_ids": ["prediction.model_favorite"],
        },
        {
            "claim_type": "data_mode",
            "value": context.data_mode,
            "evidence_ids": ["metadata.data_mode"],
        },
        {
            "claim_type": "model_status",
            "value": context.prediction.model_status,
            "evidence_ids": ["prediction.model_status"],
        },
    ]
    if context.value is not None:
        claims.extend(
            [
                {
                    "claim_type": "implied_probability",
                    "subject": context.value.selection.value,
                    "value": float(context.value.implied_probability),
                    "evidence_ids": ["value.implied_probability"],
                },
                {
                    "claim_type": "odds",
                    "subject": context.value.selection.value,
                    "value": float(context.value.odds),
                    "evidence_ids": ["value.odds"],
                },
                {
                    "claim_type": "edge",
                    "subject": context.value.selection.value,
                    "value": float(context.value.edge),
                    "evidence_ids": ["value.edge"],
                },
                {
                    "claim_type": "ev",
                    "subject": context.value.selection.value,
                    "value": float(context.value.ev),
                    "evidence_ids": ["value.ev"],
                },
            ]
        )
        if context.value_selection is not None:
            claims.append(
                {
                    "claim_type": "value_selection",
                    "subject": context.value_selection.value,
                    "evidence_ids": ["value.value_selection"],
                }
            )
    return claims


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
