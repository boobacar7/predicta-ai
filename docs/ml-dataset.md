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
  → PostgreSQL canonique + MemoryCanonicalSink
  → PointInTimeStore
  → build_ml_dataset(competition, seasons, cutoff_policy)
```

Commandes :

```bash
python -m predicta_ingestion ingest-history --league MLS --dry-run
python -m predicta_ingestion build-ml-dataset --league MLS --season 2024 --dry-run --write-dataset ./var/mls-1x2.json
```

`--dry-run` ne persiste ni PostgreSQL ni le filesystem raw.

## 2. MLS

La MLS (Sportmonks league id `779`, slug `mls`, alias `MLS`) est la compétition
historique de référence.

Le pipeline :

1. appelle `GET /leagues/779?include=country;seasons` ;
2. parse uniquement les saisons **présentes dans la réponse** ;
3. ingère chaque saison sélectionnée via `/fixtures/seasons/{id}` ;
4. rapporte `fetched / normalized / inserted / duplicate / quarantined`.

Les fichiers `workers/ingestion/fixtures/sportmonks/league_mls.json` sont des
**doubles de test**. Ils ne documentent pas la couverture réelle du plan Growth.
Les saisons réellement disponibles sont celles du rapport d'un run live.

## 3. Cutoff et anti-leakage

Pour un match au coup d'envoi `T` :

| Champ | Rôle |
| --- | --- |
| `event_at` | fait sportif (ici le kickoff) |
| `available_at` | moment où le fait est utilisable |
| `collected_at` | audit d'ingestion, jamais un cutoff d'entraînement |

Règle : une feature pour `T` n'utilise que des faits avec `available_at < T`
et `event_at < T`. Le match cible est exclu.

Forme récente (points, buts, domicile/extérieur) : uniquement des matchs dont
la **date UTC** est strictement antérieure à `T.date()`. Un match du 20/09/2024
n'entre pas dans les features du match PSG–Marseille du 20/09/2024.

Elo pré-match : parcours chronologique par `kickoff_at`. Le rating **avant** N
est celui obtenu après tous les matchs **précédant** N. Jamais un Elo calculé
sur toute la saison puis réinjecté.

Classement : uniquement `standings_as_of(league_id, T)`. Tant que Sportmonks
standings n'est pas ingéré, les ranks sont `null` (`standings_available=false`).

`available_at` des résultats terminés est une hypothèse (`kickoff + 3h`, bornée
par `collected_at`). Ce n'est pas un timestamp d'observation Sportmonks. Le
dataset ne prétend donc pas un PIT parfait sur l'instant exact de publication
du score.

## 4. Observation

Chaque ligne séparée **target** vs **features** :

- `match_id`, `event_at`, `home_team_id`, `away_team_id`
- `target` ∈ {`HOME`, `DRAW`, `AWAY`}
- `features` : forme, buts, goal-diff, matches joués, Elo pré-match, ranks (souvent null)
- `provider`, `raw_payload_id`, `data_mode`, `dataset_version`, `cutoff_policy`

Les matchs non terminés ou sans scores n'entrent pas dans le dataset étiqueté.
Aucun score n'est inventé pour compléter une saison.

## 5. Reproduire à une date T

1. Ingester l'historique (ou relire le sink mémoire d'un run).
2. `PointInTimeStore.features_for_match(match_id, T)` refuse `T > kickoff`.
3. `build_ml_dataset(..., cutoff_policy="pre_kickoff")` applique les mêmes bornes
   à toutes les observations.
4. Enregistrer `dataset_version=football-1x2-history-0.1` et le rapport d'ingestion.

Les tests `test_ml_dataset.py` démontrent qu'un résultat postérieur ou du même
jour calendaire n'entre pas dans les features de forme.
