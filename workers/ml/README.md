# PREDICTA ML worker

Premier pipeline Football 1X2. Il consomme exclusivement le dataset figé
`football-1x2-history-0.3` produit par l'ingestion. Il n'appelle pas Sportmonks,
ne joint pas PostgreSQL, n'entraîne rien côté Data, et n'est pas branché au
backend ni au Value Engine.

## Démarrage

```bash
cd workers/ml
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Depuis la racine : `npm run verify:ml`.

## Dataset

Par défaut : `workers/ingestion/var/football-1x2-history.parquet`.

```bash
python -m predicta_ml audit --dataset ../ingestion/var/football-1x2-history.parquet
python -m predicta_ml benchmark --dataset ../ingestion/var/football-1x2-history.parquet
python -m predicta_ml validate-elo --dataset ../ingestion/var/football-1x2-history.parquet
```

Le benchmark écrit :

- `var/registry/football-1x2-model-0.1/` (carte JSON + artefact joblib, gitignoré)
- `var/reports/football-1x2-model-0.1.benchmark.json`

`validate-elo` écrit le candidat **non production** :

- `var/registry/football-elo-v1-candidate/` (joblib rechargeable, gitignoré)
- `reports/football-elo-v1-candidate.registry.json`
- `reports/football-elo-v1-candidate.summary.json`

Aucun split aléatoire. Walk-forward expanding, test final à partir de
`2026-07-01`. Seed : `42`.

Documentation : [architecture](../../docs/architecture.md),
[dataset 0.3](../../docs/ml-dataset.md),
[benchmark 1X2](../../docs/ml-football-1x2.md),
[validation Elo](../../docs/ml/elo-candidate-validation.md),
[model card Elo](../../docs/ml/model-card-football-elo.md).
