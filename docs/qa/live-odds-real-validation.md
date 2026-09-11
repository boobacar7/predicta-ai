# Live Odds Provider — Validation réelle

**Branche provider :** `agent/data/live-odds-provider` @ `d53fbf1`  
**Branche QA :** `agent/qa/live-odds-real-validation`  
**Provider :** The Odds API v4 (`the-odds-api-v4`)  
**Modèle :** `football-elo-v1-candidate` — **non promu**  
**Value Engine :** `value-engine-0.1` — **non modifié**  
**Verdict :** **GO WITH CONDITIONS**

Le matching réel est précis (aucun faux match observé). Les snapshots live
append-only, le PIT et l'isolation mock/live tiennent. La chaîne Prediction →
Value → AI Picks → AI Analyst ne peut pas encore consommer les matchs upcoming
ingérés, faute de features PIT pour ces `match_id`.

La clé API n'est pas reproduite dans ce rapport.

---

## 1. Environnement

| Item | Valeur |
| --- | --- |
| Date | 2026-09-11 |
| Worker | `workers/ingestion` venv Python 3.12 |
| API | `apps/api` venv Python 3.14 |
| PostgreSQL | `localhost:5432` / `predicta` |
| Alembic au départ | `0003_league_competition_identity` |
| Alembic après QA | `0004_odds_history` (requis pour `odds_snapshots.provider_id`) |
| Live worker | `PREDICTA_INGESTION_ENABLE_LIVE=true`, `DATA_MODE=live` |
| Région / marché | `eu` / `h2h` / decimal |
| Fenêtre | 2026-09-11T00:00:00Z → 2026-09-14T23:59:59Z |
| Historical endpoint | non utilisé |
| CI | live off, fixtures only |

Sportmonks : Premier League et Ligue 1 déjà présentes (saisons 2024/25–2026/27).
Aucun match inventé depuis The Odds API.

## 2. Provider

The Odds API v4, adapter opt-in `TheOddsApiProvider`.

L'API FastAPI n'appelle pas The Odds API. Collecte = worker → PostgreSQL →
`OddsService` (`LiveOddsProvider(snapshots=())` + `SqlOddsRepository`).

## 3. Périmètre

- Ligues : `soccer_epl` / `premier-league`, `soccer_france_ligue_one` / `ligue-1`
- Marché : `h2h` → canonique `1X2` (`HOME` / `DRAW` / `AWAY`)
- Pas de backfill, pas d'historique payant
- 2 crédits current odds (1 par ligue)

## 4. Nombre d'événements

| Metric | Result |
| --- | ---: |
| Odds API events | 19 |
| Sportmonks candidates (même fenêtre) | 19 |
| Successfully matched | 11 |
| Match rejected | 8 |
| Snapshot inserted | 269 |
| Snapshot rejected (unmatched books) | 188 |
| 1X2 complete markets | 269 |
| Incomplete markets persisted | 0 |
| Unknown outcomes | 0 |
| Replay snapshot delta | 0 |

Taux de matching événement : **57.89 %** (11 / 19).  
Précision des matches tentés : **100 %** (0 faux positifs).

## 5. Taux de matching

Clé naturelle actuelle :

```text
football|{slugify(home)}|{slugify(away)}|{kickoff.isoformat()}
```

`slugify` : NFKD, accents retirés, minuscule, ponctuation → tirets. Pas
d'alias, pas de tolérance de coup d'envoi, pas d'inversion home/away.

Les 11 matches exacts avaient le même coup d'envoi UTC et les mêmes noms après
slugify (ex. `Paris Saint Germain` Sportmonks = `Paris Saint Germain` Odds API).

## 6. Détails des mismatches

Tous les rejets : `team_name_slug_mismatch` / `unmatched_odds_event`.
Aucun ordre home/away inversé. Aucun écart de timezone.

| Odds API home | Odds API away | Kickoff UTC | Candidat Sportmonks | Raison |
| --- | --- | --- | --- | --- |
| Bournemouth | Brentford | 2026-09-12T14:00:00Z | AFC Bournemouth vs Brentford | préfixe `AFC` |
| Coventry City | Brighton and Hove Albion | 2026-09-13T13:00:00Z | Coventry City vs Brighton & Hove Albion | `and` vs `&` |
| Rennes | Marseille | 2026-09-11T18:45:00Z | Rennes vs Olympique Marseille | préfixe `Olympique` |
| Strasbourg | AS Monaco | 2026-09-12T15:15:00Z | Strasbourg vs Monaco | préfixe `AS` |
| Le Havre | Angers | 2026-09-12T18:45:00Z | Le Havre vs Angers SCO | suffixe `SCO` |
| Paris FC | Lyon | 2026-09-12T18:45:00Z | Paris vs Olympique Lyonnais | `Paris FC`≠`Paris`, `Lyon`≠`Olympique Lyonnais` |
| Lille | Troyes | 2026-09-13T13:00:00Z | LOSC Lille vs Troyes | préfixe `LOSC` |
| Le Mans FC | RC Lens | 2026-09-13T15:15:00Z | Le Mans vs Lens | suffixe `FC`, préfixe `RC` |

