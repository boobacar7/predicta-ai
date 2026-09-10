from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from predicta_ingestion.canonical.enums import Availability, MatchStatus
from predicta_ingestion.canonical.models import Match, StandingSnapshot
from predicta_ingestion.clock import ensure_utc
from predicta_ingestion.pit.store import PointInTimeStore

FORM_LOOKBACK = 5
CUTOFF_POLICY_PRE_KICKOFF = "pre_kickoff"


def form_features(
    *,
    match: Match,
    prior_matches: Sequence[Match],
    standings: Sequence[StandingSnapshot],
    home_elo: float | None,
    away_elo: float | None,
) -> dict[str, float | int | None]:
    """Features computed only from matches strictly before the target event date.

    Form uses calendar dates `< target.kickoff_at.date()` so a same-day result cannot
    enter a form feature. Elo ratings are supplied separately (kickoff-ordered).
    """
    cutoff = ensure_utc(match.kickoff_at)
    home_id = match.home_team_id or ""
    away_id = match.away_team_id or ""
    home_prior = _team_matches(prior_matches, home_id, cutoff)
    away_prior = _team_matches(prior_matches, away_id, cutoff)
    home_form = home_prior[:FORM_LOOKBACK]
    away_form = away_prior[:FORM_LOOKBACK]
    home_home = [item for item in home_prior if item.home_team_id == home_id][:FORM_LOOKBACK]
    away_away = [item for item in away_prior if item.away_team_id == away_id][:FORM_LOOKBACK]
    home_rank, away_rank = _standing_ranks(standings, home_id, away_id)
    return {
        "home_form_points": _points(home_form, home_id),
        "away_form_points": _points(away_form, away_id),
        "home_goals_for": _goals_for(home_form, home_id),
        "home_goals_against": _goals_against(home_form, home_id),
        "home_goal_diff": _goals_for(home_form, home_id) - _goals_against(home_form, home_id),
        "away_goals_for": _goals_for(away_form, away_id),
        "away_goals_against": _goals_against(away_form, away_id),
        "away_goal_diff": _goals_for(away_form, away_id) - _goals_against(away_form, away_id),
        "home_home_points": _points(home_home, home_id),
        "away_away_points": _points(away_away, away_id),
        "home_matches_played": len(home_prior),
        "away_matches_played": len(away_prior),
        "home_elo_pre": home_elo,
        "away_elo_pre": away_elo,
        "home_standing_rank": home_rank,
        "away_standing_rank": away_rank,
    }


def prior_matches_for_features(store: PointInTimeStore, match: Match) -> list[Match]:
    """Finished matches available before kickoff, excluding the target date and later."""
    cutoff = ensure_utc(match.kickoff_at)
    store.assert_pre_kickoff(match, cutoff)
    selected: list[Match] = []
    for item in store.matches_finished_before(cutoff):
        if item.id == match.id:
            continue
        if ensure_utc(item.kickoff_at).date() >= cutoff.date():
            continue
        if ensure_utc(item.kickoff_at) >= cutoff:
            continue
        selected.append(item)
    selected.sort(key=lambda item: ensure_utc(item.kickoff_at), reverse=True)
    return selected


def _team_matches(prior: Sequence[Match], team_id: str, cutoff: datetime) -> list[Match]:
    rows: list[Match] = []
    for item in prior:
        if item.status is not MatchStatus.FINISHED:
            continue
        if item.home_team_id != team_id and item.away_team_id != team_id:
            continue
        if ensure_utc(item.kickoff_at).date() >= ensure_utc(cutoff).date():
            continue
        rows.append(item)
    rows.sort(key=lambda item: ensure_utc(item.kickoff_at), reverse=True)
    return rows


def _points(matches: Sequence[Match], team_id: str) -> int:
    total = 0
    for item in matches:
        if item.home_score is None or item.away_score is None:
            continue
        if item.home_score == item.away_score:
            total += 1
        elif item.home_team_id == team_id and item.home_score > item.away_score:
            total += 3
        elif item.away_team_id == team_id and item.away_score > item.home_score:
            total += 3
    return total


def _goals_for(matches: Sequence[Match], team_id: str) -> int:
    total = 0
    for item in matches:
        if item.home_score is None or item.away_score is None:
            continue
        total += item.home_score if item.home_team_id == team_id else item.away_score
    return total


def _goals_against(matches: Sequence[Match], team_id: str) -> int:
    total = 0
    for item in matches:
        if item.home_score is None or item.away_score is None:
            continue
        total += item.away_score if item.home_team_id == team_id else item.home_score
    return total


def _standing_ranks(
    standings: Sequence[StandingSnapshot],
    home_id: str,
    away_id: str,
) -> tuple[int | None, int | None]:
    home_rank: int | None = None
    away_rank: int | None = None
    for row in standings:
        if row.availability is Availability.UNAVAILABLE:
            continue
        if row.team_id == home_id and row.rank is not None:
            home_rank = row.rank
        if row.team_id == away_id and row.rank is not None:
            away_rank = row.rank
    return home_rank, away_rank
