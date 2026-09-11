from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.match_identity.models import MatchIdentity
from app.match_identity.repository import ParquetArchiveMatchIdentityRepository
from tests.conftest import make_client
from tests.live_assets import requires_football_http

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "workers" / "ingestion" / "var" / "football-1x2-history.parquet"
RAW_ARCHIVE = REPO / "workers" / "ingestion" / "var" / "raw"

HISTORICAL_MATCHES = (
    (
        "Premier League",
        "mth_football-sportmonks-19722183",
        "Arsenal",
        "Chelsea",
        datetime(2026, 9, 6, 15, 30, tzinfo=UTC),
    ),
    (
        "Ligue 1",
        "mth_football-sportmonks-19715615",
        "Olympique Marseille",
        "Paris",
        datetime(2026, 9, 6, 18, 45, tzinfo=UTC),
    ),
    (
        "La Liga",
        "mth_football-sportmonks-19732709",
        "Elche",
        "Real Sociedad",
        datetime(2026, 9, 7, 19, 30, tzinfo=UTC),
    ),
    (
        "Bundesliga",
        "mth_football-sportmonks-19735185",
        "Eintracht Frankfurt",
        "FC Augsburg",
        datetime(2026, 9, 6, 15, 30, tzinfo=UTC),
    ),
    (
        "Serie A",
        "mth_football-sportmonks-19713588",
        "Udinese",
        "Lazio",
        datetime(2026, 9, 7, 18, 45, tzinfo=UTC),
    ),
    (
        "Champions League",
        "mth_football-sportmonks-19873242",
        "Sporting CP",
        "Galatasaray",
        datetime(2026, 9, 9, 19, 0, tzinfo=UTC),
    ),
    (
        "Major League Soccer",
        "mth_football-sportmonks-19609793",
        "Portland Timbers",
        "St. Louis City",
        datetime(2026, 9, 10, 2, 30, tzinfo=UTC),
    ),
)


@pytest.fixture(scope="module")
def identities() -> ParquetArchiveMatchIdentityRepository:
    return ParquetArchiveMatchIdentityRepository(DATASET, RAW_ARCHIVE)


@requires_football_http
@pytest.mark.parametrize(("league", "match_id", "home", "away", "kickoff"), HISTORICAL_MATCHES)
def test_real_historical_identity_across_seven_leagues(
    identities: ParquetArchiveMatchIdentityRepository,
    league: str,
    match_id: str,
    home: str,
    away: str,
    kickoff: datetime,
) -> None:
    identity = identities.get(match_id)
    assert identity is not None
    assert identity.match_id == match_id
    assert identity.home_team == home
    assert identity.away_team == away
    assert identity.league == league
    assert identity.kickoff_at == kickoff
    assert identity.home_team_id.startswith("tm_football-sportmonks-")
    assert identity.away_team_id.startswith("tm_football-sportmonks-")
    assert identity.data_mode == "live"


@requires_football_http
def test_historical_match_route_resolves_ai_pick_match_id() -> None:
    client = make_client()
    response = client.get("/api/v1/matches/mth_football-sportmonks-19719892")
    assert response.status_code == 200
    assert response.json()["data_mode"] == "live"
    data = response.json()["data"]
    assert data == {
        "match_id": "mth_football-sportmonks-19719892",
        "home_team_id": "tm_football-sportmonks-10068",
        "away_team_id": "tm_football-sportmonks-17303",
        "home_team": "Lincoln Red Imps",
        "away_team": "Inter Club d'Escaldes",
        "league": "Champions League",
        "kickoff_at": "2026-07-07T16:00:00Z",
        "data_mode": "live",
        "resource_scope": "structural_identity",
    }


@requires_football_http
def test_ai_pick_contains_resolved_match_identity() -> None:
    client = make_client()
    response = client.get("/api/v1/football/ai-picks")
    assert response.status_code == 200
    for item in response.json()["data"]["items"]:
        assert item["home_team"] == "Lincoln Red Imps"
        assert item["away_team"] == "Inter Club d'Escaldes"
        assert item["league"] == "Champions League"
        assert item["kickoff_at"] == "2026-07-07T16:00:00Z"


@requires_football_http
def test_structural_identity_projection_cannot_carry_post_kickoff_results() -> None:
    fields = set(MatchIdentity.__dataclass_fields__)
    assert fields.isdisjoint({"status", "home_score", "away_score", "result", "events"})
    identity = ParquetArchiveMatchIdentityRepository(DATASET, RAW_ARCHIVE).get(
        "mth_football-sportmonks-19722183"
    )
    assert identity is not None
    assert identity.kickoff_at == datetime(2026, 9, 6, 15, 30, tzinfo=UTC)


@requires_football_http
def test_missing_structural_labels_remain_explicitly_null(tmp_path: Path) -> None:
    identity = ParquetArchiveMatchIdentityRepository(DATASET, tmp_path).get(
        "mth_football-sportmonks-19719892"
    )
    assert identity is not None
    assert identity.home_team is None
    assert identity.away_team is None


@requires_football_http
def test_truly_unknown_match_returns_clean_404_without_mock_identity() -> None:
    client = make_client()
    response = client.get(
        "/api/v1/matches/mth_football-sportmonks-unknown",
        headers={"X-Request-ID": "req_unknown_historical"},
    )
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["X-Request-ID"] == "req_unknown_historical"
    assert response.json()["type"] == "/problems/not-found"
    assert response.json()["request_id"] == "req_unknown_historical"
    assert "home_team" not in response.json()
