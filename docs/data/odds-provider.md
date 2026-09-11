# The Odds API — provider cotes football V1

Provider retenu : **The Odds API v4** (`https://api.the-odds-api.com`).
Décision produit : [ADR 0005](../adr/0005-data-providers-v1.md).
Documentation officielle relue pour cette intégration :

- [Odds API Documentation V4](https://the-odds-api.com/liveapi/guides/v4/)
- [Sports APIs](https://the-odds-api.com/sports-odds-data/sports-apis.html)
- [Betting markets](https://the-odds-api.com/sports-odds-data/betting-markets.html)
- [Bookmakers](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html)
- [Historical odds](https://the-odds-api.com/historical-odds-data/)
- [Terms and Conditions](https://the-odds-api.com/terms-and-conditions.html) (31 August 2026)

Aucune capacité n'est supposée hors de ces pages.

## Couverture réellement vérifiée

Football (soccer) pour les ligues V1 PREDICTA, via les **sport keys** listés par le provider :

| Ligue PREDICTA | Sport key The Odds API |
| --- | --- |
| Premier League | `soccer_epl` |
| La Liga | `soccer_spain_la_liga` |
| Bundesliga | `soccer_germany_bundesliga` |
| Serie A | `soccer_italy_serie_a` |
| Ligue 1 | `soccer_france_ligue_one` |
| UEFA Champions League | `soccer_uefa_champs_league` |
| MLS | `soccer_usa_mls` |

Le provider couvre d'autres sports (NBA, tennis, etc.). Ils ne sont **pas** branchés ici.

## Marchés

V1 persiste uniquement le marché featured **`h2h`** (head to head / moneyline),
documenté comme incluant le **draw** pour le soccer. Il est normalisé vers le
marché canonique PREDICTA `1X2` (`HOME` / `DRAW` / `AWAY`).

Les marchés `spreads`, `totals`, `outrights`, `h2h_lay` et les marchés additionnels
(BTTS, player props, etc.) existent chez le provider. Ils sont **ignorés**, pas
inventés, pas convertis en value.

Format d'odds demandé : `oddsFormat=decimal` (défaut documenté : decimal).

## Bookmakers

La région par défaut est **`eu`**, listée officiellement, et c'est la région où
**Pinnacle** apparaît (`bookmaker key: pinnacle`, note provider : cotes du site
public, délai possible). D'autres books EU documentés incluent Betfair Exchange,
Betsson, Marathon Bet, Unibet (FR/IT/NL/SE), William Hill, Winamax, etc.

Aucun bookmaker n'est synthétisé s'il est absent de la réponse. Pinnacle n'est
**pas** encore un book de référence figé : le Value Engine prend le snapshot
**complet** éligible le plus récent, quel que soit le book.

## Historique

Documenté, **plans payants uniquement** :

- snapshots depuis le **6 juin 2020** ;
- intervalle 10 minutes jusqu'au 18 septembre 2022, puis **5 minutes** ;
- `GET /v4/historical/sports/{sport}/odds` avec `date` ISO 8601 ;
- le provider retourne le snapshot **le plus proche ≤ `date`**, plus
  `timestamp`, `previous_timestamp`, `next_timestamp`.

CLI : `ingest-odds --as-of 2026-09-08T15:55:00Z`.

Sans `--as-of`, l'adapter appelle l'endpoint courant
`GET /v4/sports/{sport}/odds` (upcoming / in-play, **pas** les matchs terminés).

## Timestamps

| Champ | Source vérifiée | Usage PREDICTA |
| --- | --- | --- |
| `commence_time` | événement | `event_at` (coup d'envoi) ; clé naturelle du match |
| `bookmakers[].last_update` | bookmaker | `available_at` et `collected_at` canoniques du snapshot |
| enveloppe raw `collected_at` | horloge PREDICTA | moment du fetch, store raw uniquement |
| `timestamp` historique | snapshot provider | métadonnée raw (`snapshot_timestamp`), pas une cote |

`last_update` manquant → quarantaine. La disponibilité n'est jamais inventée.
`collected_at` canonique = `last_update` pour respecter
`available_at >= collected_at` du domaine Value Engine tout en conservant
l'instant d'observation du bookmaker.

## Limites / quota (documentation v4)

Headers : `x-requests-remaining`, `x-requests-used`, `x-requests-last`.

- Odds courants : **1 crédit × régions × marchés**. V1 = 1 région (`eu`) × 1 marché (`h2h`) = **1** par ligue.
- Historique : **10 crédits × régions × marchés** = **10** par ligue et par `date`.
- `GET /v4/sports` est gratuit (non utilisé par l'adapter V1).
- Réponse vide : le provider indique que l'appel **ne compte pas**.
- 401/403 → `ProviderAuthError`. 429 → retry puis `ProviderRateLimited`. 5xx → `ProviderUnavailable`.
- Polling REST, **pas de WebSocket**.

Free tier annoncé : 500 crédits / mois. Historical est payant. Le plan exact
reste une décision humaine.

## Licence (terms 31 August 2026)

Usage commercial **autorisé** dans une application utilisateur (UI, dashboards,
outils analytiques, entraînement de modèles), y compris le stockage indéfini.

**Interdit** : revendre / redistribuer les données comme produit de données
standalone (API, feed, fichiers destinés à servir de source brute à autrui).

PREDICTA expose des analyses (probabilités modèle, edge, EV calculés par le
Value Engine), pas un feed de cotes brutes à destination de tiers. Attribution
non obligatoire. Relire le contrat du plan souscrit avant production.

## Architecture

```text
TheOddsApiProvider (opt-in)
    → RawEnvelope immuable (filesystem, data_mode=live)
    → Validator (objet JSON, data_mode, timestamps UTC)
    → OddsNormalizer (h2h → 1X2, pas d'EV / edge / no-vig)
    → IdentityResolver (clé naturelle football|home|away|kickoff)
    → Canonical odds_snapshots append-only
    → PointInTimeStore / OddsService
    → Value Engine v0.1
    → AI Picks / AI Analyst
```

Le domaine API ne connaît que `OddsProvider` :

- `MockOddsProvider` — fixtures `predicta-mock-odds-v0.1`, `data_mode=mock`
- `LiveOddsProvider` — `the-odds-api-v4`, `data_mode=live`, désactivé par défaut

L'API **n'appelle pas** The Odds API. Le worker d'ingestion collecte. Un runtime
API `data_mode=live` relit PostgreSQL (source `the-odds-api-v4`) ; un fetch
HTTP depuis l'API lève une erreur explicite, sans fallback mock.

## Configuration

Worker (`workers/ingestion/.env`, jamais Git) :

```bash
PREDICTA_INGESTION_ENABLE_LIVE=true
PREDICTA_INGESTION_DATA_MODE=live
PREDICTA_INGESTION_THE_ODDS_API_KEY=   # ou THE_ODDS_API_KEY=
PREDICTA_INGESTION_THE_ODDS_API_REGIONS=eu
```

```bash
python -m predicta_ingestion ingest-odds --league premier-league --dry-run
python -m predicta_ingestion ingest-odds --league all --as-of 2026-09-08T15:55:00Z
```

Les matchs football (Sportmonks) doivent déjà être ingérés pour lier les cotes
via la clé naturelle. Un snapshot dont le match canonique n'existe pas n'est
**pas** inséré en SQL (FK) et n'invente pas de match.

## Erreurs

| Situation | Comportement |
| --- | --- |
| Live off | `LiveIngestionDisabled` — aucun HTTP |
| Clé absente | `ProviderNotConfigured` — aucun HTTP, aucun mock |
| 401/403 | `ProviderAuthError` — secret jamais loggé |
| 429 épuisé | `ProviderRateLimited` |
| Timeout / 5xx | `ProviderUnavailable` |
| Cote ≤ 1, prix manquant, `last_update` manquant | quarantaine de ce marché / book |
| Bookmaker ou sélection absente | pas de ligne, pas de fallback |
| API live sans worker | `OddsUnavailableError`, pas de mock |

`data_mode` est posé sur l'enveloppe raw, le snapshot canonique, et l'enveloppe
API. Un mélange mock/live est refusé.

## Stratégie historique

1. Backfill ciblé par ligue V1 et par `date` (coût ×10).
2. Utiliser `previous_timestamp` / `next_timestamp` pour marcher dans le temps
   **uniquement** avec des `date` réellement retournées.
3. Ne pas interpoler entre deux snapshots.
4. Ne pas rejouer trop de timestamps : le quota historical est le coût caché.
5. football-data.co.uk reste **recherche / backtest**, pas ce flux produit.

## Stratégie PIT

Ingestion / ML (`PointInTimeStore`) :

```text
available_at < cutoff_at
event_at is None OR event_at < cutoff_at
```

Pour les cotes, le filtre ML utilise `available_at` (`last_update`). `event_at`
est le `commence_time` du match : il identifie l'événement, il ne doit pas
exclure les cotes pre-match du match cible au cutoff = coup d'envoi.

Value Engine / API (contrat v0.1 inchangé) :

```text
odds.available_at <= cutoff_at
```

Une cote avec `available_at` strictement après le cutoff n'est jamais utilisée.
Les snapshots sont append-only : un changement de cote crée un **nouvel** id.
Un snapshot incomplet plus récent ne masque pas un 1X2 complet plus ancien.

## CI

Aucun test n'appelle le réseau The Odds API. Les réponses sont des fixtures
enregistrées sous `workers/ingestion/fixtures/the_odds_api/`.
