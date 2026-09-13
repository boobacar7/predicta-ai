from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_staging_refuses_mock_repository() -> None:
    with pytest.raises(ValidationError, match="Mock repositories are forbidden"):
        Settings(_env_file=None, env="staging", repository="mock", data_mode="live")


def test_staging_refuses_mock_data_mode() -> None:
    with pytest.raises(ValidationError, match="data_mode=mock is forbidden"):
        Settings(_env_file=None, env="staging", repository="sql", data_mode="mock")


def test_production_still_refuses_mock_repository() -> None:
    with pytest.raises(ValidationError, match="Mock repositories are forbidden"):
        Settings(_env_file=None, env="production", repository="mock", data_mode="live")


def test_staging_allows_sql_live() -> None:
    settings = Settings(_env_file=None, env="staging", repository="sql", data_mode="live")
    assert settings.resolved_data_mode() == "live"
    assert settings.is_deployed is True


def test_development_still_allows_mock() -> None:
    settings = Settings(_env_file=None, env="development")
    assert settings.repository == "mock"
    assert settings.resolved_data_mode() == "mock"


def test_get_settings_refuses_staging_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREDICTA_API_ENV", "staging")
    monkeypatch.setenv("PREDICTA_API_REPOSITORY", "mock")
    monkeypatch.setenv("PREDICTA_API_DATA_MODE", "mock")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError, match="staging"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_env_example_documents_staging_sql_live() -> None:
    example = Path(__file__).resolve().parents[1] / ".env.example"
    text = example.read_text(encoding="utf-8")
    assert "PREDICTA_API_ENV=staging" in text
    assert "PREDICTA_API_REPOSITORY=sql" in text
    assert "PREDICTA_API_DATA_MODE=live" in text
    assert "sk_live" not in text
    assert "SPORTMONKS_API_TOKEN=" not in text
