#!/bin/sh
set -eu

dataset="${PREDICTA_API_FOOTBALL_DATASET_PATH:-/data/football/datasets/football-1x2-history.parquet}"
registry="${PREDICTA_API_FOOTBALL_REGISTRY_DIR:-/data/football/registry}"
model="${PREDICTA_API_FOOTBALL_MODEL_VERSION:-football-elo-v1-candidate}"
artefact="$registry/$model/artefact.joblib"

if [ -f "$dataset" ]; then
  echo "predicta-api: PIT dataset present at $dataset"
else
  echo "predicta-api: PIT dataset MISSING at $dataset (predictions return 422, never mock)"
fi
if [ -f "$artefact" ]; then
  echo "predicta-api: candidate artefact present at $artefact"
else
  echo "predicta-api: candidate artefact MISSING at $artefact (predictions return 503, never mock)"
fi

if [ "${PREDICTA_API_MIGRATE_ON_START:-true}" = "true" ]; then
  echo "predicta-api: alembic upgrade head"
  alembic upgrade head
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PREDICTA_API_PORT:-8000}"