Aucun alias n'a été ajouté. Un matching flou `Paris` / `Paris FC` /
`Paris Saint Germain` serait plus dangereux qu'un rejet.

Matches réussis (échantillon) : Liverpool–Fulham, Chelsea–Hull City,
Manchester United–Manchester City, Brest–Paris Saint Germain, Auxerre–Nice.

## 7. Snapshots insérés

Pour les 11 matchs liés :

- `canonical_match_id` = id Sportmonks (ex. `mth_football-sportmonks-19722167`)
- `provider` = `the_odds_api`
- `source` = `the-odds-api-v4`
- `data_mode` = `live`
- `market` = `1X2`
- `available_at` = `collected_at` = `bookmakers[].last_update`
- `raw_payload_id` présent
- `event_at` / coup d'envoi : sur `matches.kickoff_at`, pas une colonne odds
- HOME / DRAW / AWAY uniquement ; 0 outcome inconnu persisté

## 8. Bookmakers

26 books EU observés, dont `pinnacle`, `betfair_ex_eu`, `williamhill`,
`winamax_fr`, `unibet_fr`, `marathonbet`, `betclic_fr`. Aucun book inventé.

## 9. Marchés

Uniquement `h2h` → `1X2`. `totals` ignoré. 269 / 269 snapshots persistés sont
complets HOME+DRAW+AWAY.

## 10. Timestamps

`commence_time` parsé via RFC 3339 `Z` → `+00:00`, identique au kickoff
Sportmonks pour tous les matches exacts. `last_update` bookmaker = `available_at`.

## 11. PIT

**PASS** (cotes).

Ingestion `PointInTimeStore.odds_as_of` : `available_at < cutoff`, `event_at`
ignoré pour les cotes (le kickoff ne masque pas le pre-match).

Sur Liverpool–Fulham (25 snapshots, 13 `available_at` distincts) :

| Cas | Résultat |
| --- | --- |
| cutoff avant le plus ancien `available_at` | aucune snapshot |
| cutoff = min(`available_at`) | aucune snapshot (strict `<`) |
| cutoff juste après min | snapshot ancienne acceptée |
| cutoff après max | snapshot la plus récente éligible |
| Value Engine cutoff intermédiaire | n'utilise pas une snapshot plus récente post-cutoff |
| Value Engine cutoff avant toute snapshot | `OddsTemporalLeakageError` |
| snapshot incomplète plus récente (overlay mémoire) | ne masque pas la complète valide |

Value Engine v0.1 : `available_at <= cutoff_at` (contrat inchangé).

Replay des mêmes enveloppes : **0** snapshot supplémentaire (`ON CONFLICT DO NOTHING`).

Un second tick live (nouvelle cote / nouveau `last_update`) n'a pas été
observé : un seul fetch current par ligue. Le chemin append-only est couvert
par les tests déterministes + l'absence de mutation des lignes existantes.

## 12. Value Engine

**PASS** (formules sur cotes live). **CONDITION** (chaîne produit).

Formules v0.1 inchangées, vérifiées sur Pinnacle Liverpool–Fulham
(`1.45` / `5.02` / `6.69`) :

- `implied = 1 / odds`
- `overround = Σ implied` ≈ 1.038
- `no_vig = implied / overround`
- `edge` / `EV` branchés sur le calculator canonique

`GET /api/v1/football/value/mth_football-sportmonks-19722167` en
`repository=sql` + `data_mode=live` retourne RFC 9457
`/problems/pit-features-unavailable` : le parquet candidat n'a pas de ligne
pour ce match upcoming. Aucune cote ni probabilité n'est inventée.

Le modèle n'a pas été recalibré ni promu.

## 13. AI Picks

**CONDITION.**

L'univers V0.1 reste `[mth_football-sportmonks-19719892]` (Lincoln). Les matchs
live ingérés n'y entrent pas. Ranking et formules non déplacés. Frontend
inchangé. Pas de calcul métier ajouté.

## 14. AI Analyst

**CONDITION.**

LLM réel désactivé (`deterministic` / `mock-explainer-0.1`). Sans prédiction
PIT, l'analyste ne peut pas expliquer un match upcoming live. Grounding
inchangé. Le narrative LLM n'est pas rendu.

## 15. Mock / live isolation

