from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai_analyst.context import AnalystContext, AnalystEvidence
from app.ai_analyst.deterministic import DeterministicAnalystProvider
from app.ai_analyst.grounding import (
    EDGE_RE,
    EV_RE,
    ODDS_RE,
    PERCENT_RE,
    AnalystGroundingError,
    assert_statements_grounded,
)
from app.ai_analyst.llm_client import (
    ANALYST_LLM_TEMPERATURE,
    AnalystLLMClient,
    AnalystLLMResponseError,
)
from app.ai_analyst.models import LLM_ANALYST_PROVIDER_ID, FootballAnalystExplanation
from app.ai_analyst.statements import ClaimKind, FactualClaim, GroundedStatement, render_statements
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
PERCENT_FIELDS = frozenset(
    {
        "home_probability",
        "draw_probability",
        "away_probability",
        "implied_probability",
        "no_vig_probability",
    }
)
CLAIM_KIND_BY_FIELD: dict[str, ClaimKind] = {
    "home_probability": "probability",
    "draw_probability": "probability",
    "away_probability": "probability",
    "implied_probability": "probability",
    "no_vig_probability": "probability",
    "odds": "odds",
    "edge": "edge",
    "ev": "ev",
    "home_team": "team",
    "away_team": "team",
    "league": "league",
    "model_version": "version",
    "dataset_version": "version",
    "value_engine_version": "version",
}


class LLMStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1)
    evidence_ids: list[str]


class LLMNarration(BaseModel):
    """The only payload an LLM may return. Business fields are reconstructed later."""

    model_config = ConfigDict(extra="forbid")

    statements: list[LLMStatement] = Field(min_length=1)


