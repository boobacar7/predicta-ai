# PREDICTA ingestion worker

Fondation DATA : adapters, raw immuable, validation, normalisation, résolution
d'identités et lectures point-in-time.

Le mode par défaut est `mock`. L'ingestion Sportmonks réelle est opt-in.

## Démarrage (mock / tests)

```bash
cd workers/ingestion
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest
```

Depuis la racine : `npm run verify:ingestion`.

## Ingestion Football réelle (Sportmonks Growth)

Aucun token n'est livré avec le dépôt. Créer un compte Sportmonks, plan Growth,
puis copier le token **uniquement** dans `workers/ingestion/.env` (fichier gitignoré).

```bash
cp .env.example .env
# Éditer .env :
# SPORTMONKS_API_TOKEN=<token local>
# PREDICTA_INGESTION_ENABLE_LIVE=true
# PREDICTA_INGESTION_DATA_MODE=live
```

Appliquer les migrations API sur la même base PostgreSQL (`0002_data_ingestion`).

```bash
cd workers/ingestion
python -m predicta_ingestion ingest-football \
  --league premier-league \
  --date-from 2026-08-01 \
  --date-to 2026-09-10 \
  --dry-run
```

`--dry-run` fetch / valide / normalise **sans** écrire PostgreSQL ni le store raw.
Retirer `--dry-run` pour persister.

Ligues V1 : `premier-league`, `la-liga`, `bundesliga`, `serie-a`, `ligue-1`,
`champions-league`, ou `all`.

Données V1 : compétitions, équipes, fixtures (statut, coup d'envoi UTC,
domicile/extérieur, score final si terminé). Pas de stats, joueurs, blessures,
lineups, événements, xG ni cotes.

Vérifier qu'un run a utilisé Sportmonks :

- `data_mode` du rapport = `live`
- `provider` = `sportmonks`
- fichiers raw sous `var/raw/live/sportmonks/`
- lignes `raw_payloads` / `matches` avec `data_mode=live` et `source=sportmonks`

Si `ENABLE_LIVE=false` ou token absent, le processus échoue. Il n'y a pas de
bascule silencieuse vers les fixtures mock.

## Règles

- Les fixtures de `fixtures/mock` portent `data_mode: mock`.
- `fixtures/sportmonks` sont des réponses HTTP de test, jamais des faits produit.
- `PREDICTA_INGESTION_ENABLE_LIVE=false` refuse tout adapter live.
- PostgreSQL est celui de `apps/api`.
- Le Value Engine n'est pas recalculé ici.

Documentation : [data-strategy.md](../../docs/data-strategy.md),
[data-pipeline.md](../../docs/data-pipeline.md),
[data-providers.md](../../docs/data-providers.md).
