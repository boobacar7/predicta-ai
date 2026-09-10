# AI Picks + Value Finder — QA after Match Identity

**Branche backend validée :** `agent/backend/fix-ai-picks-match-identity` @ `c31a367`  
**Branche frontend de référence :** `agent/frontend/ai-picks-value-finder` @ `ff4e224`  
**Branche QA :** `agent/qa/ai-picks-frontend-validation`  
**Verdict :** **NO-GO**

Le correctif Match Identity est réel côté API. Il n’est pas consommé par
l’interface. Les cartes AI Picks continuent d’afficher `match_id` à la place
des équipes et d’affirmer que le moteur ne publie ni nom ni horaire.

Les claims backend (MATCH RESOLUTION, TEAM IDENTITY, KICKOFF, PIT, DTO,
OpenAPI, 135 tests) ont été reproduits indépendamment et tiennent. Le claim
frontend (cartes Home vs Away / Kickoff après le fix) ne tient pas.

---

## 1. Scope

Validation end-to-end de AI Picks + Value Finder après
`c31a367 fix(api): resolve ai picks match identity`.

Inclus :

- `GET /api/v1/football/ai-picks` (DTO, identité, métadonnées) ;
- identité canonique sur 7 compétitions historiques ;
- `GET /api/v1/matches/{match_id}` pour les mêmes IDs ;
- PIT / absence de résultat post-kickoff dans la résolution d’identité ;
- chaîne Prediction → Value Engine → AI Picks ;
- UI `/ai-picks` et `/value-finder` (mock local + contrat TypeScript) ;
- responsive 1440 / 1024 / 820 / 390 ;
- filtres, tris, empty / error / loading / mock / candidate ;
- OpenAPI vs backend vs frontend (`openapi-typescript` régénéré) ;
- régression `ruff` / `mypy` / `pytest` / lint / typecheck / build / vitest.

Exclus (volontairement) :

- création d’AI Analyst ;
- modification ou promotion du modèle ;
- branchement des cotes live ;
- implémentation du fix frontend (hors scope QA).

---

## 2. Environment

| Item | Valeur |
| --- | --- |
| API commit | `c31a367 fix(api): resolve ai picks match identity` |
| Frontend commit (ancêtre) | `ff4e224 feat(web): build ai picks and value finder` |
| `model_version` | `football-elo-v1-candidate` |
| `model_status` | `candidate` |
| `value_engine_version` | `value-engine-0.1` |
| `ai_picks_version` | `ai-picks-0.1` |
| Univers AI Picks V0.1 | `PREDICTA_API_AI_PICKS_CANDIDATE_MATCH_IDS=["mth_football-sportmonks-19719892"]` |
| Harness API | `TestClient` via `tests.conftest.make_client()` (`repository=mock`, horloge figée `2026-09-09T18:00:00Z`) |
| Identité par défaut | `ParquetArchiveMatchIdentityRepository` (SQL seulement si `PREDICTA_API_REPOSITORY=sql`) |
| Dataset PIT | `workers/ingestion/var/football-1x2-history.parquet` (**gitignoré**) |
| Raw archive | `workers/ingestion/var/raw` (**gitignoré**) |
| Frontend local | `NEXT_PUBLIC_PREDICTA_DATA_SOURCE=mock` (`apps/web/.env.local`) |
| UI vérifiée | `next start` `http://127.0.0.1:3002` sur le build de cette branche |

Un clone Git sans `var/` ne suffit pas à servir l’identité historique. Le
frontend local, tel que configuré, n’appelle pas l’API identity-fixed.

---

## 3. Backend validation

`GET /api/v1/football/ai-picks` → **200**.

Envelope : `data_mode=mock` (fournisseur de cotes mock). `evaluated_matches=1`.
Deux opportunités éligibles, une exclusion.

Chaque item expose, sans champ manquant :

