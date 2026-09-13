from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from predicta_ingestion.canonical.enums import MatchStatus
from predicta_ingestion.canonical.models import Match
from predicta_ingestion.clock import ensure_utc
from predicta_ingestion.pit.store import PointInTimeStore

FORM_WINDOWS = (5, 10)
H2H_MIN_MATCHES = 2
CUTOFF_POLICY_PRE_KICKOFF = "pre_kickoff"
FEATURE_SCHEMA_VERSION = "football-1x2-features-0.3"

FEATURE_SCHEMA: tuple[str, ...] = (
    "home_elo_pre",
    "away_elo_pre",
    "elo_diff",
    "elo_available",
    "home_form_5",
    "away_form_5",
    "home_form_10",
    "away_form_10",
    "home_form_5_available",
    "away_form_5_available",
    "home_form_10_available",
    "away_form_10_available",
    "home_goals_for_5",
    "home_goals_against_5",
    "home_goals_for_10",
    "home_goals_against_10",
    "away_goals_for_5",
    "away_goals_against_5",
    "away_goals_for_10",
    "away_goals_against_10",
    "h2h_home_wins",
    "h2h_draws",
    "h2h_away_wins",
    "h2h_available",
    "h2h_matches",
    "home_matches_played",
    "away_matches_played",
)


def form_features(
    *,
    match: Match,
    prior_matches: Sequence[Match],
    home_elo: float | None,
    away_elo: float | None,
) -> dict[str, float | int | None]:
    """Features computed only from facts strictly before the target cutoff.

    Prior matches must already satisfy `event_at < kickoff` and
    `available_at < kickoff`. The target result is never used. Standings are
    not a feature in this schema.
    """
    cutoff = ensure_utc(match.kickoff_at)
    home_id = match.home_team_id or ""
    away_id = match.away_team_id or ""
    home_prior = _team_matches(prior_matches, home_id, cutoff)
    away_prior = _team_matches(prior_matches, away_id, cutoff)
    h2h = _head_to_head(prior_matches, home_id, away_id, cutoff)
    features: dict[str, float | int | None] = {
        "home_matches_played": len(home_prior),
        "away_matches_played": len(away_prior),
        "home_elo_pre": home_elo,
        "away_elo_pre": away_elo,
        "elo_diff": None if home_elo is None or away_elo is None else home_elo - away_elo,
        "elo_available": 1 if home_elo is not None and away_elo is not None else 0,
        "h2h_matches": h2h["matches"],
        "h2h_home_wins": h2h["home_wins"],
        "h2h_draws": h2h["draws"],
        "h2h_away_wins": h2h["away_wins"],
        "h2h_available": 1 if h2h["matches"] >= H2H_MIN_MATCHES else 0,
    }
    for window in FORM_WINDOWS:
        home_form = home_prior[:window]
        away_form = away_prior[:window]
        features[f"home_form_{window}"] = _points(home_form, home_id)
        features[f"away_form_{window}"] = _points(away_form, away_id)
        features[f"home_goals_for_{window}"] = _goals_for(home_form, home_id)
        features[f"home_goals_against_{window}"] = _goals_against(home_form, home_id)
        features[f"away_goals_for_{window}"] = _goals_for(away_form, away_id)
        features[f"away_goals_against_{window}"] = _goals_against(away_form, away_id)
        features[f"home_form_{window}_available"] = 1 if len(home_prior) >= window else 0
        features[f"away_form_{window}_available"] = 1 if len(away_prior) >= window else 0
    return {key: features[key] for key in FEATURE_SCHEMA}


def prior_matches_for_features(store: PointInTimeStore, match: Match) -> list[Match]:
    """Finished matches with event_at and available_at strictly before kickoff."""
    cutoff = ensure_utc(match.kickoff_at)
    store.assert_pre_kickoff(match, cutoff)
    selected: list[Match] = []
    for item in store.matches_finished_before(cutoff):
        if item.id == match.id:
            continue
        if ensure_utc(item.kickoff_at) >= cutoff:
            continue
        selected.append(item)
    selected.sort(key=lambda item: (ensure_utc(item.kickoff_at), item.id), reverse=True)
    return selected


def _team_matches(prior: Sequence[Match], team_id: str, cutoff: datetime) -> list[Match]:
    rows: list[Match] = []
    for item in prior:
        if item.status is not MatchStatus.FINISHED:
            continue
        if item.home_team_id != team_id and item.away_team_id != team_id:
            continue
        if ensure_utc(item.kickoff_at) >= ensure_utc(cutoff):
            continue
        rows.append(item)
    rows.sort(key=lambda item: (ensure_utc(item.kickoff_at), item.id), reverse=True)
    return rows


def _head_to_head(
    prior: Sequence[Match],
    home_id: str,
    away_id: str,
    cutoff: datetime,
) -> dict[str, int]:
    wins_home = 0
    draws = 0
    wins_away = 0
    count = 0
    for item in prior:
        if item.status is not MatchStatus.FINISHED:
            continue
        teams = {item.home_team_id, item.away_team_id}
        if teams != {home_id, away_id}:
            continue
        if ensure_utc(item.kickoff_at) >= ensure_utc(cutoff):
            continue
        if item.home_score is None or item.away_score is None:
            continue
        count += 1
        if item.home_score == item.away_score:
            draws += 1
            continue
        winner = item.home_team_id if item.home_score > item.away_score else item.away_team_id
        if winner == home_id:
            wins_home += 1
        else:
            wins_away += 1
    return {
        "matches": count,
        "home_wins": wins_home,
        "draws": draws,
        "away_wins": wins_away,
    }


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
