from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

AI_PICKS_VERSION = "ai-picks-0.1"


class AiPicksThresholds(BaseModel):
    """Single source of truth for V0.1 eligibility thresholds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum_edge: Decimal = Field(default=Decimal("0"), ge=Decimal("-1"), lt=Decimal("1"))
    minimum_ev: Decimal = Field(default=Decimal("0"), ge=Decimal("-1"))
    minimum_model_probability: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), lt=Decimal("1"))
    maximum_odds_age: timedelta = Field(default=timedelta(hours=24), gt=timedelta(0))
