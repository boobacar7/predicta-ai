from pathlib import Path

import pytest
from app.core.config import Settings, get_settings
from pydantic import ValidationError


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


def test_staging_refuses_auth_bypass() -> None:
    with pytest.raises(ValidationError, match="AUTH_BYPASS is forbidden"):
        Settings(
            _env_file=None,
            env="staging",
            repository="sql",
            data_mode="live",
            auth_bypass=True,
        )


def test_production_refuses_auth_bypass() -> None:
    with pytest.raises(ValidationError, match="AUTH_BYPASS is forbidden"):
        Settings(
            _env_file=None,
            env="production",
            repository="sql",
            data_mode="live",
            auth_bypass=True,
        )


def test_development_allows_auth_bypass() -> None:
    settings = Settings(_env_file=None, env="development", auth_bypass=True)
    assert settings.auth_bypass is True
    assert settings.session_cookie_secure is False


def test_staging_session_cookie_is_secure() -> None:
    settings = Settings(_env_file=None, env="staging", repository="sql", data_mode="live")
    assert settings.auth_bypass is False
    assert settings.session_cookie_secure is True


def test_env_example_documents_staging_sql_live() -> None:
    example = Path(__file__).resolve().parents[1] / ".env.example"
    text = example.read_text(encoding="utf-8")
    assert "PREDICTA_API_ENV=staging" in text
    assert "PREDICTA_API_REPOSITORY=sql" in text
    assert "PREDICTA_API_DATA_MODE=live" in text
    assert "PREDICTA_API_AUTH_BYPASS=false" in text
    assert "PREDICTA_API_INVITE_ALLOWLIST=" in text
    assert "sk_live" not in text
    assert "SPORTMONKS_API_TOKEN=" not in text