| Champ | Item 1 | Item 2 |
| --- | --- | --- |
| `match_id` | `mth_football-sportmonks-19719892` | identique |
| `home_team` | Lincoln Red Imps | identique |
| `away_team` | Inter Club d'Escaldes | identique |
| `league` | Champions League | identique |
| `kickoff_at` | `2026-07-07T16:00:00Z` | identique |
| `selection` | AWAY | DRAW |
| `odds` | 5.0 | 4.0 |
| `model_probability` | 0.31261487997008847 | 0.2710215458899908 |
| `implied_probability` | 0.2 | 0.25 |
| `no_vig_probability` | 0.21052631578947367 | 0.2631578947368421 |
| `edge` | 0.11261487997008847 | 0.0210215458899908 |
| `ev` | 0.5630743998504424 | 0.0840861835599632 |
| `model_version` | `football-elo-v1-candidate` | identique |
| `model_status` | `candidate` | identique |
| `value_engine_version` | `value-engine-0.1` | identique |
| `ai_picks_version` | `ai-picks-0.1` | identique |
| `cutoff_at` | `2026-07-07T16:00:00Z` | identique |
| `generated_at` | `2026-09-09T18:00:00Z` | identique |
| `data_mode` | `mock` | identique |

`cutoff_at` est égal à `kickoff_at`. Les métadonnées de liste
(`AiPicksMetadata`) portent les seuils et le ranking, pas `model_version` :
celui-ci est sur chaque pick, conformément au contrat.

Filtres serveur reproduits :

| Query | Résultat |
| --- | --- |
| `league=Champions League` | 2 items, 1 match évalué |
| `league=Premier League` | 0 match évalué |
| `date=2026-07-07` | 2 items |
| `min_edge=0.9` | 0 item, 3 exclusions |

**AI PICKS API : PASS**

---

## 4. Match identity

Sept matchs historiques réels, via `GET /api/v1/matches/{match_id}` et le
dépôt parquet/raw. Noms lus depuis le modèle canonique (Sportmonks) : « Paris »
et non une invention « Paris Saint-Germain ».

| Compétition | `match_id` | Home | Away | Kickoff |
| --- | --- | --- | --- | --- |
| Premier League | `mth_football-sportmonks-19722183` | Arsenal | Chelsea | `2026-09-06T15:30:00Z` |
| Ligue 1 | `mth_football-sportmonks-19715615` | Olympique Marseille | Paris | `2026-09-06T18:45:00Z` |
| La Liga | `mth_football-sportmonks-19732709` | Elche | Real Sociedad | `2026-09-07T19:30:00Z` |
| Bundesliga | `mth_football-sportmonks-19735185` | Eintracht Frankfurt | FC Augsburg | `2026-09-06T15:30:00Z` |
| Serie A | `mth_football-sportmonks-19713588` | Udinese | Lazio | `2026-09-07T18:45:00Z` |
| Champions League | `mth_football-sportmonks-19873242` | Sporting CP | Galatasaray | `2026-09-09T19:00:00Z` |
| MLS | `mth_football-sportmonks-19609793` | Portland Timbers | St. Louis City | `2026-09-10T02:30:00Z` |

Tous **200**, `resource_scope=structural_identity`. Aucun nom fabriqué. IDs
équipes au préfixe `tm_football-sportmonks-`. `data_mode=live` sur l’identité.

Le SQL (`matches` ⋈ `teams` ⋈ `leagues`) n’est **pas** le chemin par défaut.
`SqlMatchIdentityRepository` n’est instancié que si
`PREDICTA_API_REPOSITORY=sql`. La requête SQL ne sélectionne que `id`,
`home_team_id`, `away_team_id`, `kickoff_at`, `data_mode` et les noms. C’est
structurellement PIT, mais ce n’est pas le store utilisé par le `TestClient`
ni par la config mock.

**MATCH IDENTITY : PASS**  
**TEAM IDENTITY : PASS**  
**KICKOFF : PASS**

---

## 5. Match details

Les IDs historiques ne retournent plus 404.

Réponse = `HistoricalMatchIdentity`, pas `MatchDetail`. Clés observées :

`match_id`, `home_team_id`, `away_team_id`, `home_team`, `away_team`, `league`,
`kickoff_at`, `data_mode`, `resource_scope`.

Aucune des clés `score`, `status`, `timeline`, `stats`, `result`, `events`,
`standings`, `form`.

Le pick AI Picks et `GET /matches/{id}` pour `mth_football-sportmonks-19719892`
sont identiques sur `match_id`, `home_team`, `away_team`, `league`,
`kickoff_at`.

ID inconnu : 404 RFC 9457 (`application/problem+json`,
`type=/problems/not-found`), sans `home_team` dans le body.

