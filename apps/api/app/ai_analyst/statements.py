from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ClaimKind = Literal["probability", "odds", "edge", "ev", "team", "league", "version", "percent"]
ClaimType = Literal[
    "team",
    "league",
    "kickoff",
    "model_probability",
    "probability_comparison",
    "model_favorite",
    "odds",
    "implied_probability",
    "no_vig_probability",
    "edge",
    "ev",
    "value_selection",
    "value_comparison",
    "data_mode",
    "model_status",
    "statistic",
    "injury",
    "lineup",
    "result",
    "event",
    "ranking",
    "recommendation",
]
ClaimRelation = Literal["greater_than", "less_than", "equal", "greater_or_equal", "less_or_equal"]


@dataclass(frozen=True, slots=True)
class FactualClaim:
    kind: ClaimKind
    value: str | float
    source_field: str


@dataclass(frozen=True, slots=True)
class GroundedClaim:
    """Internal factual assertion. Never serialized to HTTP. Never taken from prose."""

    claim_type: ClaimType
    subject: str | None = None
    value: str | float | bool | None = None
    compare_to: str | float | None = None
    relation: ClaimRelation | None = None
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GroundedNarrative:
    """LLM payload after schema parse. Claims are the only factual channel."""

    narrative: str
    claims: tuple[GroundedClaim, ...]


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
