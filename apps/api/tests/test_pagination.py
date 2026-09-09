from tests.conftest import make_client


def test_pagination_limit_and_offset() -> None:
    client = make_client()
    full = client.get("/api/v1/teams").json()["data"]
    page = client.get("/api/v1/teams", params={"limit": 2, "offset": 1}).json()["data"]
    assert full["total"] == page["total"]
    assert len(page["items"]) == 2
    assert page["items"][0]["id"] == full["items"][1]["id"]


def test_sport_and_query_filters() -> None:
    client = make_client()
    football = client.get("/api/v1/leagues", params={"sport": "football"}).json()["data"]
    assert football["total"] >= 1
    assert all(item["sport"] == "football" for item in football["items"])
    search = client.get("/api/v1/teams", params={"query": "Northgate"}).json()["data"]
    assert search["total"] == 1
    assert search["items"][0]["id"] == "tm_northgate"


def test_match_status_and_date_filters() -> None:
    client = make_client()
    live = client.get("/api/v1/matches", params={"status": "live"}).json()["data"]
    assert live["total"] == 1
    assert live["items"][0]["id"] == "mth_riverside_oakmont"
    dated = client.get("/api/v1/matches", params={"date": "2026-09-09"}).json()["data"]
    assert dated["total"] >= 1
    assert all(item["kickoff_at"].startswith("2026-09-09") for item in dated["items"])