Le frontend n’entre pas dans ce PASS : `getMatch` est typé `MatchDetail` et
`MatchDetailView` lit `match.home.name`, `match.sport`, `match.quality`. Une
identité historique ferait échouer le contrat client. Les cartes AI Picks
n’ont pas de lien « Voir le match ».

**MATCH DETAILS : PASS** (HTTP backend)

---

## 6. PIT

`MatchIdentity` ne contient que l’identité structurelle. Les champs
`status`, `home_score`, `away_score`, `result`, `events` sont absents du
dataclass (test `test_structural_identity_projection_cannot_carry_post_kickoff_results`).

`ParquetArchiveMatchIdentityRepository._structural_names` ne lit, dans le raw
immuable, que :

- `id` du fixture (égalité avec `match_id`) ;
- `starting_at` (égalité stricte avec `kickoff_at` parquet, sinon noms `null`) ;
- `participants[].meta.location`, `participants[].id`, `participants[].name`.

Kickoff parquet ≠ kickoff raw → noms `null`, jamais un substitut. Archive raw
absente → noms `null` (test `test_missing_structural_labels_remain_explicitly_null`).

Le JSON raw **contient** encore des données post-coup d’envoi. Exemple Arsenal
vs Chelsea (`19722183`) dans
`workers/ingestion/var/raw/live/sportmonks/2026/09/10/raw_sportmonks-fixtures-84aa3f04b7c7.json` :

- `scores` présent ;
- `state.developer_name = FT` ;
- `result_info` présent.

Le code d’identité ne les lit pas. Même pattern de co-localisation que les
labels ML dans le parquet. Ce n’est pas une fuite fonctionnelle, c’est un
risque de maintenance.

`cutoff_at` des picks = kickoff canonique. Les cotes Value Engine sont
retenues avec `available_at <= cutoff_at`.

**PIT : PASS**

---

## 7. Prediction / Value integration

Pour les deux sélections éligibles du match candidat :

| Contrôle | AWAY | DRAW |
| --- | --- | --- |
| `prediction.{sel}_probability` == `value.prediction.{sel}_probability` | True | True |
| `value.prediction` == `ai-picks.model_probability` | True | True |
| odds Value == odds AI Picks | True | True |
| implied / no-vig / edge / EV Value == AI Picks | True | True |
| `cutoff` prediction = value = pick = kickoff | `2026-07-07T16:00:00Z` | identique |

AI Picks copie les probabilités du Prediction Service via le Value Engine. Il
ne les recalcule pas. `_validate_analysis` refuse une analyse dont le cutoff,
le simplex ou le math Value Engine divergent.

`opportunity_score = EV + Edge` est le seul agrégat AI Picks, documenté.

**PREDICTION INTEGRATION : PASS**  
**VALUE INTEGRATION : PASS**

---

## 8. Frontend validation

Source active : mock. Les pages ne voient **pas** Lincoln Red Imps /
Inter Club d'Escaldes.

### `/ai-picks` (navigateur, mock succès)

Affiché :

- league, `match_id`, selection, odds, P modèle, implicite, no-vig, edge, EV ;
- warning mock (`predicta-mock-odds-v0.1`) ;
- warning candidate (`football-elo-v1-candidate`, « ni champion ni promu ») ;
- exclusions explicites ;
- sport verrouillé Football.

Non affiché, alors que le backend les publie maintenant :

- Home team ;
- vs ;
- Away team ;
- Kickoff (le cutoff est affiché, ce n’est pas le coup d’envoi du match en
  tant que champ d’identité).

Le type `AiPick` dans `apps/web/src/types/api.ts` **omet** `home_team`,
`away_team`, `kickoff_at`. Commentaire encore en vigueur :

> The engine resolves team identity and kickoff internally but does not
> publish them.

`AiPickCard` rend league + `match_id`. `AiPickDetailDialog` force
`Unavailable` : « Le moteur ai-picks-0.1 ne publie ni nom d'équipe ni
horaire ».

Les fixtures mock omettent aussi ces champs. C’est honnête pour le mock, mais
le code UI ne **peut pas** afficher l’identité même si HTTP la fournit : les
champs n’existent pas sur le type.

Le test `identifies a match by its id rather than inventing team names`
**verrouille** ce contrat périmé, y compris le texte du dialog.

### `/value-finder`

