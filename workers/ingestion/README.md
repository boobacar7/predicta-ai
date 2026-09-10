# PREDICTA ingestion worker

Fondation DATA : adapters, raw immuable, validation, normalisation, résolution
d'identités et lectures point-in-time.

Aucun fournisseur payant n'est connecté. Le mode par défaut est `mock`.

## Démarrage

```bash
cd workers/ingestion
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest
```

Depuis la racine : `npm run verify:ingestion`.

## Règles

- Les fixtures de `fixtures/mock` portent `data_mode: mock`.
- `PREDICTA_INGESTION_ENABLE_LIVE=false` refuse tout adapter live.
- PostgreSQL est celui de `apps/api` (migration `0002_data_ingestion`).
- Le Value Engine n'est pas recalculé ici.

Documentation : [data-strategy.md](../../docs/data-strategy.md),
[data-pipeline.md](../../docs/data-pipeline.md),
[data-providers.md](../../docs/data-providers.md).
