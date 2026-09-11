from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ClaimKind = Literal["probability", "odds", "edge", "ev", "team", "league", "version", "percent"]
ClaimType = Literal[
    "team",
    "league",
    "kickoff",
    "model_probability",
    "odds",
    "implied_probability",
    "no_vig_probability",
    "edge",
    "ev",
    "model_favorite",
    "value_selection",
    "data_mode",
    "statistic",
    "injury",
    "lineup",
    "result",
    "event",
    "recommendation",
]


@dataclass(frozen=True, slots=True)
class FactualClaim:
    kind: ClaimKind
    value: str | float
    source_field: str


@dataclass(frozen=True, slots=True)
class GroundedClaim:
    """Internal factual assertion extracted from narrative. Never serialized to HTTP."""

    claim_type: ClaimType
    subject: str | None
    value: str | float | None
    evidence_ids: tuple[str, ...] = ()


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
