# syntax=docker/dockerfile:1
# Build from the repository root:
#   docker build -f apps/api/Dockerfile .

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/usr/local/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system predicta \
    && useradd --system --gid predicta --create-home --home-dir /home/predicta predicta \
    && mkdir -p /data/football/datasets /data/football/registry /data/football/raw \
    && chown -R predicta:predicta /data/football

WORKDIR /app

COPY workers/ml /app/workers/ml
COPY workers/ingestion /app/workers/ingestion
COPY contracts /app/contracts
COPY apps/api /app/apps/api

RUN pip install --no-cache-dir \
        /app/workers/ml \
        /app/workers/ingestion \
        /app/apps/api \
    && chmod +x /app/apps/api/docker-entrypoint.sh

WORKDIR /app/apps/api
USER predicta

EXPOSE 8000
ENTRYPOINT ["/app/apps/api/docker-entrypoint.sh"]
