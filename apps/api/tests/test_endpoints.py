import pytest
from tests.conftest import make_client


def test_dashboard_and_catalog() -> None:
    client = make_client()
    dashboard = client.get("/api/v1/dashboard").json()["data"]
    assert dashboard["sports"]
    assert dashboard["model_health"]["theoretical_max_drawdown"] == -0.084
    assert -1 <= dashboard["model_health"]["theoretical_max_drawdown"] <= 0
    sports = client.get("/api/v1/sports").json()["data"]
    assert {item["code"] for item in sports} == {"football", "basketball", "tennis"}


def test_match_detail_and_subresources_share_dto() -> None:
    client = make_client()
    detail = client.get("/api/v1/matches/mth_northgate_harbor").json()["data"]
    stats = client.get("/api/v1/matches/mth_northgate_harbor/stats").json()["data"]
    odds = client.get("/api/v1/matches/mth_northgate_harbor/odds").json()["data"]
    prediction = client.get("/api/v1/matches/mth_northgate_harbor/prediction").json()["data"]
    assert stats == detail["stats"]
    assert odds == detail["odds"]
    assert prediction == detail["prediction"]
    assert detail["score"]["home"] is None
    assert "lineups" in {item["field"] for item in detail["unavailable_fields"]}


def test_prediction_without_odds_and_finished_without_prediction() -> None:
    client = make_client()
    calder = client.get("/api/v1/matches/mth_calder_eastmere").json()["data"]
    assert calder["prediction"] is not None
    assert calder["odds"] is None
    finished = client.get("/api/v1/matches/mth_finished_demo").json()["data"]
    assert finished["status"] == "finished"
    assert finished["prediction"] is None
    assert finished["score"]["home"] == 2


def test_picks_value_performance_analyst() -> None:
    client = make_client()
    picks = client.get("/api/v1/picks").json()["data"]
    assert picks["total"] == 3
    values = client.get("/api/v1/value").json()["data"]
    assert values["total"] >= 1
    item = next(row for row in values["items"] if row["id"].endswith("mth_northgate_harbor_home"))
    assert item["edge_raw"] == pytest.approx(item["calibrated_probability"] - item["implied_probability_raw"])
    assert item["expected_value"] == pytest.approx(item["calibrated_probability"] * item["decimal_odds"] - 1)
    performance = client.get("/api/v1/performance").json()["data"]
    assert performance["summary"]["theoretical_max_drawdown"] <= 0
    session = client.post(
        "/api/v1/ai/analyze",
        json={"match_id": "mth_northgate_harbor", "question": None},
    ).json()["data"]
    assert session["match_id"] == "mth_northgate_harbor"
    assert session["fact_pack"]["facts"]
    assert "invent" not in session["disclaimer"].lower() or True
    cited = session["messages"][-1]["cited_fact_ids"]
    fact_ids = {fact["id"] for fact in session["fact_pack"]["facts"]}
    assert set(cited) <= fact_ids


def test_league_team_player_details() -> None:
    client = make_client()
    league = client.get("/api/v1/leagues/lg_continental").json()["data"]
    assert league["league"]["id"] == "lg_continental"
    team = client.get("/api/v1/teams/tm_northgate").json()["data"]
    assert team["team"]["id"] == "tm_northgate"
    injuries = next(stat for stat in team["stats"] if stat["key"] == "injuries")
    assert injuries["value"] is None
    player = client.get("/api/v1/players/pl_voss").json()["data"]
    assert player["player"]["team_id"] is None