Cartes mock : Home · Away, ligue, selection, odds, probabilités, edge, EV.
Kickoff du match dans le dialog (`Coup d'envoi`), pas comme ligne dédiée sur
la carte (horodatage « cote observée »). Pas de `model_status` candidate :
c’est `GET /value` (catalogue mock), pas `GET /football/value/{id}` ni AI Picks.

Aucun inventaire d’équipe fabriqué : quand l’identité AI Picks est absente du
DTO, l’UI dit « indisponible ».

**FRONTEND : FAIL**

---

## 9. Responsive

Mesure `documentElement.scrollWidth > clientWidth` :

| Viewport | `/ai-picks` overflow | `/value-finder` overflow |
| --- | --- | --- |
| 1440 | non | non |
| 1024 | non | non (vérifié 1440 + structure identique) |
| 820 | non | — |
| 390 | non | non |

Filtres lisibles et utilisables à 390 (wrap). Cartes exploitables. Dialog AI
Picks ouvrable à 390 après `scrollIntoView` : le CTA « Détail de l'opportunité »
peut être intercepté par la barre mobile « Raccourcis » tant qu’il n’est pas
sorti du sticky footer. Ce n’est pas un overflow horizontal.

**RESPONSIVE : PASS**

---

## 10. Filters

### AI Picks

`HttpDataSource.getFootballAiPicks` envoie `date`, `league`, `limit`,
`offset`, `min_edge`, `min_ev`. Pas de `sport` (moteur football only). Le
sélecteur sport UI est disabled. Changement de seuil → nouvelle requête
moteur (test `re-queries the engine when a threshold filter changes`). Pas de
recalcul d’edge / EV / rank. `summarizeAiPicks` prend le `rank` moteur.

### Value Finder

`getValue` n’envoie que les filtres match génériques (`sport`, `date`, …).
Marché, edge min, EV min, proba min, cote min et le tri sont appliqués dans
`filterValueOpportunities` / `sortValueOpportunities` **après** réception.
Les grandeurs publiées ne sont pas ré-dérivées, mais le résultat affiché est
recalculé côté client. `GET /value` n’expose pas ces query params.

**FILTERS : FAIL** (Value Finder post-filtre ; AI Picks seul serait PASS)

Tri AI Picks : ordre backend, pas de contrôle de tri UI. Tri Value Finder :
client, documenté par le test « reorders without changing any published value ».

---

## 11. Error states

Vérifiés en navigateur et/ou tests :

| État | Surface | Observation |
| --- | --- | --- |
| Vide | Value Finder scénario Vide | « Aucun écart de value » / résultat, pas une erreur |
| Vide | AI Picks test + scénario | « Aucune opportunité éligible », pas de Réessayer |
| Erreur | Value Finder scénario Erreur | « Impossible de charger ces données » + Réessayer |
| Erreur | AI Picks test | `role=alert` + Réessayer |
| Mock | les deux pages | bannière mock + `DataModeNotice` |
| Candidate | AI Picks | `CandidateModelNotice` + badge carte |
| Sport hors couverture | AI Picks tennis | « Moteur limité au football », pas de picks inventés |
| RFC 9457 | HTTP client | parse `ProblemDetails` ; test AI Picks source 422 `min_edge` |
| 404 identité | backend | problem+json, pas d’identité mock |

Loading : `QueryBoundary` + skeletons (tests query-boundary). Pas de page
blanche sur les scénarios exercés.

L’erreur HTTP live RFC 9457 n’a pas été déclenchée depuis le navigateur :
la source frontend par défaut est mock.

**ERROR STATES : PASS**

---

## 12. OpenAPI

`npx openapi-typescript contracts/openapi.yaml --output /tmp/predicta-api.generated.ts`
(openapi-typescript 7.13.0).

`components.schemas.AiPick` généré contient `home_team: string | null`,
`away_team: string | null`, `kickoff_at`. `HistoricalMatchIdentity` est
présent. Backend Pydantic / routes alignés.

Frontend : types **handwritten** dans `apps/web/src/types/api.ts`. Ils ne
sont pas remplacés par le fichier généré (`docs/api-contract.md` génère vers
`/tmp`). Divergence actuelle : `AiPick` frontend sans les trois champs
d’identité, alors qu’ils sont `required` (nullables) dans OpenAPI.

**OPENAPI : FAIL** (backend PASS, frontend types FAIL)

---

## 13. Regression

Reproduit dans cette session, sans faire confiance aux claims :

