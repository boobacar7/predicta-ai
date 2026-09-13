#!/usr/bin/env bash
# Copy gitignored frozen football artefacts into the isolated staging tree.
# Default dest: <repo>/var/football/{datasets,registry,raw}
#
# Laptop source of truth (not committed):
#   workers/ingestion/var/football-1x2-history.parquet
#   workers/ml/var/registry/football-elo-v1-candidate/
#
# Does not bake parquet/joblib into Git or the API image. Missing sources fail
# honestly (exit 1). Prematch parquet is optional.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

normalize_repo_path() {
  local value="$1"
  if [[ "$value" == /* ]]; then
    printf '%s\n' "$value"
    return
  fi
  # Compose-file-relative paths from infra/containers/
  if [[ "$value" == ../../* ]]; then
    printf '%s\n' "$ROOT/${value#../../}"
    return
  fi
  printf '%s\n' "$ROOT/${value#./}"
}

SRC_DATASET="$(normalize_repo_path "${PREDICTA_FOOTBALL_DATASET_SOURCE:-workers/ingestion/var/football-1x2-history.parquet}")"
SRC_PREMATCH="$(normalize_repo_path "${PREDICTA_FOOTBALL_PREMATCH_SOURCE:-workers/ingestion/var/football-1x2-prematch.parquet}")"
SRC_REGISTRY="$(normalize_repo_path "${PREDICTA_FOOTBALL_REGISTRY_SOURCE:-workers/ml/var/registry/football-elo-v1-candidate}")"
DEST_ROOT="$(normalize_repo_path "${PREDICTA_FOOTBALL_DATA_DIR:-var/football}")"

DEST_DATASETS="$DEST_ROOT/datasets"
DEST_REGISTRY="$DEST_ROOT/registry"
DEST_RAW="$DEST_ROOT/raw"

mkdir -p "$DEST_DATASETS" "$DEST_REGISTRY" "$DEST_RAW"

if [[ ! -f "$SRC_DATASET" ]]; then
  echo "prepare-staging-football-data: missing PIT parquet: $SRC_DATASET" >&2
  echo "Copy workers/ingestion/var/football-1x2-history.parquet onto this machine first." >&2
  exit 1
fi

if [[ ! -d "$SRC_REGISTRY" ]]; then
  echo "prepare-staging-football-data: missing candidate registry dir: $SRC_REGISTRY" >&2
  echo "Copy workers/ml/var/registry/football-elo-v1-candidate/ onto this machine first." >&2
  exit 1
fi

if [[ ! -f "$SRC_REGISTRY/artefact.joblib" ]]; then
  echo "prepare-staging-football-data: missing artefact.joblib in $SRC_REGISTRY" >&2
  exit 1
fi

cp -f "$SRC_DATASET" "$DEST_DATASETS/football-1x2-history.parquet"
if [[ -f "$SRC_PREMATCH" ]]; then
  cp -f "$SRC_PREMATCH" "$DEST_DATASETS/football-1x2-prematch.parquet"
fi

rm -rf "$DEST_REGISTRY/football-elo-v1-candidate"
cp -R "$SRC_REGISTRY" "$DEST_REGISTRY/football-elo-v1-candidate"

echo "prepare-staging-football-data: wrote"
echo "  $DEST_DATASETS/football-1x2-history.parquet"
echo "  $DEST_REGISTRY/football-elo-v1-candidate/"
echo "Mount with compose (isolated tree):"
echo "  PREDICTA_FOOTBALL_DATASETS_HOST=$DEST_DATASETS"
echo "  PREDICTA_FOOTBALL_REGISTRY_HOST=$DEST_REGISTRY"
echo "  PREDICTA_FOOTBALL_RAW_HOST=$DEST_RAW"
