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
  → reconstruct_pre_match_elo (timeline globale)
  → build_ml_dataset(competition, seasons, cutoff_policy)
  → JSON + Parquet + rapport qualité
```

Commandes :

```bash
python -m predicta_ingestion build-ml-dataset \
  --league all \
  --write-dataset ./var/football-1x2-history.json
```

`build-ml-dataset` lit PostgreSQL. Il n'appelle pas Sportmonks et n'entraîne rien.
`--league all` construit le dataset 1X2 sur les 7 compétitions V1 déjà ingérées.

## 2. Périmètre

Compétitions (union chronologique, un seul Elo) :

- Premier League
- Ligue 1
- La Liga
- Bundesliga
- Serie A
- Champions League
- MLS

Seuls les matchs **terminés** avec scores sont étiquetés. Les matchs futurs
`scheduled` restent dans le canonique et sont rejetés (`not_finished`). Aucune
ligne de standings n'entre dans les features.

## 3. Cutoff et anti-leakage

Pour un match au coup d'envoi `T` :

| Champ | Rôle |
| --- | --- |
| `event_at` | fait sportif (kickoff) |
| `available_at` | moment où le fait est utilisable |
| `collected_at` | audit d'ingestion, jamais un cutoff d'entraînement |

Règle : une feature pour `T` n'utilise que des faits avec `available_at < T`
et `event_at < T`. Le match cible est exclu de ses propres rolling windows et du H2H.

Forme récente (fenêtres 5 et 10) : matchs PIT-valides antérieurs uniquement,
toutes compétitions. Un match dont le résultat n'est pas encore
`available_at < T` n'entre pas, même s'il a déjà kickoff.

### Elo global

Elo pré-match : **global inter-compétitions**, clé `canonical_team_id`.
Un résultat Ligue 1 met à jour le même club qui joue ensuite en Champions League.

Paramètres : `initial=1500`, `K=20`, avantage domicile `+80`, échelle 400.

Reconstruction :

1. snapshot Elo **avant** le match, au `event_at` ;
2. mise à jour **uniquement** à `available_at` ;
3. aucun résultat n'influence un match antérieur ;
4. un match futur n'entre pas dans la marche.

Timestamps identiques : les événements sont triés par
`(timestamp, kind, match_id)` avec snapshot `kind=0` puis update `kind=1`.
Deux matchs au même instant voient donc tous les deux les ratings pré-match.

Si `available_at` du match A est **supérieur ou égal** au kickoff du match B,
le résultat de A **ne doit pas** changer l'Elo pré-match de B. Quand les deux
instants sont égaux, le snapshot de B (`kind=0`) s'exécute avant l'update de A
(`kind=1`). Le cutoff Elo est donc `available_at < T`, pas `<=`.

H2H : confrontations antérieures au kickoff cible. `h2h_available=1` si
au moins 2 matchs PIT-valides.

Classements : **non utilisés**. Un standing saisonnier courant n'est pas
Point-in-Time. `standings_available` reste `false`.

`available_at` des résultats terminés est une hypothèse (`kickoff + 3h`, bornée
par `collected_at`). Ce n'est pas un timestamp d'observation Sportmonks.

## 4. Observation

Chaque ligne sépare **identité / target** vs **features** :

Identité :

- `match_id`, `competition_id`, `competition_name`, `season_id`, `season`
- `event_at`, `home_team_id`, `away_team_id`

Target :

- `home_win` / `draw` / `away_win` ∈ {0, 1}
- `target` ∈ {HOME, DRAW, AWAY}

Features (`feature_schema_version` = `football-1x2-features-0.3`) :

- Elo : `home_elo_pre`, `away_elo_pre`, `elo_diff`, `elo_available`
- Forme : `home_form_5/10`, `away_form_5/10` + flags `*_available`
- Buts 5/10 for/against des deux côtés
- H2H : `h2h_home_wins`, `h2h_draws`, `h2h_away_wins`, `h2h_available`, `h2h_matches`
- Volume : `home_matches_played`, `away_matches_played`

Métadonnées dataset : `dataset_version`, `feature_schema_version`, `code_version`,
`cutoff_policy`, `source`, `generated_at`, nombre de lignes / features / rejets.

Les matchs non terminés ou sans scores sont **rejetés** (raison dans le rapport),
pas étiquetés. Aucun score n'est inventé.

Version : `football-1x2-history-0.3`.

## 5. Artefacts

`build-ml-dataset` écrit, à côté du JSON :

- `{stem}.parquet` : table aplatie reproductible
- `{stem}.quality.json` : lignes, rejets, doublons, nulls, distribution 1/X/2,
  période, équipes / compétitions / saisons, stats Elo, ordre chronologique,
  anti-leakage, H2H, timestamps identiques

Les tests `test_ml_dataset.py` couvrent Elo sans fuite, rolling, H2H,
`available_at`, timestamps identiques, club multi-compétitions,
`canonical_team_id` global, exclusion des matchs futurs, reproductibilité.

## 6. Snapshot live (0.3)

Construit le 2026-09-10 depuis PostgreSQL, sans re-fetch Sportmonks :

- 5729 lignes (matchs terminés)
- 27 features
- 1893 rejets, tous `not_finished` (1890 scheduled + 3 autres statuts)
- 1/X/2 : 2546 / 1389 / 1794
- période : 2024-02-22 → 2026-09-10 UTC
- 263 équipes, 7 compétitions, 6 saisons
- Elo pré-match : home mean 1513.13 (min 1332.08, max 1793.02)
- 0 null, 0 doublon, anti-leakage OK, standings non utilisés

Artefacts locaux (gitignorés) : `workers/ingestion/var/football-1x2-history.json`,
`.parquet`, `.quality.json`.
