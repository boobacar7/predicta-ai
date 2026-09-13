# syntax=docker/dockerfile:1
# Build from workers/ingestion:
#   docker build -f workers/ingestion/Dockerfile workers/ingestion

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system predicta \
    && useradd --system --gid predicta --create-home --home-dir /home/predicta predicta

WORKDIR /app
COPY . /app/workers/ingestion
RUN pip install --no-cache-dir /app/workers/ingestion

USER predicta
WORKDIR /app/workers/ingestion
ENTRYPOINT ["python", "-m", "predicta_ingestion"]
CMD ["--help"]