def build_narration_prompt(context: AnalystContext, *, prompt_version: str) -> str:
    facts = [
        {
            "evidence_id": item.evidence_id,
            "category": item.category,
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
        "Use cautious language: 'le modèle estime', 'la probabilité modélisée', "
        "'la valeur théorique détectée', 'cet indicateur suggère'.\n"
        "Forbidden: garantie, certitude, gain garanti, pari sûr, ce pari va gagner, "
        "bookmaker phrasing, injuries, lineups, invented statistics or results.\n"
        f"data_mode={context.data_mode}. If mock, the narration must remain identifiable as mock.\n"
        f"model_favorite={favorite}. value_selection={value_selection}.\n"
        "Never present value_selection as the model favorite when they differ.\n"
        "Return JSON only: {\"statements\":[{\"statement\":\"...\",\"evidence_ids\":[\"...\"]}]}\n"
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


def grounded_statements_from_narration(
    context: AnalystContext,
    narration: LLMNarration,
) -> tuple[GroundedStatement, ...]:
    evidence = context.evidence()
    ids = {item.evidence_id: item for item in evidence}
    statements: list[GroundedStatement] = []
    for item in narration.statements:
        unknown = [evidence_id for evidence_id in item.evidence_ids if evidence_id not in ids]
        if unknown:
            raise AnalystGroundingError(f"GroundedStatement referenced an unknown evidence_id: {unknown[0]}.")
        _assert_cited_facts_match(item.statement, tuple(item.evidence_ids), ids)
        statements.append(
            GroundedStatement(
                statement=item.statement,
                evidence_ids=tuple(item.evidence_ids),
                factual_claims=_claims_from_statement(item.statement, tuple(item.evidence_ids), ids),
            )
        )
    return tuple(statements)


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
            statements = self._narrate(context)
            assert_statements_grounded(context, statements)
            assembled = self._fallback.assemble(context)
            return assembled.model_copy(
                update={
                    "summary": render_statements(statements),
                    "provider": LLM_ANALYST_PROVIDER_ID,
                }
            )
        except ApiError:
            raise
        except Exception as exc:
            self.last_fallback_reason = type(exc).__name__
            try:
                return self._fallback.generate_analysis(context)
            except AnalystGroundingError:
                return self._fallback.assemble(context)

    def _narrate(self, context: AnalystContext) -> tuple[GroundedStatement, ...]:
        prompt = build_narration_prompt(context, prompt_version=self._prompt_version)
        raw = self._client.narrate(context, prompt, timeout_seconds=self._timeout_seconds)
        narration = parse_llm_narration(raw)
        return grounded_statements_from_narration(context, narration)


def _unwrap_fence(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text
    text = re.sub(r"^```(?:json)?\s*", "", text)
    return re.sub(r"\s*```$", "", text)


def _claims_from_statement(
    statement: str,
    evidence_ids: tuple[str, ...],
    evidence: dict[str, AnalystEvidence],
) -> tuple[FactualClaim, ...]:
    claims: list[FactualClaim] = []
    for evidence_id in evidence_ids:
        item = evidence[evidence_id]
        if item.availability != "available" or item.value is None:
            continue
        kind = CLAIM_KIND_BY_FIELD.get(item.source_field)
        if kind is None:
            continue
        if not _value_appears(statement, item):
            continue
        claims.append(FactualClaim(kind, item.value, item.source_field))
    return tuple(claims)


def _assert_cited_facts_match(
    statement: str,
    evidence_ids: tuple[str, ...],
    evidence: dict[str, AnalystEvidence],
) -> None:
    percents = {_to_decimal(raw) for raw in PERCENT_RE.findall(statement)}
    odds = {_quantize(_to_decimal(raw)) for raw in ODDS_RE.findall(statement)}
    signed = {_quantize(_to_decimal(raw)) for raw in (*EV_RE.findall(statement), *EDGE_RE.findall(statement))}
    for evidence_id in evidence_ids:
        item = evidence[evidence_id]
        if item.availability != "available" or item.value is None:
            continue
        if item.source_field in PERCENT_FIELDS and percents:
            expected = (Decimal(str(item.value)) * Decimal(100)).quantize(Decimal("0.1"))
            if expected not in percents and abs(expected) not in percents:
                raise AnalystGroundingError(
                    f"Cited {item.source_field} does not match the percent asserted in the statement."
                )
        if item.source_field == "odds" and odds:
            if _quantize(Decimal(str(item.value))) not in odds:
                raise AnalystGroundingError("Cited odds do not match the odds asserted in the statement.")
        if item.source_field in {"edge", "ev"} and signed:
            points = (Decimal(str(item.value)) * Decimal(100)).quantize(Decimal("0.1"))
            raw = _quantize(Decimal(str(item.value)))
            if points not in signed and raw not in signed and abs(points) not in signed:
                raise AnalystGroundingError(
                    f"Cited {item.source_field} does not match the signed metric asserted in the statement."
                )
        if item.source_field in {"home_team", "away_team"} and isinstance(item.value, str):
            others = [
                candidate.value
                for candidate in evidence.values()
                if candidate.source_field in {"home_team", "away_team"}
                and candidate.availability == "available"
                and isinstance(candidate.value, str)
                and candidate.value.casefold() != item.value.casefold()
            ]
            if item.value.casefold() not in statement.casefold() and any(
                other.casefold() in statement.casefold() for other in others
            ):
                raise AnalystGroundingError("Cited team evidence does not match the team named in the statement.")


def _to_decimal(raw: str) -> Decimal:
    return Decimal(raw.replace(",", ".").replace("+", ""))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"))


def _value_appears(statement: str, item: AnalystEvidence) -> bool:
    if item.value is None:
        return False
    if item.source_field in PERCENT_FIELDS and isinstance(item.value, int | float):
        expected = (Decimal(str(item.value)) * Decimal(100)).quantize(Decimal("0.1"))
        return expected in {_to_decimal(raw) for raw in PERCENT_RE.findall(statement)}
    if item.source_field == "odds" and isinstance(item.value, int | float):
        return _quantize(Decimal(str(item.value))) in {
            _quantize(_to_decimal(raw)) for raw in ODDS_RE.findall(statement)
        }
    if item.source_field in {"edge", "ev"} and isinstance(item.value, int | float):
        points = (Decimal(str(item.value)) * Decimal(100)).quantize(Decimal("0.1"))
        signed = {_quantize(_to_decimal(raw)) for raw in (*EV_RE.findall(statement), *EDGE_RE.findall(statement))}
        return points in signed or _quantize(Decimal(str(item.value))) in signed
    return str(item.value).casefold() in statement.casefold()
