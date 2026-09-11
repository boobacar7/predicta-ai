# PREDICTA ingestion worker

Fondation DATA : adapters, raw immuable, validation, normalisation, résolution
d'identités et lectures point-in-time.

Le CLI charge `workers/ingestion/.env` tout seul (via python-dotenv), même si
la commande est lancée depuis la racine du monorepo. Les variables déjà
présentes dans le process restent prioritaires. Le token n'est jamais affiché.

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

Ligues V1 : `mls` (alias `MLS`), `premier-league`, `la-liga`, `bundesliga`, `serie-a`,
`ligue-1`, `champions-league`, ou `all`.

## Historique + dataset ML

La MLS est la compétition historique de référence. Le pipeline **découvre** les
saisons Sportmonks ; il n'en suppose aucune.

```bash
python -m predicta_ingestion ingest-history --league MLS --dry-run
python -m predicta_ingestion ingest-history \
  --league mls \
  --season 2024 \
  --date-from 2024-03-01 \
  --date-to 2024-11-30
python -m predicta_ingestion build-ml-dataset \
  --league MLS \
  --write-dataset ./var/football-1x2-history.json
```

Par défaut, la MLS ingère toutes les saisons découvertes. Les ligues européennes V1
sont limitées aux 3 saisons les plus récentes sauf `--all-seasons` ou `--season`.

Le rapport JSON liste saisons découvertes vs ingérées, volumes, quarantaine et
`ingestion_run_id`. Les chiffres canned dans `fixtures/sportmonks` ne sont pas
la couverture réelle du provider.

`--dry-run` ne persiste ni PostgreSQL ni le raw store.

Aucun modèle n'est entraîné ici. Voir [docs/ml-dataset.md](../../docs/ml-dataset.md).

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

## Ingestion cotes (The Odds API)

Opt-in, même flags live. La clé ne quitte pas `.env` :

```bash
PREDICTA_INGESTION_THE_ODDS_API_KEY=
# ou THE_ODDS_API_KEY=
python -m predicta_ingestion ingest-odds --league premier-league --dry-run
python -m predicta_ingestion ingest-odds --league all --as-of 2026-09-08T15:55:00Z
```

`--as-of` utilise l'endpoint historical documenté (plans payants, 10 crédits par
région et marché). Sans `--as-of`, l'endpoint courant `h2h` / région `eu`.
Aucun appel live dans la CI. Détail : [odds-provider.md](../../docs/data/odds-provider.md).

Les matchs Sportmonks doivent déjà exister pour lier les cotes. Le worker ne
calcule ni EV, ni edge, ni no-vig.

## Règles

- Les fixtures de `fixtures/mock` portent `data_mode: mock`.
- `fixtures/sportmonks` sont des réponses HTTP de test, jamais des faits produit.
- `PREDICTA_INGESTION_ENABLE_LIVE=false` refuse tout adapter live.
- PostgreSQL est celui de `apps/api`.
- Le Value Engine n'est pas recalculé ici.

Documentation : [data-strategy.md](../../docs/data-strategy.md),
[data-pipeline.md](../../docs/data-pipeline.md),
[data-providers.md](../../docs/data-providers.md),
[odds-provider.md](../../docs/data/odds-provider.md),
[ml-dataset.md](../../docs/ml-dataset.md).
