import os
from pathlib import Path

import pytest
from tests.conftest import TEST_SPORTMONKS_TOKEN

from predicta_ingestion.cli import main
from predicta_ingestion.config import Settings, get_settings, load_local_env
from predicta_ingestion.providers.errors import ProviderNotConfigured
from predicta_ingestion.secrets import redact_text

PROCESS_TOKEN = "sm_from_process_do_not_log"


def _write_env(path: Path, *, token: str) -> Path:
    path.write_text(
        "\n".join(
            [
                f"SPORTMONKS_API_TOKEN={token}",
                "PREDICTA_INGESTION_ENABLE_LIVE=true",
                "PREDICTA_INGESTION_DATA_MODE=live",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_load_local_env_reads_unprefixed_token_and_live_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = _write_env(tmp_path / ".env", token=TEST_SPORTMONKS_TOKEN)
    monkeypatch.delenv("SPORTMONKS_API_TOKEN", raising=False)
    monkeypatch.delenv("PREDICTA_INGESTION_SPORTMONKS_KEY", raising=False)
    monkeypatch.delenv("PREDICTA_INGESTION_ENABLE_LIVE", raising=False)
    monkeypatch.delenv("PREDICTA_INGESTION_DATA_MODE", raising=False)
    loaded = load_local_env(env_file=env_file)
    assert loaded == (env_file.resolve(),)
    get_settings.cache_clear()
    settings = Settings(_env_file=None)
    assert settings.sportmonks_key == TEST_SPORTMONKS_TOKEN
    assert settings.enable_live is True
    assert settings.data_mode == "live"
    assert TEST_SPORTMONKS_TOKEN not in repr(settings)


def test_explicit_environment_wins_over_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = _write_env(tmp_path / ".env", token=TEST_SPORTMONKS_TOKEN)
    monkeypatch.setenv("SPORTMONKS_API_TOKEN", PROCESS_TOKEN)
    monkeypatch.delenv("PREDICTA_INGESTION_SPORTMONKS_KEY", raising=False)
    loaded = load_local_env(env_file=env_file)
    assert loaded == (env_file.resolve(),)
    assert os.environ["SPORTMONKS_API_TOKEN"] == PROCESS_TOKEN
    settings = Settings(_env_file=None)
    assert settings.sportmonks_key == PROCESS_TOKEN
    assert TEST_SPORTMONKS_TOKEN not in repr(settings)
    assert PROCESS_TOKEN not in repr(settings)


def test_cli_stderr_never_contains_token(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("SPORTMONKS_API_TOKEN", TEST_SPORTMONKS_TOKEN)
    monkeypatch.setattr(
        "predicta_ingestion.cli.get_settings",
        lambda: (_ for _ in ()).throw(RuntimeError(f"Authorization failed {TEST_SPORTMONKS_TOKEN}")),
    )
    assert main(["ingest-history", "--league", "MLS", "--dry-run"]) == 1
    captured = capsys.readouterr()
    assert TEST_SPORTMONKS_TOKEN not in captured.err
    assert TEST_SPORTMONKS_TOKEN not in captured.out
    assert "[redacted]" in captured.err


def test_provider_not_configured_does_not_include_secret() -> None:
    message = str(ProviderNotConfigured("sportmonks"))
    assert TEST_SPORTMONKS_TOKEN not in message
    assert PROCESS_TOKEN not in message
    assert redact_text(message, TEST_SPORTMONKS_TOKEN) == message


def test_cli_loads_dotenv_without_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = _write_env(tmp_path / ".env", token=TEST_SPORTMONKS_TOKEN)
    monkeypatch.delenv("SPORTMONKS_API_TOKEN", raising=False)
    monkeypatch.delenv("PREDICTA_INGESTION_SPORTMONKS_KEY", raising=False)
    monkeypatch.delenv("PREDICTA_INGESTION_ENABLE_LIVE", raising=False)
    monkeypatch.delenv("PREDICTA_INGESTION_DATA_MODE", raising=False)
    monkeypatch.setattr("predicta_ingestion.cli.load_local_env", lambda: load_local_env(env_file=env_file))
    captured: dict[str, Settings] = {}

    def fake_get_settings() -> Settings:
        settings = Settings(_env_file=None)
        captured["settings"] = settings
        raise RuntimeError("no-network")

    monkeypatch.setattr("predicta_ingestion.cli.get_settings", fake_get_settings)
    assert main(["ingest-history", "--league", "MLS", "--dry-run"]) == 1
    settings = captured["settings"]
    assert settings.sportmonks_key == TEST_SPORTMONKS_TOKEN
    assert settings.enable_live is True
    assert settings.data_mode == "live"
