#!/bin/sh
set -eu

if [ "${PREDICTA_API_MIGRATE_ON_START:-true}" = "true" ]; then
  echo "predicta-api: alembic upgrade head"
  alembic upgrade head
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PREDICTA_API_PORT:-8000}"
