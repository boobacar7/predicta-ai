# Pipeline DATA

Implémentation de référence : package Python `predicta_ingestion` dans `workers/ingestion`.

## 1. Flux

```text
Provider adapter
    │  RawEnvelope (bytes, headers, collected_at, data_mode)
    ▼
Raw store (immuable) + raw_payloads (métadonnées PostgreSQL)
    │
    ▼
Validation (schéma, types, timestamps UTC, data_mode)
    │  échec → quarantine_records
    ▼
Normalisation (provider JSON → modèles canoniques)
    │
    ▼
Entity resolution (provider_id → canonical_id)
    │  ambiguïté → quarantaine
    ▼
Déduplication (checksum raw, clé naturelle canonique)
    │
    ▼
Canonical sink (PostgreSQL via modèles apps/api)
    │
    ▼
Point-in-time reader (cutoff explicite, pour le worker ML)
```

Le pipeline ne publie pas de prédictions et n'appelle pas le Value Engine.

## 2. Abstractions

| Protocole | Responsabilité |
| --- | --- |
| `FootballProvider` / `BasketballProvider` / `TennisProvider` / `OddsProvider` | Collecte uniquement. Retourne du raw. |
| `RawStore` | Écriture append-only, lecture par id, jamais d'update. |
| `Validator` | Schéma + invariants. Pas de « réparation ». |
| `Normalizer` | Mapping provider → canonique. Un adapter par fournisseur. |
| `IdentityResolver` | Mapping d'identités, création déterministe, refus des fusions ambiguës. |
| `CanonicalSink` | Persistance. Mémoire pour tests, SQL pour l'API. |
| `PointInTimeStore` | Lectures bornées par cutoff. |

Aucun module `canonical` n'importe un client HTTP.

## 3. Modèles canoniques

Définis dans `predicta_ingestion.canonical` :

- `Sport`, `League`, `Team`, `Player`
- `Match`, `MatchEvent`
- `TeamStats`, `PlayerStats`
- `OddsSnapshot` (+ sélections)
- `StandingSnapshot`, `Injury`, `Lineup` (extensions football-first)

Chaque objet métier porte un `Provenance` :

- `provider`
- `provider_id`
- `collected_at`
- `event_at` (nullable si non applicable)
- `available_at`
- `source`
- `freshness`
- `data_mode`
- `raw_payload_id`

Les statistiques restent typées par `stat_key` + unité + `availability`. Un zéro métier n'est écrit que s'il est explicitement présent dans le raw validé.

## 4. Ingestion raw

`RawEnvelope` contient le body binaire, le content-type, le provider, la ressource, une clé de requête et `collected_at`.

Le store filesystem (`FilesystemRawStore`) écrit :

```text
{root}/{data_mode}/{provider}/{yyyy}/{mm}/{dd}/{raw_id}.json
```

Le fichier n'est jamais écrasé. Un checksum SHA-256 identique court-circuite l'écriture (déduplication), y compris après réouverture du process : le store indexe les JSON déjà présents et recalcule le checksum courant à partir du body. Les métadonnées volatiles Sportmonks (`rate_limit`, `subscription`, `pagination.next_cursor`) sont exclues du checksum. `data_mode=mock` et `live` sont des arbres disjoints.

PostgreSQL table `raw_payloads` : id, provider, resource_type, checksum, storage_uri, collected_at, data_mode. Pas de payload complet en base.

## 5. Validation

Rejets immédiats :

- datetime naïf (sans timezone);
- `data_mode` absent ou `live` sur une fixture de test;
- cote décimale ≤ 1;
- sport inconnu;
- identifiant provider vide;
- score présent alors que le match n'est pas `finished` / `live` selon la règle du sport;
- payload trop volumineux (limite documentée dans la config).

Les erreurs provider (timeout, 429, 5xx, auth) ne sont pas transformées en entités vides. Elles échouent le run avec un statut d'erreur.

## 6. Normalisation

Chaque adapter possède un normalizer. Exemple conceptuel API-Football :

