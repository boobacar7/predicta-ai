from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import yaml
from app.core.config import Settings

REPO = Path(__file__).resolve().parents[3]
STAGING_COMPOSE = REPO / "infra" / "containers" / "compose.staging.yml"
STAGING_ENV = REPO / "infra" / "containers" / ".env.staging.example"
PREPARE_SCRIPT = REPO / "infra" / "containers" / "prepare-staging-football-data.sh"
ENTRYPOINT = REPO / "apps" / "api" / "docker-entrypoint.sh"
API_DOCKERFILE = REPO / "apps" / "api" / "Dockerfile"
DOCKERIGNORE = REPO / ".dockerignore"

CONTAINER_DATASET = Path("/data/football/datasets/football-1x2-history.parquet")
CONTAINER_REGISTRY = Path("/data/football/registry")
CONTAINER_ARTEFACT = CONTAINER_REGISTRY / "football-elo-v1-candidate" / "artefact.joblib"


def test_staging_compose_keeps_postgres_off_the_host() -> None:
    text = STAGING_COMPOSE.read_text(encoding="utf-8")
    assert "5432:5432" not in text
    assert "6379:6379" not in text
    assert "apps/api/Dockerfile" in text
    assert "context: ../../apps/web" in text
    assert "PREDICTA_API_FOOTBALL_REGISTRY_DIR" in text
    assert "football-elo-v1-candidate" in text
    assert "PREDICTA_API_AUTH_BYPASS: ${PREDICTA_API_AUTH_BYPASS:-false}" in text
    assert "NEXT_PUBLIC_PREDICTA_AUTH_BYPASS: ${PREDICTA_API_AUTH_BYPASS:-false}" in text
    assert 'PREDICTA_API_AUTH_BYPASS: "false"' not in text


def test_staging_env_example_is_fail_closed_and_secret_free() -> None:
    text = STAGING_ENV.read_text(encoding="utf-8")
    assert "PREDICTA_API_ENV=staging" in text
    assert "PREDICTA_API_REPOSITORY=sql" in text
    assert "PREDICTA_API_DATA_MODE=live" in text
    assert "PREDICTA_API_AUTH_BYPASS=false" in text
    assert "NEXT_PUBLIC_PREDICTA_AUTH_BYPASS=false" in text
    assert "NEXT_PUBLIC_PREDICTA_ENV=staging" in text
    assert "NEXT_PUBLIC_PREDICTA_DATA_SOURCE=http" in text
    assert "PREDICTA_API_FOOTBALL_REGISTRY_DIR=" in text
    assert "PREDICTA_API_FOOTBALL_DATASET_PATH=" in text
    assert "PREDICTA_API_FOOTBALL_MODEL_VERSION=football-elo-v1-candidate" in text
    assert "sk_live" not in text
    assert "SPORTMONKS_API_TOKEN" not in text
    assert "THE_ODDS_API_KEY" not in text
    assert "BEGIN PRIVATE" not in text
    assert "ghp_" not in text
    assert "aws_secret" not in text.lower()


def test_staging_compose_bind_mounts_worker_var_into_api_data_paths() -> None:
    compose = yaml.safe_load(STAGING_COMPOSE.read_text(encoding="utf-8"))
    api = compose["services"]["api"]
    env = api["environment"]
    volumes = api["volumes"]

    assert env["PREDICTA_API_FOOTBALL_DATASET_PATH"] == (
        "${PREDICTA_API_FOOTBALL_DATASET_PATH:-/data/football/datasets/football-1x2-history.parquet}"
    )
    assert env["PREDICTA_API_FOOTBALL_REGISTRY_DIR"] == (
        "${PREDICTA_API_FOOTBALL_REGISTRY_DIR:-/data/football/registry}"
    )
    assert env["PREDICTA_API_FOOTBALL_MODEL_VERSION"] == "football-elo-v1-candidate"

    assert (
        "${PREDICTA_FOOTBALL_DATASETS_HOST:-../../workers/ingestion/var}:/data/football/datasets:ro"
        in volumes
    )
    assert (
        "${PREDICTA_FOOTBALL_REGISTRY_HOST:-../../workers/ml/var/registry}:/data/football/registry:ro"
        in volumes
    )
    assert (
        "${PREDICTA_FOOTBALL_RAW_HOST:-../../workers/ingestion/var/raw}:/data/football/raw:ro"
        in volumes
    )
    ingestion_volumes = compose["services"]["ingestion"]["volumes"]
    assert (
        "${PREDICTA_FOOTBALL_DATASETS_HOST:-../../workers/ingestion/var}:/data/football/datasets"
        in ingestion_volumes
    )
    assert (
        "${PREDICTA_FOOTBALL_REGISTRY_HOST:-../../workers/ml/var/registry}:/data/football/registry:ro"
        in ingestion_volumes
    )
    assert "${PREDICTA_FOOTBALL_DATA_DIR:-../../var/football}:/data/football:ro" not in volumes
    assert "**/var" in DOCKERIGNORE.read_text(encoding="utf-8")
    dockerfile = API_DOCKERFILE.read_text(encoding="utf-8")
    assert "/data/football/datasets" in dockerfile
    assert "/data/football/registry" in dockerfile


