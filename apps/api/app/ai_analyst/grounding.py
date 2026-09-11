from __future__ import annotations

import re
from decimal import Decimal

from app.ai_analyst.context import AnalystContext, AnalystEvidence
from app.ai_analyst.language import FORBIDDEN_CLAIMS
from app.ai_analyst.models import FootballAnalystExplanation
from app.ai_analyst.statements import FactualClaim, GroundedStatement

VALUE_ONLY_FACTORS = frozenset({"market_probability", "edge", "ev", "data_freshness"})
PERCENT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
ODDS_RE = re.compile(r"(?:odds|cote)\s*(?:=|de|:)?\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
EV_RE = re.compile(r"(?:\bev\b|espérance(?: théorique)?)\s*(?:=|de|:)?\s*([+-]?\d+(?:[.,]\d+)?)", re.IGNORECASE)
EDGE_RE = re.compile(r"\bedge\b\s*(?:=|de|:)?\s*([+-]?\d+(?:[.,]\d+)?)", re.IGNORECASE)
POINTS_RE = re.compile(r"([+-]\d+(?:[.,]\d+)?)\s*points", re.IGNORECASE)
TEAM_TOKEN_RE = re.compile(r"\bTeam\s+[A-Z0-9]+\b")
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?")
NAME_TOKEN = r"(?:St\.\s+)?[A-Z][A-Za-zÀ-ÿ']+"
PROPER_NAME_RE = re.compile(
    rf"\b({NAME_TOKEN}(?:\s+(?:d'|de |del |l'|la |le )?{NAME_TOKEN})+)\b"
)
NARRATIVE_PROPER_NAMES = frozenset({"value engine"})


class AnalystGroundingError(ValueError):
    """Provider output referenced a fact that is not in AnalystContext."""


def assert_grounded(context: AnalystContext, explanation: FootballAnalystExplanation) -> None:
    """Refuse narrative that invents facts. Numeric DTOs stay owned by the service."""

    evidence = context.evidence()
    allowed_numbers = {
        item.value
        for item in evidence
        if item.availability == "available" and isinstance(item.value, int | float)
    }
    allowed_sources = {item.source for item in evidence if item.availability == "available"}
    for factor in explanation.key_factors:
        if factor.source not in allowed_sources:
            raise AnalystGroundingError(f"Factor source '{factor.source}' is outside AnalystContext.")
        if factor.type in VALUE_ONLY_FACTORS and context.value is None:
            raise AnalystGroundingError(f"Factor '{factor.type}' is unavailable in AnalystContext.")
        if factor.value is not None:
            grounded = any(abs(float(factor.value) - float(item)) < 1e-9 for item in allowed_numbers)
            if not grounded:
                raise AnalystGroundingError(f"Factor value {factor.value} is not present in AnalystContext.")
    texts = (
        explanation.summary,
        explanation.confidence.basis,
        *explanation.strengths,
        *explanation.risks,
    )
    for text in texts:
        _assert_text_grounded(context, text)


def assert_statements_grounded(context: AnalystContext, statements: tuple[GroundedStatement, ...]) -> None:
    """Refuse structured claims that are not present on AnalystEvidence."""

    evidence = context.evidence()
    ids = {item.evidence_id for item in evidence}
    fields = {item.source_field: item for item in evidence}
    for statement in statements:
        if any(evidence_id not in ids for evidence_id in statement.evidence_ids):
            raise AnalystGroundingError("GroundedStatement referenced an unknown evidence_id.")
        for claim in statement.factual_claims:
            _assert_claim_grounded(fields, claim)
        _assert_text_grounded(context, statement.statement)


def _assert_claim_grounded(fields: dict[str, AnalystEvidence], claim: FactualClaim) -> None:
    item = fields.get(claim.source_field)
    if item is None or item.availability != "available":
        raise AnalystGroundingError(
            f"FactualClaim {claim.kind}={claim.value} is not available in AnalystContext."
        )
    if not _values_match(item.value, claim.value):
        raise AnalystGroundingError(
            f"FactualClaim {claim.kind}={claim.value} does not match AnalystEvidence."
        )


def _assert_text_grounded(context: AnalystContext, text: str) -> None:
    forbidden = _forbidden_term(text)
    if forbidden is not None:
        raise AnalystGroundingError(f"Analyst text contains forbidden language: {forbidden}.")
    allowed_percents = _allowed_percents(context)
    for raw in PERCENT_RE.findall(text):
        if _to_decimal(raw) not in allowed_percents:
            raise AnalystGroundingError(f"Percent claim {raw}% is not present in AnalystContext.")
    if context.value is None:
        if ODDS_RE.search(text):
            raise AnalystGroundingError("Odds were asserted while unavailable in AnalystContext.")
        for claim in ("edge", "espérance", "implicite brute"):
            if claim in text.casefold() and "aucune" not in text.casefold() and "n'est affirmée" not in text.casefold():
                raise AnalystGroundingError("Unavailable value facts were asserted.")
    else:
        allowed_odds = {_quantize(_to_decimal(str(context.value.odds)))}
        for raw in ODDS_RE.findall(text):
            if _quantize(_to_decimal(raw)) not in allowed_odds:
                raise AnalystGroundingError(f"Odds claim {raw} is not present in AnalystContext.")
        allowed_signed = _allowed_signed_metrics(context)
        for raw in (*EV_RE.findall(text), *EDGE_RE.findall(text), *POINTS_RE.findall(text)):
            if _quantize(_to_decimal(raw)) not in allowed_signed:
                raise AnalystGroundingError(f"Signed metric claim {raw} is not present in AnalystContext.")
    allowed_names = _allowed_names(context)
    for token in TEAM_TOKEN_RE.findall(text):
        if token.casefold() not in allowed_names:
            raise AnalystGroundingError(f"Team token '{token}' is not present in AnalystContext.")
    for name in PROPER_NAME_RE.findall(text):
        if name.casefold() in NARRATIVE_PROPER_NAMES:
            continue
        if name.casefold() not in allowed_names:
            raise AnalystGroundingError(f"Entity '{name}' is not present in AnalystContext.")
    allowed_days = _allowed_days(context)
    for raw in ISO_DATE_RE.findall(text):
        if raw[:10] not in allowed_days:
            raise AnalystGroundingError(f"Date '{raw}' is not present in AnalystContext.")


def _forbidden_term(text: str) -> str | None:
    lowered = text.casefold()
    for term in FORBIDDEN_CLAIMS:
        if " " in term or "%" in term:
            if term in lowered:
                return term
            continue
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            return term
    return None


def _allowed_percents(context: AnalystContext) -> set[Decimal]:
    values = [
        context.prediction.home_probability,
        context.prediction.draw_probability,
        context.prediction.away_probability,
    ]
    if context.value is not None:
        values.extend([context.value.implied_probability, context.value.no_vig_probability])
        values.append(abs(context.value.edge))
        values.append(abs(context.value.ev))
    allowed: set[Decimal] = set()
    for value in values:
        percent = (value * Decimal(100)).quantize(Decimal("0.1"))
        allowed.add(percent)
        allowed.add(abs(percent))
    return allowed


def _allowed_signed_metrics(context: AnalystContext) -> set[Decimal]:
    if context.value is None:
        return set()
    allowed = set()
    for value in (context.value.edge, context.value.ev):
        points = (value * Decimal(100)).quantize(Decimal("0.1"))
        allowed.add(points)
        allowed.add(_quantize(value))
    return allowed


def _allowed_names(context: AnalystContext) -> set[str]:
    names = {
        context.identity.league.casefold(),
        context.prediction.model_version.casefold(),
        context.prediction.dataset_version.casefold(),
    }
    if context.identity.home_team:
        names.add(context.identity.home_team.casefold())
    if context.identity.away_team:
        names.add(context.identity.away_team.casefold())
    if context.value is not None:
        names.add(context.value.value_engine_version.casefold())
    return names


def _allowed_days(context: AnalystContext) -> set[str]:
    return {
        context.identity.kickoff_at.date().isoformat(),
        context.prediction.cutoff_at.date().isoformat(),
    }


def _values_match(evidence: str | float | None, claim: str | float) -> bool:
    if evidence is None:
        return False
    if isinstance(evidence, int | float) or isinstance(claim, int | float):
        try:
            return abs(float(evidence) - float(claim)) < 1e-9
        except (TypeError, ValueError):
            return False
    return str(evidence).casefold() == str(claim).casefold()


def _to_decimal(raw: str) -> Decimal:
    return Decimal(raw.replace(",", ".").replace("+", ""))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"))
