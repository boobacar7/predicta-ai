from tests.conftest import make_client


def test_rfc9457_not_found() -> None:
    client = make_client()
    response = client.get("/api/v1/matches/unknown")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["title"] == "Not Found"
    assert body["status"] == 404
    assert "request_id" in body
    assert body["type"] == "/problems/not-found"
    assert response.headers["X-Request-ID"] == body["request_id"]


def test_invalid_sport_returns_400_problem() -> None:
    client = make_client()
    response = client.get("/api/v1/matches", params={"sport": "chess"})
    assert response.status_code == 400
    body = response.json()
    assert body["status"] == 400
    assert body["type"] == "/problems/validation"
    assert "request_id" in body


def test_invalid_limit_returns_400() -> None:
    client = make_client()
    response = client.get("/api/v1/leagues", params={"limit": 0})
    assert response.status_code == 400
    assert response.json()["status"] == 400


def test_invalid_analyst_body_returns_422() -> None:
    client = make_client()
    response = client.post("/api/v1/ai/analyze", json={"question": "hello"})
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == 422
    assert "request_id" in body
