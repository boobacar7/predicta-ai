from __future__ import annotations

from datetime import UTC, datetime

import pytest

from predicta_ingestion.expand_historical_odds import ISOLATED_PARIS_TEAM_ID
from predicta_ingestion.historical_odds import CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED
from predicta_ingestion.oos_final_odds_batch import (
    CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY,
    MAX_FINAL_BATCH_CREDITS,
    MAX_FINAL_BATCH_REQUESTS,
    HistoricalEvent,
    estimate_final_oos_odds_batch,
    plan_champions_league_qualification_slots,
)
from predicta_ingestion.oos_historical_odds import historical_request_key as oos_request_key
from predicta_ingestion.persist_historical_odds import PilotMatch

HELIX_KICKOFF = datetime(2026, 8, 21, 19, 0, tzinfo=UTC)
LIGA_KICKOFF = datetime(2026, 8, 21, 19, 0, tzinfo=UTC)
MLS_KICKOFF = datetime(2026, 8, 15, 23, 30, tzinfo=UTC)
PARIS_KICKOFF = datetime(2026, 8, 22, 18, 45, tzinfo=UTC)
CL_QUAL_KICKOFF = datetime(2026, 7, 7, 16, 0, tzinfo=UTC)
CL_GROUP_KICKOFF = datetime(2026, 9, 8, 19, 0, tzinfo=UTC)


def _match(
    *,
    match_id: str,
    home: str,
    away: str,
    home_id: str,
    away_id: str,
    league: str,
    slug: str,
    kickoff: datetime,
) -> PilotMatch:
    return PilotMatch(
        match_id=match_id,
        home_team=home,
        away_team=away,
        home_team_id=home_id,
        away_team_id=away_id,
        league=league,
        league_slug=slug,
        kickoff_at=kickoff,
    )


def _universe() -> tuple[PilotMatch, ...]:
    return (
        _match(
            match_id="mth_pl",
            home="Helix FC",
            away="Meridian Athletic",
            home_id="tm_helix",
            away_id="tm_meridian",
            league="Premier League",
            slug="premier-league",
            kickoff=HELIX_KICKOFF,
        ),
        _match(
            match_id="mth_liga",
            home="Helix FC",
            away="Meridian Athletic",
            home_id="tm_helix",
            away_id="tm_meridian",
            league="La Liga",
            slug="la-liga",
            kickoff=LIGA_KICKOFF,
        ),
        _match(
            match_id="mth_mls",
            home="Inter Miami",
            away="Atlanta United",
            home_id="tm_miami",
            away_id="tm_atlanta",
            league="Major League Soccer",
            slug="mls",
            kickoff=MLS_KICKOFF,
        ),
        _match(
            match_id="mth_paris",
            home="Troyes",
            away="Paris",
            home_id="tm_troyes",
            away_id=ISOLATED_PARIS_TEAM_ID,
            league="Ligue 1",
            slug="ligue-1",
            kickoff=PARIS_KICKOFF,
        ),
        _match(
            match_id="mth_cl_qual",
            home="Lincoln Red Imps",
            away="Inter Club d'Escaldes",
            home_id="tm_lincoln",
            away_id="tm_escaldes",
            league="UEFA Champions League",
            slug="champions-league",
            kickoff=CL_QUAL_KICKOFF,
        ),
        _match(
            match_id="mth_cl_group",
            home="Real Madrid",
            away="Inter",
            home_id="tm_madrid",
            away_id="tm_inter",
            league="UEFA Champions League",
            slug="champions-league",
            kickoff=CL_GROUP_KICKOFF,
        ),
    )


def test_final_batch_credit_cap_is_ten_thousand() -> None:
    assert MAX_FINAL_BATCH_CREDITS == 10_000
    assert MAX_FINAL_BATCH_REQUESTS * CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED == 10_000


def test_qualification_slots_skip_group_stage_already_in_champs_league_payloads() -> None:
    events = (
        HistoricalEvent(
            sport_key="soccer_uefa_champs_league",
            home_team="Real Madrid",
            away_team="Inter Milan",
            commence_at=CL_GROUP_KICKOFF,
            event_id="cl_group",
            request_key="the_odds_api:historical_odds:soccer_uefa_champs_league:eu:h2h:2026-09-08T19:00:00Z",
        ),
    )
    slots = plan_champions_league_qualification_slots(
        _universe(),
        covered_ids=frozenset(),
        isolated_ids=frozenset(),
        existing_keys=frozenset(),
        events=events,
    )
    assert len(slots) == 1
    assert slots[0].kickoff_date == "2026-07-07"
    assert slots[0].sport_key == CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY
    assert slots[0].as_of == CL_QUAL_KICKOFF


