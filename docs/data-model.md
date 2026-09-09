# Modèle de données

Ce document décrit le schéma conceptuel persisté par `apps/api`. Il n'autorise
pas l'invention de faits sportifs : une table vide signifie une absence de
données, jamais un zéro métier.

## Périmètre v1

Inclus :

- catalogue : `sports`, `leagues`, `teams`, `players`
- mapping d'identités provider : `provider_entity_maps`
- événements : `matches`, `match_events`
- statistiques : `match_statistics`, `team_statistics`, `player_statistics`
- cotes append-only : `odds_snapshots`, `odds_selections`
- registre de modèles : `model_versions`, `model_metrics`
- prédictions : `predictions`, `prediction_outcomes`, `prediction_factors`
- signaux publiés : `published_picks`
- analyses : `ai_analyses`

Exclus jusqu'à la phase 10 :

- `users`, `subscriptions`, `user_favorites`, `user_bets`

Les payloads provider bruts restent hors de PostgreSQL jusqu'à l'agent Data.
Ils devront vivre dans un store immuable (objet) avec checksum.

## Identifiants

Les identifiants publics sont des chaînes stables (`Identifier`, max 128). Les
IDs provider ne remplacent jamais l'ID canonique ; ils passent par
`provider_entity_maps`.

## Temps

Tous les timestamps persistés sont UTC. `kickoff_at` est le temps d'événement.
`observed_at` / `cutoff_at` sont le temps d'observation ou de feature. Ils ne
sont pas interchangeables.

## Cotes et prédictions

Les snapshots de cotes sont append-only. Une évaluation value n'est pas une
table de faits séparée en v1 : elle est calculée de façon déterministe à partir
d'une prédiction calibrée et d'un snapshot, avec `formula_version`.

Les probabilités sont stockées en `Numeric` borné `[0, 1]`. Les cotes
décimales respectent `> 1`. `theoretical_max_drawdown` est borné `[-1, 0]`.

## Qualité

Les observations métier portent un statut d'availability. Une statistique
manquante est `NULL` plus `availability=unavailable`, jamais `0`.

## Remplacement mock → SQL

Les fixtures vivent dans `apps/api/app/fixtures`. Les services parlent aux
protocols de `app/repositories`. Le passage à SQL se fait en implémentant ces
protocols, sans changer les routes.
