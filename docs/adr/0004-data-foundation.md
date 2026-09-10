# ADR 0004 — Fondation DATA et recommandation fournisseurs

- Statut : accepté pour l'architecture. Les fournisseurs V1 sont confirmés dans
  [ADR 0005](0005-data-providers-v1.md).
- Date : 2026-09-09
- Agent : Data
- Portée : `workers/ingestion`, schéma PostgreSQL via Alembic, documentation `docs/data-*.md`.
  Aucune connexion provider live. Aucune modification des vues `apps/web`.

## Contexte

La phase 3 doit permettre d'alimenter PostgreSQL sans inventer de faits sportifs, sans fuite ML, et sans coupler le domaine à un fournisseur. Les choix cloud objet, queue et licences commerciales restent ouverts.

## Décisions

### 1. Worker d'ingestion, même base

L'ingestion vit dans `workers/ingestion` (`predicta_ingestion`). PostgreSQL de `apps/api` reste la source de vérité. Pas de second schéma indépendant. Les payloads bruts sont hors ligne de tables métier ; seules leurs métadonnées sont en base.

### 2. Raw immuable + canonique séparé

Chaque collecte produit un payload checksumé, un `collected_at` et une URI de stockage. La normalisation ne mutile jamais le raw. Un replay est toujours possible.

### 3. Point-in-time par `available_at`

Le cutoff ML est `available_at < T` et `event_at < T`. `collected_at` est un horodatage d'audit. Les adapters de backfill doivent reconstruire `available_at` historique, pas la date d'import.

### 4. Adapters par sport, domaine agnostique

`FootballProvider`, `BasketballProvider`, `TennisProvider`, `OddsProvider` sont des protocoles. Les modèles canoniques n'embarquent pas de types fournisseur.

### 5. Fournisseurs : recommandés, non branchés

Les comparatifs détaillés sont dans [data-providers.md](../data-providers.md). Synthèse retenue comme **recommandation**, pas comme contrat signé :

| Besoin | Recommandation | Pourquoi |
| --- | --- | --- |
| Football live / catalogue | Sportmonks | Couverture stats plus homogène, xG, support, SLA ; pas le moins cher |
| Football bootstrap / parsing | API-Football (fixtures mock aujourd'hui) | Documentation répandue, surface large, coût d'entrée bas |
| Football historique résultats + closing odds | football-data.co.uk | Profondeur historique précieuse pour le backtest ; pas une API |
| NBA | BALLDONTLIE | Historique profond, box scores, blessures, lineups |
| Tennis historique ML | Jeux de données Sackmann (licence à valider) | Surface, H2H, profondeur 1968+ |
| Tennis live (phase 9) | API-Tennis ou MatchPoint | Décision reportée |
| Cotes live + historique PIT depuis 2020 | The Odds API | Snapshots horodatés documentés, multi-sports |
| Event data football recherche | StatsBomb Open Data | Qualité élevée mais **usage commercial interdit** sans licence |

Le moins cher n'est pas retenu comme critère unique. La reproductibilité ML, la licence et la fraîcheur pèsent plus que le prix d'entrée.

### 6. Live disabled by default

`PREDICTA_INGESTION_ENABLE_LIVE` vaut `false`. Les adapters live lèvent une erreur explicite. Aucun secret n'est versionné.

## Conséquences

- L'agent ML peut construire des features et datasets contre `predicta_ingestion.pit` et les tables canoniques.
- Un changement de fournisseur est un nouvel adapter + mapping d'identités, pas une refonte métier.
- Sportmonks, The Odds API, StatsBomb commercial et tout objet S3 exigeaient un ADR
  de confirmation : voir [0005](0005-data-providers-v1.md). La connexion live n'est
  toujours pas autorisée par le seul ADR 0004.
