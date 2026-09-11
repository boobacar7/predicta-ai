from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ClaimKind = Literal["probability", "odds", "edge", "ev", "team", "league", "version", "percent"]


@dataclass(frozen=True, slots=True)
class FactualClaim:
    kind: ClaimKind
    value: str | float
    source_field: str


@dataclass(frozen=True, slots=True)
class GroundedStatement:
    """One narrative sentence bound to AnalystEvidence.

    The statement text is interpretation. factual_claims are the only numbers
    and entities it may assert. LLM output is never a source of truth.
    """

    statement: str
    evidence_ids: tuple[str, ...]
    factual_claims: tuple[FactualClaim, ...]


def render_statements(statements: tuple[GroundedStatement, ...]) -> str:
    return " ".join(item.statement for item in statements)
