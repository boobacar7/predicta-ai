from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from predicta_ml.oos.dataset import OosMatch
from predicta_ml.oos.errors import OosLeakageError, OosProtocolError


@dataclass(frozen=True)
class MatchOutcome:
    match_id: str
    outcome: str
    observed_at: datetime


def outcome_for_evaluation(match: OosMatch, *, now: datetime) -> MatchOutcome:
    """Outcomes are evaluation-only. They must never enter prediction features."""

    clock = now.astimezone(UTC)
    if clock < match.kickoff_at:
        raise OosLeakageError(
            f"Outcome for {match.match_id} was requested before kickoff {match.kickoff_at.isoformat()}."
        )
    if match.outcome not in {"HOME", "DRAW", "AWAY"}:
        raise OosProtocolError(f"Finished OOS match {match.match_id} has no 1X2 outcome.")
    return MatchOutcome(match_id=match.match_id, outcome=match.outcome, observed_at=clock)


def labels(matches: tuple[OosMatch, ...]) -> list[int]:
    return [item.y for item in matches]