```text
fixture.teams.home.id  → Team.provider_id
fixture.fixture.date   → Match.kickoff_at (UTC)
fixture.fixture.status → Match.status (enum canonique)
```

Les enums provider sont mappés vers des enums canoniques. Une valeur inconnue va en quarantaine ; elle n'est pas coercée vers `unknown` silencieusement pour les champs critiques (statut de match, marché de cotes).

Mapping Sportmonks V1 (fixtures) :

```text
fixture.id                 → Match.provider_id
starting_at (UTC)          → Match.kickoff_at / event_at
state_id                   → Match.status
participants.meta.location → home/away teams
scores[description=CURRENT] → home_score / away_score (finished/live only)
season.name / season_id   → League.season
```

Un match `scheduled` n'emporte pas de score, même si le JSON contient `0`.
Un résultat `finished` a `available_at` strictement après le coup d'envoi
(`kickoff + 3h`, ou `collected_at` s'il est plus tôt). Le PIT refuse ce
résultat comme feature pre-match.

Découverte d'historique :

```text
GET /seasons?filters=seasonLeagues:{leagueId}
GET /fixtures?include=participants;scores;league.country;season;venue;state&filters=fixtureLeagues:{leagueId};fixtureSeasons:{seasonId}
```

Une fenêtre `--date-from` / `--date-to` utilise l'endpoint documenté
`GET /fixtures/between/{start}/{end}` (max 100 jours) avec les mêmes filtres.

MLS (Sportmonks id 779) est ingérée pour toutes les saisons réellement retournées.
Les ligues européennes V1 sont limitées par défaut aux 3 saisons les plus récentes.
`--season`, `--date-from`, `--date-to` et `--all-seasons` restreignent le run.
Une saison absente de la réponse provider n'est pas inventée.

Une fixture invalide (placeholder, scores manquants, même équipe des deux côtés)
va en quarantaine **individuellement** ; les voisines valides de la page sont
normalisées.

## 7. Résolution d'identités

Ordre déterministe, sans fuzzy matching :

1. Lookup exact `(provider, entity_type, provider_entity_id)`.
2. Mapping historique explicite (alias de slug MLS ou id provider documenté).
3. Nom normalisé (`slugify`, égalité stricte) **uniquement s'il existe un seul** canonical pour cette compétition.
4. Si 0 candidat : créer un canonical id déterministe.
5. Si ≥ 2 candidats : quarantaine `ambiguous_identity`.

Les ligues Sportmonks sont identifiées par `{league_id}:{season}` : MLS `779` en 2024 et `779` en 2025 ne se marchent pas dessus.

Les IDs déterministes sont des slugs stables, pas un hash opaque, afin de rester lisibles (`tm_football_arsenal_epl`). Un suffixe numérique n'est ajouté qu'après collision réelle.

## 8. Déduplication

| Objet | Clé naturelle |
| --- | --- |
| Raw | `(provider, checksum_sha256)` |
| Mapping | `(provider, entity_type, provider_entity_id)` |
| Match | canonical id issu du mapping provider match |
| Odds snapshot | `(provider, bookmaker, match_id, market, observed_at)` |
| Standing | `(league_id, season, team_id, as_of, provider)` |
| Stats snapshot | `(entity_id, season, stat_key, as_of, provider)` |

Les upserts sont idempotents. Relancer un run ne duplique pas les faits.

## 9. Stockage et historique

Les tables de faits volumineuses sont append-only. Un classement n'est pas écrasé : un nouveau `as_of` est inséré. Les cotes déjà persistées ne sont pas mises à jour.

Reproductibilité d'un dataset :

1. figer `cutoff_at` (kickoff du match cible) ;
2. lire via `PointInTimeStore` ;
3. construire `build_ml_dataset(competition, seasons, cutoff_policy)` ;
4. hasher les canonical ids + `available_at` max par type ;
5. enregistrer le hash à côté de `dataset_version` (`football-1x2-history-0.2`).

Correction d'un payload Sportmonks : le raw d'origine reste immuable. Un payload
corrigé (checksum différent) crée un nouvel enregistrement raw et un upsert
canonique du match. `raw_payload_id` pointe vers le raw le plus récemment accepté.

## 10. Point-in-time (contrat ML)

```text
PointInTimeStore.matches_finished_before(cutoff)
PointInTimeStore.odds_as_of(match_id, cutoff)
PointInTimeStore.standings_as_of(league_id, cutoff)
PointInTimeStore.injuries_as_of(team_id, cutoff)
PointInTimeStore.lineups_as_of(match_id, cutoff)
```

Toute méthode applique :

```text
available_at < cutoff_at
event_at is None OR event_at < cutoff_at
data_mode filtré explicitement par l'appelant
```

Une composition publiée après le coup d'envoi n'entre pas dans les features pre-match. Un résultat du match cible n'est jamais accessible pour ce match.

Les features de forme football (`predicta_ingestion.ml.features`) n'utilisent que des
matchs dont `event_at < kickoff` et `available_at < kickoff`. Fenêtres rolling 5 et
10, plus les totaux prior. Un résultat pas encore disponible est exclu.

Le rating Elo pré-match (`predicta_ingestion.ml.elo`) est une reconstruction
historique, pas un entraînement : snapshot au `event_at`, mise à jour uniquement
quand `available_at` est atteint. Paramètres : initial 1500, K=20, avantage
domicile +80. Le rating après le match N n'est jamais réinjecté dans le match N.

Les classements ne sont pas encore ingérés depuis Sportmonks. Les features
`home_standing_rank` / `away_standing_rank` restent `null` tant que des
`StandingSnapshot` PIT-valides n'existent pas. Ils ne sont pas interpolés.

## 11. Cotes et Value Engine

Le pipeline persiste :

- bookmaker / provider
- market
- selection
- decimal odds
- timestamps
- match_id canonique
- source

Il ne remplit pas `implied_probability_raw`, `no_vig_probability`, `edge` ni `expected_value`. Ces colonnes existantes côté API restent à la charge du Value Engine.

## 12. Tennis et basketball

Les protocoles et modèles canoniques existent. La table `matches` v1 exige encore `home_team_id` / `away_team_id` pour rester compatible avec l'API football. Le tennis (joueur contre joueur) exigera une migration ultérieure `match_participants` ; elle n'est pas anticipée de façon destructive ici.

## 13. Exécution

```bash
cd workers/ingestion
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest
```

Mock par défaut. Live Sportmonks :

```bash
python -m predicta_ingestion ingest-football --league premier-league --date-from 2026-08-01 --date-to 2026-09-10 --dry-run
```

Sans `PREDICTA_INGESTION_ENABLE_LIVE=true` et sans `SPORTMONKS_API_TOKEN`,
la commande lève `LiveIngestionDisabled` ou `ProviderNotConfigured`.
Aucun fallback mock.

Historique + dataset PIT :

```bash
python -m predicta_ingestion ingest-history --league MLS --dry-run
python -m predicta_ingestion ingest-history --league mls --season 2024 --date-from 2024-03-01 --date-to 2024-11-30
python -m predicta_ingestion build-ml-dataset --league MLS --write-dataset ./var/football-1x2-history.json
```

`--dry-run` ne écrit ni PostgreSQL ni le store raw. Le rapport d'ingestion liste
les saisons **découvertes** (réponse provider) et celles **sélectionnées**.

Détail ML : [ml-dataset.md](ml-dataset.md).

## 14. Handoff ML

L'agent ML doit :

- importer `predicta_ingestion.pit` et `predicta_ingestion.ml` plutôt que de joindre SQL librement;
- versionner les définitions de features (`football-1x2-history-0.2`);
- n'utiliser que `available_at < cutoff` et `event_at < cutoff`;
- traiter `availability=unavailable` et les ranks nuls comme donnée manquante;
- ignorer toute ligne `data_mode=mock` dans un entraînement présenté comme réel;
- ne pas lire `predictions` pour entraîner le même marché sans protocole dédié (fuite);
- ne pas réentraîner Elo / Poisson / Gradient Boosting dans le worker DATA.
