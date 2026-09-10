# Dataset ML football (point-in-time)

Cette couche prépare un dataset **reproductible** pour l'agent ML. Elle n'entraîne
aucun modèle, ne calcule aucune probabilité 1X2, aucun ROI, aucun Poisson / Dixon-Coles /
XGBoost / LightGBM.

## 1. Flux

```text
Sportmonks
  → ingest-history (saisons découvertes, pas inventées)
  → raw immuable
  → validation / normalisation / quarantaine
  → PostgreSQL canonique
  → load_memory_sink (lecture SQL, pas de re-fetch)
  → PointInTimeStore
  → build_ml_dataset(competition, seasons, cutoff_policy)
  → JSON + Parquet + rapport qualité
```

Commandes :

```bash
python -m predicta_ingestion ingest-history --league MLS
python -m predicta_ingestion build-ml-dataset \
  --league MLS \
  --write-dataset ./var/football-1x2-history.json
```

`build-ml-dataset` lit PostgreSQL. Il n'appelle pas Sportmonks et n'entraîne rien.
`--dry-run` sur `ingest-history` ne persiste ni PostgreSQL ni le filesystem raw.

## 2. MLS

La MLS (Sportmonks league id `779`, slug `mls`, alias `MLS`) est la compétition
historique de référence.

Les saisons réellement disponibles sont celles du rapport d'un run live, pas
les fixtures de test.

## 3. Cutoff et anti-leakage

Pour un match au coup d'envoi `T` :

| Champ | Rôle |
| --- | --- |
| `event_at` | fait sportif (kickoff) |
| `available_at` | moment où le fait est utilisable |
| `collected_at` | audit d'ingestion, jamais un cutoff d'entraînement |

Règle : une feature pour `T` n'utilise que des faits avec `available_at < T`
et `event_at < T`. Le match cible est exclu.

Forme récente (fenêtres 5 et 10) : matchs PIT-valides uniquement. Un match dont
le résultat n'est pas encore `available_at < T` n'entre pas, même s'il a déjà
kickoff.

Elo pré-match : snapshot au kickoff, mise à jour **uniquement** à `available_at`.
Paramètres : `initial=1500`, `K=20`, avantage domicile `+80`, échelle 400.

H2H : confrontations antérieures entre les deux clubs. `h2h_available=1` si
au moins 2 matchs PIT-valides.

Classement : uniquement `standings_as_of`. Tant que Sportmonks standings n'est
pas ingéré, `home_standing_rank` / `away_standing_rank` restent `null`.

`available_at` des résultats terminés est une hypothèse (`kickoff + 3h`, bornée
par `collected_at`). Ce n'est pas un timestamp d'observation Sportmonks.

## 4. Observation

Chaque ligne sépare **target** vs **features** :

- `match_id`, `event_at`, `home_team_id`, `away_team_id`, `competition`, `season`
- `home_win` / `draw` / `away_win` ∈ {0, 1} (one-hot) et `target` ∈ {HOME, DRAW, AWAY}
- `features` : forme 5/10, buts prior/5/10, Elo, diff Elo, H2H, flags `*_available`
- `provider`, `raw_payload_id`, `data_mode`, `dataset_version`, `cutoff_policy`

Les matchs non terminés ou sans scores sont **rejetés** (raison dans le rapport),
pas étiquetés. Aucun score n'est inventé.

Version : `football-1x2-history-0.2`.

## 5. Artefacts

`build-ml-dataset` écrit, à côté du JSON :

- `{stem}.parquet` : table aplatie reproductible
- `{stem}.quality.json` : doublons, nulls, ordre temporel, flags de disponibilité,
  compteurs de rejet, paramètres Elo, `code_version`

Les tests `test_ml_dataset.py` couvrent anti-leakage, Elo différé, rolling 5/10 et H2H.
