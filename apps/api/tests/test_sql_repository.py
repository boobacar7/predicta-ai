from pathlib import Path

from app.db.session import reset_database_state
from app.repositories.sql import SqlRepositoryBundle
from tests.conftest import make_client
from tests.sql_support import (
    FORBIDDEN_FIXTURE_IDS,
    LIVE_MATCH_ID,
    MOCK_MATCH_ID,
    create_catalog_database,
    sql_settings,
)


def test_empty_sql_database_stays_empty_and_live(tmp_path: Path) -> None:
    url = create_catalog_database(tmp_path / "empty.sqlite", seed=False)
    try:
        client = make_client(repository="sql", data_mode="live", database_url=url)
        matches = client.get("/api/v1/matches").json()
        assert matches["data_mode"] == "live"
        assert matches["data"]["items"] == []
        assert matches["data"]["total"] == 0
        sports = client.get("/api/v1/sports").json()
        assert sports["data_mode"] == "live"
        assert sports["data"] == []
        leagues = client.get("/api/v1/leagues").json()
        assert leagues["data"]["items"] == []
        assert leagues["data"]["total"] == 0
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["data"]["database"] is True
    finally:
        reset_database_state()


def test_sql_catalog_reads_live_identities_without_inventing_odds(tmp_path: Path) -> None:
    url = create_catalog_database(tmp_path / "catalog.sqlite", seed=True)
    try:
        client = make_client(repository="sql", data_mode="live", database_url=url)
        matches = client.get("/api/v1/matches").json()
        assert matches["data_mode"] == "live"
        ids = {item["id"] for item in matches["data"]["items"]}
        assert LIVE_MATCH_ID in ids
        assert "mth_catalog_finished_002" in ids
        assert MOCK_MATCH_ID not in ids
        assert ids.isdisjoint(FORBIDDEN_FIXTURE_IDS)
        assert matches["data"]["total"] == 2

        scheduled = next(item for item in matches["data"]["items"] if item["id"] == LIVE_MATCH_ID)
        assert scheduled["home"]["id"] == "tm_catalog_alpha"
        assert scheduled["away"]["id"] == "tm_catalog_beta"
        assert scheduled["league"]["id"] == "lg_catalog_premier"
        assert scheduled["score"]["home"] is None
        assert scheduled["score"]["away"] is None
        assert scheduled["score"]["quality"]["availability"] == "unavailable"
        assert scheduled["prediction_preview"] is None
        assert scheduled["value_preview"] is None

        detail = client.get(f"/api/v1/matches/{LIVE_MATCH_ID}").json()["data"]
        assert detail["id"] == LIVE_MATCH_ID
        assert detail["odds"] is None
        assert detail["prediction"] is None
        assert detail["stats"] == []
        assert {item["field"] for item in detail["unavailable_fields"]} >= {
            "odds",
            "prediction",
            "stats",
            "timeline",
            "form",
        }
        odds = client.get(f"/api/v1/matches/{LIVE_MATCH_ID}/odds").json()["data"]
        prediction = client.get(f"/api/v1/matches/{LIVE_MATCH_ID}/prediction").json()["data"]
        stats = client.get(f"/api/v1/matches/{LIVE_MATCH_ID}/stats").json()["data"]
        assert odds is None
        assert prediction is None
        assert stats == []

        sports = client.get("/api/v1/sports").json()["data"]
        assert {item["code"] for item in sports} == {"football"}
        teams = client.get("/api/v1/teams").json()["data"]["items"]
        assert {item["id"] for item in teams} == {"tm_catalog_alpha", "tm_catalog_beta"}
        players = client.get("/api/v1/players").json()["data"]["items"]
        assert players[0]["id"] == "pl_catalog_keeper"
        league = client.get("/api/v1/leagues/lg_catalog_premier").json()["data"]
        assert league["standing"] == []
        assert "standing" in {item["field"] for item in league["unavailable_fields"]}
    finally:
        reset_database_state()


def test_sql_repository_bundle_does_not_load_mock_fixtures(tmp_path: Path) -> None:
    url = create_catalog_database(tmp_path / "catalog.sqlite", seed=True)
    try:
        repos = SqlRepositoryBundle(sql_settings(url))
        match_ids = {item.id for item in repos.matches.list_matches(
            sport=None, league_id=None, match_date=None, status=None
        )}
        assert LIVE_MATCH_ID in match_ids
        assert MOCK_MATCH_ID not in match_ids
        assert match_ids.isdisjoint(FORBIDDEN_FIXTURE_IDS)
        assert repos.signals.list_picks() == []
        assert repos.matches.get_match(FORBIDDEN_FIXTURE_IDS[0]) is None
    finally:
        reset_database_state()
