from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
STAGING_COMPOSE = REPO / "infra" / "containers" / "compose.staging.yml"
STAGING_ENV = REPO / "infra" / "containers" / ".env.staging.example"


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
