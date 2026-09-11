from __future__ import annotations

from app.ai_analyst.context import AnalystContext
from app.ai_analyst.deterministic import FORBIDDEN_CLAIMS
from app.ai_analyst.models import FootballAnalystExplanation

VALUE_ONLY_FACTORS = frozenset({"market_probability", "edge", "ev", "data_freshness"})


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
        lowered = text.casefold()
        for term in FORBIDDEN_CLAIMS:
            if term in lowered:
                raise AnalystGroundingError(f"Analyst text contains forbidden language: {term}.")
        if context.value is None:
            for claim in ("edge", "espérance", "implicite brute"):
                if claim in lowered and "aucune" not in lowered and "n'est affirmée" not in lowered:
                    raise AnalystGroundingError("Unavailable value facts were asserted.")