**PASS.**

| Cas | Résultat |
| --- | --- |
| LIVE OFF | `LiveIngestionDisabled`, aucun HTTP |
| LIVE ON + clé absente | `ProviderNotConfigured`, aucun HTTP, aucun mock |
| LIVE ON + 401 (tests scriptés) | `ProviderAuthError`, secret non loggé |
| LIVE ON + HTTP 503 (tests) | `ProviderUnavailable`, sink vide, mock distinct |
| LIVE ON + événement non matché | `unmatched_odds_event`, 0 snapshot |
| API `data_mode=mock` | Lincoln catalogue ; Liverpool 404 |
| API `data_mode=live` + `repository=sql` | Liverpool `data_mode=live` ; pas d'appel The Odds API |

## 16. Quality gates

**PASS.**

| Gate | Résultat |
| --- | --- |
| `npm run verify:ingestion` | 125 passed |
| `npm run verify:api` | 547 passed |
| `npm run verify:ml` | 27 passed |
| `npm run verify:web` | OpenAPI inchangé, 283 tests, build OK |
| CI The Odds API | aucun test ne requiert `THE_ODDS_API_KEY` ; pas d'URL live dans `.github/workflows` |

Python : venvs du projet (`workers/ingestion/.venv`, `apps/api/.venv`,
`workers/ml/.venv`), scripts `verify` inchangés.

## 17. Problèmes rencontrés

1. **Schéma** : persist live échouait (`provider_id` absent) tant que 0004
   n'était pas appliqué. Corrigé localement par `alembic upgrade head`.
2. **psycopg3** : `WHERE EXISTS (... id = :match_id)` avec le même bind que
   l'INSERT levait `AmbiguousParameter`. Correctif : paramètres distincts
   `existing_match_id` / `existing_snapshot_id`.
3. **Rejet silencieux** : un unmatched laissait un `match_id` synthétique et
   SQL skippait sans raison. Correctif : quarantaine `unmatched_odds_event`
   et exclusion du batch. Mock odds inchangé.
4. **`--dry-run`** n'hydratte plus à vide : lecture des clés Sportmonks pour
   mesurer le matching sans écrire.
5. Vocabulaire de noms (voir §6) : rejets explicites, pas de faux match.

## 18. HIGH / MEDIUM / LOW

### HIGH (1)

- **H-01** — Toute base qui sert l'ingestion live doit être en Alembic
  `0004_odds_history`. Sans ça, aucun snapshot n'est persisté.

### MEDIUM (2)

- **M-01** — 8 / 19 événements rejetés pour variantes de noms (AFC, Olympique,
  LOSC, AS, SCO, FC, RC, `&` vs `and`). Table d'alias explicite à proposer
  plus tard, avec tests déterministes. Pas de fuzzy matching.
- **M-02** — Les matchs upcoming live n'ont pas de features PIT dans le
  dataset `football-elo-v1-candidate`. Value / Picks / Analyst ne peuvent pas
  encore les évaluer. C'est un gap de couverture ML, pas une invention de
  données.

### LOW (4)

- **L-01** — `PersistResult.inserted` compte les tentatives, pas les rowcounts.
- **L-02** — `event_at` cotes n'est pas une colonne SQL ; le kickoff est sur
  `matches`.
- **L-03** — Pas de second tick live observé (quota). Idempotence same-payload
  et tests d'append couvrent le contrat.
- **L-04** — `GET /matches/{id}/odds` reste le catalogue, pas `OddsService`.

## 19. Recommandations

Avant une activation générale du provider live :

1. Appliquer Alembic `0004` sur chaque environnement.
2. Introduire une table d'alias **explicite** (paires documentées), pas une
   similarité de chaînes. Exemples réels ci-dessus. Tests one-to-one.
   Ne pas fusionner `Paris` / `Paris FC` / `Paris Saint Germain` par fuzzy.
3. Produire des features PIT pre-match pour les fixtures scheduled si la
   chaîne Value/Picks doit lire des cotes live upcoming. Ne pas réentraîner
   ni promouvoir le candidat pour autant.
4. Garder CI live-off + fixtures.
5. Ne pas élargir le polling au-delà des ligues V1 nécessaires.

## 20. Verdict

**GO WITH CONDITIONS**

Le provider live matche avec précision, refuse explicitement les non-matches,
persiste des snapshots 1X2 complets `data_mode=live`, respecte le PIT et
n'a pas de fallback mock. Il ne doit pas être activé comme source unique des
écrans Value / Picks / Analyst tant que (1) 0004 est partout, (2) les alias
critiques sont tranchés, (3) les matchs cibles ont des features PIT.

`football-elo-v1-candidate` reste CANDIDATE.
