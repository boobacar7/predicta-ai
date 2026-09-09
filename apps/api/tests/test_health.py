from tests.conftest import make_client


def test_health_ok() -> None:
    client = make_client()
    response = client.get("/health", headers={"X-Request-ID": "req_health"})
    assert response.status_code == 200
    body = response.json()
    assert body["data_mode"] == "mock"
    assert body["request_id"] == "req_health"
    assert response.headers["X-Request-ID"] == "req_health"
    assert body["data"]["status"] == "ok"


def test_ready_ok_in_mock_mode() -> None:
    client = make_client()
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"
    assert "request_id" in response.json()
