from pathlib import Path

import pytest
from pydantic import ValidationError

from predicta_ingestion.config import Settings, get_settings


def test_staging_refuses_mock_data_mode() -> None:
    with pytest.raises(ValidationError, match="data_mode=mock is forbidden"):
        Settings(_env_file=None, env="staging", data_mode="mock", enable_live=False)


def test_production_still_refuses_mock_data_mode() -> None:
    with pytest.raises(ValidationError, match="data_mode=mock is forbidden"):
        Settings(_env_file=None, env="production", data_mode="mock", enable_live=False)


def test_live_without_enable_live_is_not_relabelled_as_mock() -> None:
    with pytest.raises(ValidationError, match="refusing to relabel as mock"):
        Settings(_env_file=None, env="staging", data_mode="live", enable_live=False)


def test_staging_allows_live_with_enable_live() -> None:
    settings = Settings(_env_file=None, env="staging", data_mode="live", enable_live=True)
    assert settings.resolved_data_mode() == "live"
    assert settings.is_deployed is True


def test_get_settings_refuses_staging_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREDICTA_INGESTION_ENV", "staging")
    monkeypatch.setenv("PREDICTA_INGESTION_DATA_MODE", "mock")
    monkeypatch.setenv("PREDICTA_INGESTION_ENABLE_LIVE", "false")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError, match="staging"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_env_example_documents_staging_live() -> None:
    example = Path(__file__).resolve().parents[1] / ".env.example"
    text = example.read_text(encoding="utf-8")
    assert "PREDICTA_INGESTION_ENV=staging" in text
    assert "PREDICTA_INGESTION_DATA_MODE=live" in text
    assert "PREDICTA_INGESTION_ENABLE_LIVE=true" in text
