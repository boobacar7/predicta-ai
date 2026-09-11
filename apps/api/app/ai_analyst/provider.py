from __future__ import annotations

from typing import Protocol

from app.ai_analyst.context import AnalystContext
from app.ai_analyst.models import FootballAnalystExplanation


class AnalystProvider(Protocol):
    """Downstream explanation port.

    Implementations receive only AnalystContext. LLM output is never a source
    of truth: probabilities, odds, edge, EV, versions, cutoff and data_mode
    stay owned by the service. A provider may narrate context.evidence() and
    must fail rather than invent a missing fact.
    """

    def generate_analysis(self, context: AnalystContext) -> FootballAnalystExplanation: ...
