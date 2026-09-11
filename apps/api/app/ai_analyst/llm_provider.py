from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.ai_analyst.claims import ClaimGroundingError, render_grounded_narrative, validate_narrative_and_claims
from app.ai_analyst.context import AnalystContext
from app.ai_analyst.deterministic import DeterministicAnalystProvider
from app.ai_analyst.grounding import AnalystGroundingError, assert_grounded
from app.ai_analyst.llm_client import (
    ANALYST_LLM_TEMPERATURE,
    AnalystLLMClient,
    AnalystLLMResponseError,
)
from app.ai_analyst.models import LLM_ANALYST_PROVIDER_ID, FootballAnalystExplanation
from app.ai_analyst.statements import ClaimRelation, ClaimType, GroundedClaim, GroundedNarrative
from app.core.errors import ApiError

FORBIDDEN_LLM_FIELDS = frozenset(
    {
        "probabilities",
        "probability",
        "home_probability",
        "draw_probability",
        "away_probability",
        "odds",
        "edge",
        "ev",
        "expected_value",
        "model_version",
        "dataset_version",
        "cutoff_at",
        "data_mode",
        "value_engine_version",
        "model_favorite",
        "value_selection",
    }
)


class LLMClaim(BaseModel):
    """Structured fact. The backend compares this to AnalystContext; prose cannot substitute."""

    model_config = ConfigDict(extra="forbid")

    claim_type: ClaimType
    subject: str | None = None
    value: str | float | bool | None = None
    compare_to: str | float | None = None
    relation: ClaimRelation | None = None
    evidence_ids: list[str] = Field(min_length=1)


class LLMNarration(BaseModel):
    """The only payload an LLM may return. Business fields are reconstructed later."""

    model_config = ConfigDict(extra="forbid")

    narrative: str = ""
    claims: list[LLMClaim] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_narrative_or_claims(self) -> LLMNarration:
        if not self.narrative.strip() and not self.claims:
            raise ValueError("LLM narrator returned neither narrative nor claims.")
        return self


def build_narration_prompt(context: AnalystContext, *, prompt_version: str) -> str:
    facts = [
        {
            "evidence_id": item.evidence_id,
            "category": item.category,
            "evidence_type": item.evidence_type,
            "source_field": item.source_field,
            "value": item.value,
            "availability": item.availability,
            "source": item.source,
        }
        for item in context.evidence()
    ]
    favorite = context.favorite_selection().value
    value_selection = context.value_selection.value if context.value_selection is not None else None
    return (
        f"prompt_version={prompt_version}\n"
        f"temperature={ANALYST_LLM_TEMPERATURE}\n"
        "You are a sports-analytics narrator. You are not a source of truth.\n"
        "Do not compute probabilities, odds, edge, EV, versions, cutoff or data_mode.\n"
        "Use only the validated facts below. If a fact is unavailable, say it is unavailable.\n"
        "Put every factual assertion in claims. Narrative prose must stay stylistic: "
        "no digits, no HOME/AWAY/DRAW labels, no team or league names.\n"
        "Each claim must include claim_type, subject, value or comparison, and evidence_ids.\n"
        "The backend validates claims against AnalystContext. Unvalidated prose is discarded.\n"
        f"data_mode={context.data_mode}. If mock, a data_mode claim must stay mock.\n"
        f"model_favorite={favorite}. value_selection={value_selection}.\n"
        "Never present value_selection as the model favorite when they differ.\n"
        "Return JSON only: "
        '{"narrative":"...","claims":[{"claim_type":"...","subject":"HOME",'
        '"value":0.417,"evidence_ids":["prediction.home_probability"]}]}\n'
        "facts="
        + json.dumps(facts, ensure_ascii=False, default=str)
    )


def parse_llm_narration(raw: str) -> LLMNarration:
    text = _unwrap_fence(raw)
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AnalystLLMResponseError("LLM narrator returned malformed JSON.") from exc
    if not isinstance(payload, dict):
        raise AnalystLLMResponseError("LLM narrator returned a non-object payload.")
    extras = FORBIDDEN_LLM_FIELDS.intersection(payload)
    if extras:
        raise AnalystLLMResponseError(
            "LLM narrator attempted to define business fields: " + ", ".join(sorted(extras)) + "."
        )
    try:
        return LLMNarration.model_validate(payload)
    except ValidationError as exc:
        raise AnalystLLMResponseError("LLM narrator returned an invalid schema.") from exc


def grounded_narrative_from_llm(narration: LLMNarration) -> GroundedNarrative:
    claims = tuple(
        GroundedClaim(
            claim_type=item.claim_type,
            subject=item.subject,
            value=item.value,
            compare_to=item.compare_to,
            relation=item.relation,
            evidence_ids=tuple(item.evidence_ids),
        )
        for item in narration.claims
    )
    return GroundedNarrative(narrative=narration.narrative, claims=claims)


class LLMAnalystProvider:
    """Narrator behind AnalystProvider. LLM output never owns business fields."""

    def __init__(
        self,
        client: AnalystLLMClient,
        *,
        fallback: DeterministicAnalystProvider | None = None,
        timeout_seconds: float = 2.0,
        prompt_version: str = "analyst-prompt-0.1",
    ) -> None:
        self._client = client
        self._fallback = fallback or DeterministicAnalystProvider()
        self._timeout_seconds = timeout_seconds
        self._prompt_version = prompt_version
        self.last_fallback_reason: str | None = None

    def generate_analysis(self, context: AnalystContext) -> FootballAnalystExplanation:
        self.last_fallback_reason = None
        try:
            summary = self._narrate(context)
            assembled = self._fallback.assemble(context)
            explanation = assembled.model_copy(
                update={
                    "summary": summary,
                    "provider": LLM_ANALYST_PROVIDER_ID,
                }
            )
            assert_grounded(context, explanation)
            return explanation
        except ApiError:
            raise
        except Exception as exc:
            self.last_fallback_reason = type(exc).__name__
            try:
                return self._fallback.generate_analysis(context)
            except AnalystGroundingError:
                return self._fallback.assemble(context)

    def _narrate(self, context: AnalystContext) -> str:
        prompt = build_narration_prompt(context, prompt_version=self._prompt_version)
        raw = self._client.narrate(context, prompt, timeout_seconds=self._timeout_seconds)
        narration = parse_llm_narration(raw)
        grounded = grounded_narrative_from_llm(narration)
        try:
            validate_narrative_and_claims(context, grounded)
        except ClaimGroundingError as exc:
            raise AnalystGroundingError(str(exc)) from exc
        return render_grounded_narrative(context, grounded)


def _unwrap_fence(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text
    text = re.sub(r"^```(?:json)?\s*", "", text)
    return re.sub(r"\s*```$", "", text)
