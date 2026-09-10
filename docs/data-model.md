# Modèle de données

Ce document décrit le schéma conceptuel persisté par `apps/api`. Il n'autorise
pas l'invention de faits sportifs : une table vide signifie une absence de
données, jamais un zéro métier.

Le worker `workers/ingestion` écrit dans ce schéma. Il n'introduit pas une
seconde base.

## Périmètre

Inclus (fondation backend + DATA) :

- catalogue : `sports`, `leagues`, `teams`, `players`
- mapping d'identités provider : `provider_entity_maps`
- événements : `matches`, `match_events`
- statistiques snapshots : `match_statistics`, `team_statistics`, `player_statistics`
- cotes append-only : `odds_snapshots`, `odds_selections`
- classements snapshots : `standings`
- blessures : `injuries`
- compositions : `lineups`, `lineup_players`
- raw metadata : `raw_payloads`
- runs : `ingestion_runs`
- quarantaine : `quarantine_records`
- registre de modèles : `model_versions`, `model_metrics`
- prédictions : `predictions`, `prediction_outcomes`, `prediction_factors`
- signaux publiés : `published_picks`
- analyses : `ai_analyses`

Exclus jusqu'à la phase 10 :

- `users`, `subscriptions`, `user_favorites`, `user_bets`

Les **bodies** provider restent hors PostgreSQL (store objet / filesystem).
`raw_payloads` ne conserve que métadonnées, checksum et URI.

## Identifiants

Les identifiants publics sont des chaînes stables (`Identifier`, max 128). Les
IDs provider ne remplacent jamais l'ID canonique ; ils passent par
`provider_entity_maps`.

## Temps

Tous les timestamps persistés sont UTC.

| Champ | Rôle |
| --- | --- |
| `kickoff_at` / `event_at` | temps du fait sportif |
| `available_at` | temps auquel le fait était utilisable (cutoff ML) |
| `collected_at` | temps de collecte PREDICTA (audit) |
| `observed_at` | observation exposée API ; aligné sur `available_at` à l'ingestion |
| `cutoff_at` | frontière d'une prédiction, jamais postérieure au coup d'envoi |

## Provenance des observations

Les tables de faits DATA portent autant que possible :

- `provider`, `source`, `data_mode`
- `collected_at`, `available_at`
- `freshness`, `availability`
- `raw_payload_id` nullable

`data_mode=mock` ne doit pas être promu en production.

## Cotes et prédictions

Les snapshots de cotes sont append-only. Une évaluation value n'est pas une
table de faits séparée en v1 : elle est calculée de façon déterministe à partir
d'une prédiction calibrée et d'un snapshot, avec `formula_version`.

L'ingestion n'écrit pas implied / no-vig / edge / EV.

Les probabilités sont stockées en `Numeric` borné `[0, 1]`. Les cotes
décimales respectent `> 1`. `theoretical_max_drawdown` est borné `[-1, 0]`.

## Qualité

Les observations métier portent un statut d'availability. Une statistique
manquante est `NULL` plus `availability=unavailable`, jamais `0`.

Les lignes `quarantine_records` sont exclues des lectures produit et PIT.

## Migration 0002

Ajout non destructif (expand) :

- colonnes de provenance sur observations existantes;
- tables `raw_payloads`, `ingestion_runs`, `quarantine_records`;
- `standings`, `injuries`, `lineups`, `lineup_players`;
- enrichissement de `provider_entity_maps`.

Aucune suppression de colonne. Le tennis joueur-contre-joueur reste compatible
via les modèles canoniques ; `matches.home_team_id` reste requis en SQL v1.

## Remplacement mock → SQL

Les fixtures API vivent dans `apps/api/app/fixtures`. Les fixtures d'ingestion
vivent dans `workers/ingestion/fixtures` et portent `data_mode: mock`. Les
services parlent aux protocols de `app/repositories`. Le passage à SQL se fait
en implémentant ces protocols, sans changer les routes, une fois l'ingestion
live validée.
