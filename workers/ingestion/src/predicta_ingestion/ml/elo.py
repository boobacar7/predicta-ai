from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from predicta_ingestion.canonical.enums import MatchStatus
from predicta_ingestion.canonical.models import Match
from predicta_ingestion.clock import ensure_utc

INITIAL_ELO = 1500.0
ELO_K = 20.0
HOME_ADVANTAGE = 80.0


def expected_score(rating: float, opponent: float) -> float:
    return 1.0 / (1.0 + 10 ** ((opponent - rating) / 400.0))


def reconstruct_pre_match_elo(
    matches: Sequence[Match],
    *,
    initial: float = INITIAL_ELO,
    k: float = ELO_K,
    home_advantage: float = HOME_ADVANTAGE,
) -> dict[str, tuple[float, float]]:
    """Walk finished matches in kickoff order and record ratings *before* each result.

    Ratings after match N are never written back onto match N. That would leak the
    outcome into a pre-match feature.
    """
    ordered = [
        item
        for item in matches
        if item.status is MatchStatus.FINISHED
        and item.home_score is not None
        and item.away_score is not None
        and item.home_team_id
        and item.away_team_id
    ]
    ordered.sort(key=lambda item: (ensure_utc(item.kickoff_at), item.id))
    ratings: dict[str, float] = defaultdict(lambda: initial)
    pre_match: dict[str, tuple[float, float]] = {}
    for match in ordered:
        home_id = match.home_team_id or ""
        away_id = match.away_team_id or ""
        home_goals = match.home_score
        away_goals = match.away_score
        if home_goals is None or away_goals is None:
            continue
        pre_match[match.id] = (ratings[home_id], ratings[away_id])
        home_expected = expected_score(ratings[home_id] + home_advantage, ratings[away_id])
        away_expected = 1.0 - home_expected
        if home_goals > away_goals:
            home_actual, away_score = 1.0, 0.0
        elif home_goals < away_goals:
            home_actual, away_score = 0.0, 1.0
        else:
            home_actual, away_score = 0.5, 0.5
        ratings[home_id] = ratings[home_id] + k * (home_actual - home_expected)
        ratings[away_id] = ratings[away_id] + k * (away_score - away_expected)
    return pre_match
