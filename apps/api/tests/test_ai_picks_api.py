from __future__ import annotations

from tests.conftest import make_client

MATCH_ID = "mth_football-sportmonks-19719892"


def test_ai_picks_api_metadata_data_mode_and_request_id() -> None:
    client = make_client()
    response = client.get(
        "/api/v1/football/ai-picks",
        headers={"X-Request-ID": "req_ai_picks"},
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req_ai_picks"
    body = response.json()
    assert body["request_id"] == "req_ai_picks"
    assert body["data_mode"] == "mock"
    data = body["data"]
    assert data["total"] >= 1
    assert data["metadata"]["ai_picks_version"] == "ai-picks-0.1"
    assert data["metadata"]["scoring_formula"] == "opportunity_score = EV + Edge"
    assert all(item["model_status"] == "candidate" for item in data["items"])
    assert all(item["data_mode"] == "mock" for item in data["items"])
    assert all(item["match_id"] == MATCH_ID for item in data["items"])
    forbidden = ("guaranteed", "safe bet", "sure win", "certain", "pari sûr", "gain garanti")
    serialized = response.text.casefold()
    assert not any(term in serialized for term in forbidden)


def test_ai_picks_api_filters_and_pagination() -> None:
    client = make_client()
    page = client.get("/api/v1/football/ai-picks", params={"limit": 1, "offset": 1})
    assert page.status_code == 200
    data = page.json()["data"]
    assert len(data["items"]) == 1
    assert data["items"][0]["rank"] == 2
    empty = client.get("/api/v1/football/ai-picks", params={"date": "2026-07-08"})
    assert empty.status_code == 200
    assert empty.json()["data"]["items"] == []
    assert empty.json()["data"]["metadata"]["evaluated_matches"] == 0


def test_ai_picks_invalid_query_is_rfc9457() -> None:
    client = make_client()
    response = client.get(
        "/api/v1/football/ai-picks",
        params={"limit": 0},
        headers={"X-Request-ID": "req_ai_picks_invalid"},
    )
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["X-Request-ID"] == "req_ai_picks_invalid"
    body = response.json()
    assert body["type"] == "/problems/validation"
    assert body["request_id"] == "req_ai_picks_invalid"
