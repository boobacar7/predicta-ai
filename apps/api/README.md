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

Auth Private Beta : sessions opaques (`HttpOnly; SameSite=Lax`, `Secure` en staging/prod), hash SHA-256 côté serveur, mots de passe Argon2id. Pas de JWT. `PREDICTA_API_AUTH_BYPASS` est refusé en staging/production. `/docs` est désactivé dans ces environnements. Provisionner un invité :

```bash
PREDICTA_API_BOOTSTRAP_PASSWORD=... python -m app.auth.provision beta@example.com
```

Probabilités football 1X2 du candidat Elo : `GET /api/v1/football/predictions/{match_id}`.
Analyse PIT Odds + Value football 1X2 : `GET /api/v1/football/value/{match_id}`.
AI Picks statistiques et déterministes : `GET /api/v1/football/ai-picks`.
AI Analyst football : `GET /api/v1/football/ai-analyst/{match_id}`.
Le narrator par défaut est déterministe. `PREDICTA_API_ANALYST_NARRATOR=llm`
active `LLMAnalystProvider` (mock-explainer, grounded, fallback déterministe).
Le DTO frontend `GET /api/v1/matches/{match_id}/prediction` n'est pas modifié.
