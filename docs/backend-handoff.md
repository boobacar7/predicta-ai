# Handoff Backend

État de `apps/api` après la passe de l'agent Backend. Les décisions
structurantes sont dans [ADR 0003](adr/0003-backend-foundation.md).

## Démarrage

```bash
cd apps/api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

PostgreSQL / Redis locaux :

```bash
docker compose -f infra/containers/docker-compose.yml up -d
cd apps/api && alembic upgrade head
```

Le frontend bascule une ressource :

```bash
NEXT_PUBLIC_PREDICTA_DATA_SOURCE=http
NEXT_PUBLIC_PREDICTA_API_BASE_URL=http://localhost:8000/api/v1
```

## Architecture

```text
apps/api/
├── app/
│   ├── api/           routes FastAPI, pagination, enveloppe
│   ├── core/          config, erreurs RFC 9457, middleware, container
│   ├── domain/        Value Engine (Decimal)
│   ├── db/            SQLAlchemy + session
│   ├── fixtures/      jeu mock isolé
│   ├── repositories/  protocols, mock, sql (vide)
│   ├── schemas/       Pydantic aligné OpenAPI
│   └── services/      cas d'usage
├── alembic/versions/0001_initial.py
└── tests/
```

Flux : `route → service → repository`. Aucune requête SQL dans une route.

## Endpoints

Tous les chemins OpenAPI `/api/v1/*` listés dans `docs/api-contract.md`, plus
`GET /health` et `GET /ready`.

## Non fait volontairement

- ingestion provider, scraping, ML, LLM réel, auth, paiement
- cache Redis actif (URL optionnelle seulement)
- mapping SQL complet des fixtures vers les tables
- connexion d'un fournisseur sportif payant (fondation DATA : adapters mock + schéma, voir `docs/data-strategy.md`)
