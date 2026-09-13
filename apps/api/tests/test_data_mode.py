from pathlib import Path

from app.db.session import reset_database_state
from tests.conftest import make_client
from tests.sql_support import create_catalog_database

ENVELOPE_KEYS = {"data_mode", "generated_at", "request_id", "data"}


def test_data_mode_is_mock_for_fixture_repository() -> None:
    client = make_client()
    for path in (
        "/api/v1/dashboard",
        "/api/v1/sports",
        "/api/v1/matches",
        "/api/v1/picks",
        "/api/v1/value",
        "/api/v1/performance",
    ):
        body = client.get(path).json()
        assert set(body) >= ENVELOPE_KEYS
        assert body["data_mode"] == "mock"
        assert body["generated_at"].endswith("Z")


def test_sql_repository_is_advertised_as_live_and_empty(tmp_path: Path) -> None:
    url = create_catalog_database(tmp_path / "empty.sqlite", seed=False)
    try:
        client = make_client(repository="sql", data_mode="live", database_url=url)
        body = client.get("/api/v1/matches").json()
        assert body["data_mode"] == "live"
        assert body["data"]["items"] == []
        assert body["data"]["total"] == 0
    finally:
        reset_database_state()
