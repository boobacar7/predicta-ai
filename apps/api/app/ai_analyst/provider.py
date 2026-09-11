from __future__ import annotations

from typing import Protocol

from app.ai_analyst.context import AnalystContext
from app.ai_analyst.models import FootballAnalystExplanation


class AnalystProvider(Protocol):
    """Downstream explanation port. Implementations must not fetch extra facts."""

    def generate_analysis(self, context: AnalystContext) -> FootballAnalystExplanation: ...
