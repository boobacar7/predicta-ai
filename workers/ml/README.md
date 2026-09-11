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
python -m predicta_ml oos-backtest --dataset ../ingestion/var/football-1x2-history.parquet
```

`oos-backtest` scores the frozen `football-elo-v1-candidate` on the true
temporal OOS window (`event_at >= 2026-07-01`). It does not retune the model,
thresholds, or Value Engine, and it does not promote the candidate.

To reuse persisted historical odds and the production Value Engine (zero Odds
API credits):

```bash
cd apps/api
python -m app.backtesting production-oos
```

Reports:

- `reports/football-elo-v1-candidate.provenance.json`
- `reports/production-oos-backtest.json`

Protocol: [production-oos-protocol.md](../../docs/ml/production-oos-protocol.md).
Results: [production-oos-backtest.md](../../docs/ml/production-oos-backtest.md).

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
[model card Elo](../../docs/ml/model-card-football-elo.md),
[OOS protocol](../../docs/ml/production-oos-protocol.md),
[OOS backtest](../../docs/ml/production-oos-backtest.md).
