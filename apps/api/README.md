# PREDICTA API

FastAPI modular monolith implementing [`contracts/openapi.yaml`](../../contracts/openapi.yaml).

## Démarrage

```bash
cd apps/api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Depuis la racine : `npm run dev:api`.

Le mode par défaut est `PREDICTA_API_REPOSITORY=mock` et `PREDICTA_API_DATA_MODE=mock`. Les payloads portent `data_mode: mock` et ne doivent pas être présentés comme des données live.

## PostgreSQL et Redis

```bash
docker compose -f infra/containers/docker-compose.yml up -d
cd apps/api
alembic upgrade head
```

`PREDICTA_API_REPOSITORY=sql` active les repositories SQL. Sans ingestion, les catalogues et matchs restent vides : le backend ne fabrique pas d'événements sportifs réels.

## Vérifications

```bash
cd apps/api
pytest
ruff check app tests
mypy
```

Depuis la racine : `npm run verify:api`.

## Endpoints

Préfixe public : `/api/v1`. Santé opérationnelle hors contrat : `GET /health`, `GET /ready`.

Probabilités football 1X2 du candidat Elo : `GET /api/v1/football/predictions/{match_id}`.
Analyse PIT Odds + Value football 1X2 : `GET /api/v1/football/value/{match_id}`.
Le DTO frontend `GET /api/v1/matches/{match_id}/prediction` n'est pas modifié.
