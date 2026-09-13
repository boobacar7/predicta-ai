from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.ai_analyst.claims import ClaimGroundingError, validate_claims
from app.ai_analyst.context import AnalystContext
from app.ai_analyst.deterministic import DeterministicAnalystProvider
from app.ai_analyst.grounding import AnalystGroundingError, assert_grounded
from app.ai_analyst.llm_client import (
    ANALYST_LLM_TEMPERATURE,
    AnalystLLMClient,
    AnalystLLMResponseError,
)
from app.ai_analyst.models import LLM_ANALYST_PROVIDER_ID, FootballAnalystExplanation
from app.ai_analyst.rendering import render_analyst_summary
from app.ai_analyst.statements import (
    AnalystFocus,
    AnalystTone,
    AnalystVerbosity,
    ClaimRelation,
    ClaimType,
    GroundedClaim,
    StylePayload,
)
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
        "summary",
        "factors",
        "strengths",
        "risks",
        "confidence",
        "commentary",
        "explanation",
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


class LLMStyle(BaseModel):
    """Closed enums only. Free-text style is rejected by schema."""

    model_config = ConfigDict(extra="forbid")

    tone: AnalystTone = "neutral"
    verbosity: AnalystVerbosity = "short"
    focus: AnalystFocus = "prediction"


class LLMNarration(BaseModel):
    """The only payload an LLM may return. Business fields are reconstructed later."""

    model_config = ConfigDict(extra="forbid")

    style: LLMStyle = Field(default_factory=LLMStyle)
    claims: list[LLMClaim] = Field(default_factory=list)
    narrative: str = Field(
        default="",
        description="UNTRUSTED LLM TEXT — NEVER RENDER DIRECTLY.",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_empty_object(cls, data: Any) -> Any:
        if not isinstance(data, dict) or not data:
            raise ValueError("LLM narrator returned an empty payload.")
        return data


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
        "Do not write factual sentences. The backend renders every published fact.\n"
        "Return JSON only with style enums and structured claims.\n"
        "style.tone must be one of: neutral, analytical, concise.\n"
        "style.verbosity must be one of: short, medium.\n"
        "style.focus must be one of: prediction, value, data_quality.\n"
        "Each claim must include claim_type, subject, value or comparison, and evidence_ids.\n"
        "The backend validates claims against AnalystContext. Any narrative field is discarded.\n"
        f"data_mode={context.data_mode}. If mock, a data_mode claim must stay mock.\n"
        f"model_favorite={favorite}. value_selection={value_selection}.\n"
        "Never present value_selection as the model favorite when they differ.\n"
        "Return JSON only: "
        '{"style":{"tone":"neutral","verbosity":"short","focus":"prediction"},'
        '"claims":[{"claim_type":"model_favorite","subject":"HOME",'
        '"evidence_ids":["prediction.model_favorite"]}]}\n'
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
    if isinstance(payload.get("style"), str):
        raise AnalystLLMResponseError("LLM narrator returned free-text style.")
    try:
        return LLMNarration.model_validate(payload)
    except ValidationError as exc:
        raise AnalystLLMResponseError("LLM narrator returned an invalid schema.") from exc


def style_from_llm(narration: LLMNarration) -> StylePayload:
    return StylePayload(
        tone=narration.style.tone,
        verbosity=narration.style.verbosity,
        focus=narration.style.focus,
    )


def claims_from_llm(narration: LLMNarration) -> tuple[GroundedClaim, ...]:
    return tuple(
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


class LLMAnalystProvider:
    """Narrator behind AnalystProvider. LLM output never owns business fields."""

    def __init__(
        self,
        client: AnalystLLMClient,
        *,
        fallback: DeterministicAnalystProvider | None = None,
        timeout_seconds: float = 2.0,
        prompt_version: str = "analyst-prompt-0.2",
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
        # UNTRUSTED LLM TEXT — NEVER RENDER DIRECTLY.
        _ = narration.narrative
        claims = claims_from_llm(narration)
        try:
            validated = validate_claims(context, claims)
        except ClaimGroundingError as exc:
            raise AnalystGroundingError(str(exc)) from exc
        return render_analyst_summary(context, validated, style_from_llm(narration))


def _unwrap_fence(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text
    text = re.sub(r"^```(?:json)?\s*", "", text)
    return re.sub(r"\s*```$", "", text)