def test_staging_env_example_points_host_sources_at_worker_var() -> None:
    text = STAGING_ENV.read_text(encoding="utf-8")
    assert "PREDICTA_FOOTBALL_DATASETS_HOST=../../workers/ingestion/var" in text
    assert "PREDICTA_FOOTBALL_REGISTRY_HOST=../../workers/ml/var/registry" in text
    assert "PREDICTA_API_FOOTBALL_DATASET_PATH=/data/football/datasets/football-1x2-history.parquet" in text
    assert "PREDICTA_API_FOOTBALL_REGISTRY_DIR=/data/football/registry" in text
    assignments = [line for line in text.splitlines() if line and not line.lstrip().startswith("#")]
    assert all(not item.startswith("PREDICTA_FOOTBALL_DATA_DIR=") for item in assignments)
    assert "workers/ingestion/var/football-1x2-history.parquet" in text


def test_staging_settings_use_the_same_paths_as_compose() -> None:
    settings = Settings(
        _env_file=None,
        env="staging",
        repository="sql",
        data_mode="live",
        football_registry_dir="/data/football/registry",
        football_dataset_path="/data/football/datasets/football-1x2-history.parquet",
    )
    assert settings.football_dataset_path == CONTAINER_DATASET
    assert settings.football_registry_dir == CONTAINER_REGISTRY
    assert settings.football_registry_dir / settings.football_model_version / "artefact.joblib" == CONTAINER_ARTEFACT
    assert settings.football_dataset_path.is_file() is False
    assert CONTAINER_ARTEFACT.is_file() is False


def test_entrypoint_reports_missing_dataset_and_artefact_without_mocking() -> None:
    text = ENTRYPOINT.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh\n")
    assert "PREDICTA_API_FOOTBALL_DATASET_PATH" in text
    assert "PREDICTA_API_FOOTBALL_REGISTRY_DIR" in text
    assert "football-elo-v1-candidate" in text
    assert "MISSING" in text
    assert "never mock" in text
    assert "alembic upgrade head" in text
    assert "uvicorn" in text


def test_prepare_script_copies_worker_var_into_isolated_layout(tmp_path: Path) -> None:
    src_dataset = tmp_path / "workers" / "ingestion" / "var" / "football-1x2-history.parquet"
    src_dataset.parent.mkdir(parents=True)
    src_dataset.write_bytes(b"parquet-placeholder")
    src_registry = tmp_path / "workers" / "ml" / "var" / "registry" / "football-elo-v1-candidate"
    src_registry.mkdir(parents=True)
    (src_registry / "artefact.joblib").write_bytes(b"joblib-placeholder")
    (src_registry / "registry.json").write_text("{}", encoding="utf-8")
    dest = tmp_path / "var" / "football"
    env = os.environ.copy()
    env["PREDICTA_FOOTBALL_DATASET_SOURCE"] = str(src_dataset)
    env["PREDICTA_FOOTBALL_PREMATCH_SOURCE"] = str(tmp_path / "missing-prematch.parquet")
    env["PREDICTA_FOOTBALL_REGISTRY_SOURCE"] = str(src_registry)
    env["PREDICTA_FOOTBALL_DATA_DIR"] = str(dest)
    subprocess.run([str(PREPARE_SCRIPT)], check=True, env=env, capture_output=True, text=True)
    copied = dest / "datasets" / "football-1x2-history.parquet"
    artefact = dest / "registry" / "football-elo-v1-candidate" / "artefact.joblib"
    assert copied.read_bytes() == b"parquet-placeholder"
    assert artefact.read_bytes() == b"joblib-placeholder"
    assert (dest / "datasets" / "football-1x2-prematch.parquet").is_file() is False


def test_prepare_script_fails_when_parquet_is_missing(tmp_path: Path) -> None:
    src_registry = tmp_path / "registry" / "football-elo-v1-candidate"
    src_registry.mkdir(parents=True)
    (src_registry / "artefact.joblib").write_bytes(b"joblib-placeholder")
    env = os.environ.copy()
    env["PREDICTA_FOOTBALL_DATASET_SOURCE"] = str(tmp_path / "missing.parquet")
    env["PREDICTA_FOOTBALL_REGISTRY_SOURCE"] = str(src_registry)
    env["PREDICTA_FOOTBALL_DATA_DIR"] = str(tmp_path / "dest")
    result = subprocess.run([str(PREPARE_SCRIPT)], env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert "missing PIT parquet" in result.stderr
    assert not (tmp_path / "dest" / "datasets" / "football-1x2-history.parquet").is_file()


def test_prepare_script_is_executable() -> None:
    mode = PREPARE_SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR
