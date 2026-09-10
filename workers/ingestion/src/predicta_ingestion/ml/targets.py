from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from predicta_ingestion.canonical.models import Match
from predicta_ingestion.errors import ValidationError


class Football1X2Target(StrEnum):
    HOME = "HOME"
    DRAW = "DRAW"
    AWAY = "AWAY"


def result_1x2(match: Match) -> Football1X2Target:
    if match.home_score is None or match.away_score is None:
        raise ValidationError("missing_score", "Finished matches require scores before a 1X2 target is assigned.")
    if match.home_score > match.away_score:
        return Football1X2Target.HOME
    if match.home_score < match.away_score:
        return Football1X2Target.AWAY
    return Football1X2Target.DRAW


def finished_labeled(matches: Sequence[Match]) -> list[Match]:
    labeled: list[Match] = []
    for match in matches:
        if match.home_score is None or match.away_score is None:
            continue
        labeled.append(match)
    return labeled