def test_qualification_slots_skip_existing_request_keys() -> None:
    key = oos_request_key(
        "champions-league",
        CL_QUAL_KICKOFF,
        sport_key=CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY,
    )
    slots = plan_champions_league_qualification_slots(
        _universe(),
        covered_ids=frozenset(),
        isolated_ids=frozenset(),
        existing_keys=frozenset({key}),
        events=(
            HistoricalEvent(
                sport_key="soccer_uefa_champs_league",
                home_team="Real Madrid",
                away_team="Inter Milan",
                commence_at=CL_GROUP_KICKOFF,
                event_id="cl_group",
                request_key="the_odds_api:historical_odds:soccer_uefa_champs_league:eu:h2h:2026-09-08T19:00:00Z",
            ),
        ),
    )
    assert slots == ()


def test_estimate_replaces_champs_league_fetch_with_qualification_and_keeps_mls() -> None:
    estimate = estimate_final_oos_odds_batch(
        matches=_universe(),
        covered_ids=frozenset({"mth_pl"}),
        existing_request_keys=frozenset(),
        events=(),
        replay_payload_count=0,
    )
    leagues = {item.league for item in estimate.fetch_slots}
    sport_keys = {item.sport_key for item in estimate.fetch_slots if item.sport_key}
    assert "mls" in leagues
    assert "champions-league" in leagues
    assert CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY in sport_keys
    assert all(
        item.sport_key == CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY
        for item in estimate.fetch_slots
        if item.league == "champions-league"
    )
    assert estimate.estimated_credits <= MAX_FINAL_BATCH_CREDITS
    assert estimate.stop_reason is None
    assert "mth_paris" in estimate.isolated_match_ids
    plan = estimate.plan_summary()
    assert plan["already_covered"] == 1
    assert plan["uncovered"] == 5
    rendered = repr(estimate.to_dict()).lower()
    assert "apikey=" not in rendered
    assert "odds_test_secret" not in rendered


def test_estimate_refuses_when_credits_exceed_hard_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("predicta_ingestion.oos_final_odds_batch.MAX_FINAL_BATCH_CREDITS", 10)
    estimate = estimate_final_oos_odds_batch(
        matches=_universe(),
        covered_ids=frozenset(),
        existing_request_keys=frozenset(),
        events=(),
        replay_payload_count=0,
    )
    assert estimate.stop_reason is not None
    assert "10" in estimate.stop_reason


def test_mls_replay_expectation_uses_existing_franchise_table() -> None:
    events = (
        HistoricalEvent(
            sport_key="soccer_usa_mls",
            home_team="Inter Miami CF",
            away_team="Atlanta United FC",
            commence_at=MLS_KICKOFF,
            event_id="mls_1",
            request_key="the_odds_api:historical_odds:soccer_usa_mls:eu:h2h:2026-08-15T23:30:00Z",
        ),
    )
    estimate = estimate_final_oos_odds_batch(
        matches=_universe(),
        covered_ids=frozenset(),
        existing_request_keys=frozenset(),
        events=events,
        replay_payload_count=1,
    )
    assert "mth_mls" in estimate.expected_replay_match_ids


def test_estimate_drops_qualification_when_catalog_unavailable() -> None:
    estimate = estimate_final_oos_odds_batch(
        matches=_universe(),
        covered_ids=frozenset(),
        existing_request_keys=frozenset(),
        events=(),
        replay_payload_count=0,
        include_qualification=False,
    )
    assert estimate.qualification_unavailable is True
    assert all(item.sport_key != CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY for item in estimate.fetch_slots)
    assert all(item.league != "champions-league" for item in estimate.fetch_slots)
    key = oos_request_key(
        "champions-league",
        CL_QUAL_KICKOFF,
        sport_key=CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY,
    )
    assert CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY in key
    assert key != oos_request_key("champions-league", CL_QUAL_KICKOFF)
