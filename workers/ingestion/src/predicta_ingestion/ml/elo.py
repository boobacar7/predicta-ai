from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from predicta_ingestion.canonical.enums import MatchStatus
from predicta_ingestion.canonical.models import Match
from predicta_ingestion.clock import ensure_utc

INITIAL_ELO = 1500.0
ELO_K = 20.0
HOME_ADVANTAGE = 80.0

ELO_PARAMETERS: dict[str, float | str] = {
    "initial": INITIAL_ELO,
    "k": ELO_K,
    "home_advantage": HOME_ADVANTAGE,
    "scale": 400.0,
    "update": "after_available_at",
}


def expected_score(rating: float, opponent: float) -> float:
    return 1.0 / (1.0 + 10 ** ((opponent - rating) / 400.0))


def reconstruct_pre_match_elo(
    matches: Sequence[Match],
    *,
    initial: float = INITIAL_ELO,
    k: float = ELO_K,
    home_advantage: float = HOME_ADVANTAGE,
) -> dict[str, tuple[float, float]]:
    """Walk finished matches and record ratings *before* each kickoff.

    Ratings are keyed by `canonical_team_id`. All competitions share one
    timeline: a Ligue 1 result updates the same club that later plays in the
    Champions League.

    Snapshot at `event_at` (kickoff). Apply the result only at `available_at`.
    A later match whose kickoff is before the previous result is available does
    not inherit that result. Ratings after match N are never written onto N.

    Equal timestamps: events are ordered by
    `(timestamp, kind, match_id)` where snapshot `kind=0` runs before update
    `kind=1`. Two matches that kick off at the same instant therefore both see
    the pre-match ratings; neither result can affect the other at that
    timestamp.

    If `available_at` of match A is greater than or equal to the kickoff of
    match B, A's result must not change B's pre-match Elo. When the two
    timestamps are equal, B's snapshot (`kind=0`) still runs before A's update
    (`kind=1`). The cutoff is therefore `available_at < T`, not `<=`. Remaining
    ties use the canonical `match_id` so the walk is deterministic.
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
    events: list[tuple[object, int, str, str, Match]] = []
    for match in ordered:
        kickoff = ensure_utc(match.kickoff_at)
        available = ensure_utc(match.provenance.available_at)
        events.append((kickoff, 0, match.id, "snapshot", match))
        events.append((available, 1, match.id, "update", match))
    events.sort(key=lambda item: (item[0], item[1], item[2]))
    ratings: dict[str, float] = defaultdict(lambda: initial)
    pre_match: dict[str, tuple[float, float]] = {}
    for _when, _order, _match_id, kind, match in events:
        home_id = match.home_team_id or ""
        away_id = match.away_team_id or ""
        if kind == "snapshot":
            pre_match[match.id] = (ratings[home_id], ratings[away_id])
            continue
        home_goals = match.home_score
        away_goals = match.away_score
        if home_goals is None or away_goals is None:
            continue
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


def snapshot_pre_match_elo(
    matches: Sequence[Match],
    *,
    initial: float = INITIAL_ELO,
    k: float = ELO_K,
    home_advantage: float = HOME_ADVANTAGE,
) -> dict[str, tuple[float, float]]:
    """Snapshot pre-match Elo for finished *and* unlabeled matches.

    Finished matches still update ratings only at `available_at` with the same
    K / home advantage as `reconstruct_pre_match_elo`. Scheduled matches are
    snapshotted at kickoff and never contribute a score or rating update.
    """
    finished: list[Match] = []
    unlabeled: list[Match] = []
    for match in matches:
        if not match.home_team_id or not match.away_team_id:
            continue
        if (
            match.status is MatchStatus.FINISHED
            and match.home_score is not None
            and match.away_score is not None
        ):
            finished.append(match)
        else:
            unlabeled.append(match)
    events: list[tuple[object, int, str, str, Match]] = []
    for match in finished:
        events.append((ensure_utc(match.kickoff_at), 0, match.id, "snapshot", match))
        events.append((ensure_utc(match.provenance.available_at), 1, match.id, "update", match))
    for match in unlabeled:
        events.append((ensure_utc(match.kickoff_at), 0, match.id, "snapshot", match))
    events.sort(key=lambda item: (item[0], item[1], item[2]))
    ratings: dict[str, float] = defaultdict(lambda: initial)
    pre_match: dict[str, tuple[float, float]] = {}
    for _when, _order, _match_id, kind, match in events:
        home_id = match.home_team_id or ""
        away_id = match.away_team_id or ""
        if kind == "snapshot":
            pre_match[match.id] = (ratings[home_id], ratings[away_id])
            continue
        home_goals = match.home_score
        away_goals = match.away_score
        if home_goals is None or away_goals is None:
            continue
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