| Gate | Commande | Résultat |
| --- | --- | --- |
| ruff | `apps/api` `ruff check app tests` | PASS |
| mypy | `apps/api` (64 fichiers) | PASS |
| pytest | `apps/api` | **135 passed** |
| eslint | `apps/web` `npm run lint` | PASS |
| tsc | `apps/web` `npm run typecheck` | PASS |
| vitest | `apps/web` `npm test` | **207 passed** |
| next build | `apps/web` `npm run build` | PASS |

Les 207 tests frontend **passent parce qu’ils attendent encore** l’identité
non publiée. Ce n’est pas une preuve que l’UI consomme le fix.

**REGRESSION : PASS**

---

## 14. Findings

### BLOCKER (1)

1. **Le frontend ne consomme pas Match Identity.**
   Types `AiPick`, cartes, dialog, fixtures mock et tests UI ignorent
   `home_team` / `away_team` / `kickoff_at`. Après `c31a367`, l’API les
   publie. L’UI continue d’afficher « Identité des équipes et coup d'envoi
   indisponible » et le `match_id`. Critère produit « Home vs Away / League /
   Kickoff sur les cartes » non atteint.

### HIGH (3)

1. **`NEXT_PUBLIC_PREDICTA_DATA_SOURCE=mock` par défaut.** Même un type
   corrigé resterait invisible tant que l’UI n’est pas branchée sur HTTP.
2. **`GET /matches/{id}` historique vs `MatchDetailView`.** Le backend
   renvoie `HistoricalMatchIdentity`. Le frontend attend `MatchDetail`
   (`home.name`, `sport`, `quality`, timeline…). Un ID historique ferait
   `invalid_response` ou un crash de rendu. AI Picks n’offre pas de lien
   match.
3. **Value Finder n’est pas le pipeline football identity-fixed.** Catalogue
   `GET /value`, filtres/tri client, pas de `model_status` candidate, pas
   d’identité AI Picks. Les seuils min edge / min EV ne sont pas transmis à
   l’API.

### MEDIUM (3)

1. Univers AI Picks V0.1 = **un** match hardcodé
   (`mth_football-sportmonks-19719892`). Les 7 ligues sont testables via
   `/matches/{id}`, pas via `/football/ai-picks`.
2. Envelope AI Picks `data_mode=mock` (cotes) alors que
   `GET /matches/{id}` du même match a `data_mode=live`. Ambigu pour l’UI
   mock warning.
3. Store d’identité par défaut = parquet + raw, pas SQL. Les payloads raw
   contiennent encore `scores` / `state=FT` / `result_info` (non lus).

---

## 15. Final Verdict

Le backend Match Identity est prêt à être consommé. Le frontend `ff4e224`
est antérieur au contrat d’identité publié et le suite de tests le fige.

GO backend identity / PIT / prediction / value. **NO-GO produit** tant que
AI Picks n’affiche pas les champs canoniques (ou un Unavailable **seulement**
quand ils sont `null`), et tant que les types OpenAPI frontend ne sont pas
alignés.

### Scorecard

```
AI PICKS API : PASS
MATCH IDENTITY : PASS
MATCH DETAILS : PASS
TEAM IDENTITY : PASS
KICKOFF : PASS
PIT : PASS
PREDICTION INTEGRATION : PASS
VALUE INTEGRATION : PASS
FRONTEND : FAIL
RESPONSIVE : PASS
FILTERS : FAIL
ERROR STATES : PASS
OPENAPI : FAIL
REGRESSION : PASS

BLOCKERS : 1
HIGH : 3
MEDIUM : 3

FINAL VERDICT : NO-GO
```

### Déblocage minimum

1. Étendre `AiPick` (types, mock, cartes, dialog) avec `home_team`,
   `away_team`, `kickoff_at` nullables. Afficher les noms **quand ils sont
   présents**. `Unavailable` seulement si `null`.
2. Inverser le test qui exige « le moteur ne publie ni nom ni horaire ».
3. Régénérer / aligner les types sur `contracts/openapi.yaml`.
4. (Recommandé) brancher `/ai-picks` sur HTTP pour vérifier Lincoln Red Imps
   vs Inter Club d'Escaldes, et accepter `HistoricalMatchIdentity` sur la
   fiche match.

Ne pas promouvoir le modèle. Ne pas brancher les cotes live pour débloquer
cette QA.
