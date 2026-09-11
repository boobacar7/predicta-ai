# Football AI Analyst — Validation e2e indépendante

**Branche :** `agent/frontend/ai-analyst`  
**Commit frontend :** `ccad413 feat(web): add football ai analyst experience`  
**Commit backend :** `ee23cff fix(api): clarify ai analyst semantics and grounding`  
**Modèle :** `football-elo-v1-candidate` (`model_status=candidate`) — **non production**  
**Provider :** `deterministic-v0.1` — aucune dépendance LLM  
**`analysis_version` :** `ai-analyst-0.1`  
**Verdict :** **GO WITH CONDITIONS**

Aucun BLOCKER. Les invariants critiques du flux principal tiennent : PIT,
séparation `model_favorite` / `value.value_selection`, copie frontend des
métriques backend, candidat non promu, erreurs HTTP non masquées par un mock.

Les conditions sont des limites documentées. Elles n’autorisent pas à brancher
un LLM, ni à présenter la value comme un pick.

---

## 1. Executive Summary

L’AI Analyst football est une **couche explicative**. Sur le cas réel
`mth_football-sportmonks-19719892` :

| Concept | Valeur observée | Métriques associées |
| --- | --- | --- |
| `model_favorite` | **HOME** (Lincoln Red Imps) | probabilités HOME 41,6 % (API) / 41,7 % (fixture mock) |
| `value.selection` | **HOME** | cote 2,00 · implicite 50 % · EV **-16,7 %** |
| `value.value_selection` | **AWAY** (Inter Club d'Escaldes) | EV Value Engine **+56,3 %** — **hors DTO analyste** |

Le backend ne mélange jamais EV HOME et EV AWAY. Le frontend ne recalcule
ni favori, ni EV, ni ranking. L’UI mock affiche « Favori du modèle · Domicile »
et « Valeur détectée · Extérieur », avec un disclaimer explicite : les mesures
copiées sont celles du favori, pas de la valeur détectée.

`assert_grounded` protège les **facteurs numériques** et les DTOs. Il ne
protège pas le **texte** du résumé : un provider malveillant peut écrire
« HOME 80 % » dans `summary` sans changer `prediction.home_probability`.
Le provider actuel, déterministe, ne le fait pas. C’est la condition
principale avant tout LLM.

---

## 2. Scope

Inclus :

1. Backend AI Analyst (`ee23cff` + `47871b1` inclus)
2. API / OpenAPI `GET /football/ai-analyst/{match_id}`
3. Frontend `/ai-analyst`, redirect `/analyst`, DataSource mock / HTTP
4. Dark / Light, persistance, SSR / hydration
5. Prediction `football-elo-v1-candidate`
6. Value Engine v0.1 (lecture seule, non modifié)
7. PIT / anti-temporal leakage
8. Grounding / anti-hallucination (provider malveillant)
9. Régression frontend + backend

Exclus volontairement :

- correction de code produit (cette QA n’a rien corrigé)
- promotion du modèle candidat
- branchement d’un provider LLM ou de cotes live
- modifications locales non commises présentes au démarrage de l’audit

---

## 3. Commits audited

| SHA | Message |
| --- | --- |
| `ee23cff53c7602b7f5df3cfadcb25ef3b1339430` | `fix(api): clarify ai analyst semantics and grounding` |
| `ccad4133124e072c16332423cc63a599127c741c` | `feat(web): add football ai analyst experience` |

HEAD de la branche au moment de l’audit : `ccad413`.

Des edits locales non commises existaient sur
`model-favorite-badge.tsx`, `value-information.tsx` et
`ai-analyst-view.test.tsx`. Elles ont été **exclues**. L’UI audité est celui
de `ccad413` (« Domicile » / « Extérieur »), pas un WIP HOME/AWAY.

---

## 4. Architecture

Pipeline observé, conforme à la spec :

```text
identity PIT
  → Prediction Service (football-elo-v1-candidate)
  → Value Engine (optionnel)
  → AnalystContext (frozen)
  → AnalystProvider.generate_analysis(context)
  → assert_grounded
  → FootballAiAnalystReport
  → GET /api/v1/football/ai-analyst/{match_id}
  → DataSource.getFootballAiAnalyst
  → AiAnalystView (copie, pas de calcul métier)
```

`AnalystContext` est `@dataclass(frozen=True, slots=True)`. Une assignation
`context.data_mode = "live"` lève `FrozenInstanceError`.

Le service reconstruit `prediction` et `value` depuis le contexte, **pas**
depuis la sortie du provider. `generated_at` est copié du contexte (horloge
injectable). `DeterministicAnalystProvider` n’a ni I/O, ni `datetime.now`,
ni réseau.

Aucune dépendance `openai` / `anthropic` / `litellm` / `langchain` dans
`apps/api/pyproject.toml`.

---

## 5. API

`GET /api/v1/football/ai-analyst/mth_football-sportmonks-19719892` → **200**.

Envelope : `data_mode=mock`, `request_id` propagé, `X-Request-ID` aligné.

Champs critiques du cas Lincoln (TestClient, horloge `2026-09-09T18:00:00Z`) :

| Champ | Valeur |
| --- | --- |
| `home_team` | Lincoln Red Imps |
| `away_team` | Inter Club d'Escaldes |
| `kickoff_at` | `2026-07-07T16:00:00Z` |
| `model_favorite` | HOME |
| `prediction.model_version` | football-elo-v1-candidate |
| `prediction.model_status` | candidate |
| `prediction.home_probability` | 0.41636357413992076 |
| `prediction.away_probability` | 0.31261487997008847 |
| `value.availability` | available |
| `value.selection` | HOME |
| `value.value_selection` | AWAY |
| `value.odds` | 2.0 (HOME) |
| `value.ev` | -0.1672728517201585 (HOME) |
| `analyst.analysis_version` | ai-analyst-0.1 |
| `analyst.provider` | deterministic-v0.1 |
| `analyst.confidence.level` | medium |

Erreurs RFC 9457 vérifiées :

| Cas | Status | `type` |
| --- | --- | --- |
| match inconnu | 404 | `/problems/not-found` |
| cutoff − 1 µs | 422 | `/problems/pit-features-unavailable` |
| cutoff + 1 µs | 409 | `/problems/temporal-leakage` |
| timestamp invalide | 400 | `/problems/validation` |
| artefact absent | 503 | `/problems/model-artefact-not-found` |

`Content-Type: application/problem+json`, `title`, `detail`, `request_id`
présents. Deux appels identiques reproduisent `prediction`, `value`,
`summary`, `key_factors` et `analyst.generated_at`.

---

## 6. Prediction

Le rapport analyste **copie** `GET /football/predictions/{match_id}` :

- `home` / `draw` / `away` identiques au bit près
- `model_version=football-elo-v1-candidate`
- `model_status=candidate`
- `cutoff_at` = kickoff

Le frontend `ModelOutlook` lit `report.prediction.*` et
`report.model_favorite`. Aucun `Math.max`, aucun ranking, aucun favori
dérivé dans les composants analyste. `ProbabilityOverview` affiche HOME /
DRAW / AWAY tels quels.

Le fixture mock utilise `home_probability=0.4165` → **41,7 %**. L’API
sert 0.41636… → résumé backend **41,6 %**. Écart de fixture, pas un
recalcul UI (F-04).

---

## 7. Value Engine

Value Engine **non modifié**. Replay indépendant :

```text
EV = (p × odds) − 1
HOME : 0.41636 × 2.00 − 1 = -0.1673   (−16,7 %)
AWAY : 0.31261 × 5.00 − 1 = +0.5631   (+56,3 %)
DRAW :                          +0.0841
```

`value.odds`, `implied_probability`, `no_vig_probability`, `edge`, `ev` du
rapport analyste sont ceux de **HOME** (`value.selection`), pas d’AWAY.

`value_engine_version=value-engine-0.1`. Absence de cotes →
`availability=unavailable`, tous les champs numériques `null`, aucun
nombre inventé.

---

## 8. Model favorite vs Value

C’est le test le plus important. Challengé hors des tests existants.

### Cas réel Lincoln

| Côté | Rôle | EV Value Engine | DTO analyste |
| --- | --- | --- | --- |
| HOME | favori modèle | −16,7 % | `model_favorite`, `value.selection`, `value.ev` |
| AWAY | meilleure EV | +56,3 % | `value.value_selection` seulement |

`value.ev` **n’est pas** l’EV AWAY. Différence observée > 0.1.

### Matrice sémantique (service isolé)

| Favori | Meilleur EV | `model_favorite` | `value.selection` / `ev` | `value_selection` |
| --- | --- | --- | --- | --- |
| HOME 60 % | AWAY (cotes 1.40 / 4.00 / 6.25) | HOME | HOME / −16 % | AWAY |
| AWAY 60 % | HOME (cotes 6.00 / 4.00 / 1.40) | AWAY | AWAY / −16 % | HOME |
| DRAW 44 % | HOME (cotes 5.50 / 2.10 / 3.80) | DRAW | DRAW / EV DRAW | HOME |

Tie-break HOME > DRAW > AWAY confirmé (HOME 0.4 = DRAW 0.4 → HOME).

### UI (`ccad413`, mock)

- Model Outlook : HOME 41,7 % marqué « Favori »
- Chip favori : « Favori du modèle · Domicile » (pas le token HOME, pas le nom d’équipe)
- Chip valeur : « Valeur détectée · Extérieur » (pas AWAY, pas Inter Club)
- Disclaimer : « Mesures copiées pour le favori du modèle (Domicile), pas pour la valeur détectée »
- EV affiché : −16,7 % — **jamais** +56,3 %
- Langage : « informative », « pas une recommandation ». Aucun pick / bet / mise conseillée

Les métriques affichées sont celles de HOME. Elles ne sont **pas** collées
silencieusement sur AWAY. L’EV AWAY n’est tout simplement pas dans le
contrat analyste V0.1 (F-03).

---

## 9. Grounding

`AnalystEvidence` expose une whitelist. `assert_grounded` refuse :

- un `source` hors contexte
- un facteur value (`edge`, `ev`, `market_probability`, `data_freshness`) si `value is None`
- une `factor.value` absente de l’ensemble des nombres du contexte
- le vocabulaire interdit (`garanti`, `safe bet`, `blessure`, …)

Provider malveillant qui pose `model_probability=0.80` en facteur :
**rejeté** (`Factor value 0.8 is not present in AnalystContext`).

Les DTOs restent immunisés : même si le résumé est empoisonné,
`prediction.home_probability` reste 0.60.

Limite réelle (F-01) : les **nombres du résumé** ne sont pas scorés contre
l’evidence. Un provider peut écrire « 80,0 % » et « Cote 9.99 » dans
`summary`. Un nom propre inventé (« Real Madrid ») passe aussi (F-01).

Cela ne se produit pas avec `deterministic-v0.1`. Cela cassera la frontière
annoncée dès qu’un LLM sera branché.

---

## 10. Anti-hallucination

Contextes minimaux, provider déterministe :

| Contexte | Résultat |
| --- | --- |
| Team A vs Team B, p=0.60/0.25/0.15, cote HOME 1.80 | résumé borné à ces faits |
| odds retirées | plus d’assertion d’implicite / edge / EV ; phrase d’absence explicite ; aucun facteur `edge`/`ev` |
| identity nulle | « l'équipe à domicile » ; Team A / Team B absents |

Le texte d’absence mentionne encore les mots « cote », « edge », « EV »
pour dire qu’ils ne sont **pas** affirmés. Ce n’est pas une invention de
valeur.

---

## 11. PIT

Chaîne Prediction → Value → Analyst.

| Check | Résultat |
| --- | --- |
| cutoff − 1 µs | 422 PIT features unavailable |
| cutoff = kickoff | 200 |
| cutoff + 1 µs | 409 temporal leakage |
| `odds.available_at` > cutoff | `OddsTemporalLeakageError` |
| `metadata.cutoff_at` > prediction cutoff | `TemporalLeakageError` |
| snapshot post-cutoff seul | 409 côté odds, pas de cote inventée |
| snapshot ancien complet + récent incomplet | **ancien complet** |
| snapshot post-cutoff ignoré si un snapshot pré-cutoff existe | pré-cutoff |
| marché 1X2 incomplet | `IncompleteOddsMarketError` → value `unavailable` |

`OddsService.market_at` filtre `available_at <= cutoff_at`, puis prend le
dernier snapshot **complet**. L’analyste ne contourne pas ce PIT :
`_validate_value_cutoff` refuse `available_at > prediction.cutoff_at`.

---

## 12. Data Mode

- Envelope `data_mode` = `report.analyst.data_quality.data_mode`
- `identity=live` **et** `value.data_mode=live` → `live`
- sinon → `mock` (y compris identité live + cotes mock)

Frontend : `DataModeNotice` lit **`envelope.data_mode`**, pas
`NEXT_PUBLIC_PREDICTA_DATA_SOURCE`. Warning « Mock data » si et seulement
si `data_mode=mock`.

`createDataSource` route `football_ai_analyst` indépendamment.
HTTP down sur l’analyste n’est **pas** remplacé par `MockDataSource`
(test factory : HTTP error + session mock toujours mock). 503/409 UI :
panneau RFC 9457, pas le rapport Lincoln.

---

## 13. Frontend

- `/ai-analyst` → `AiAnalystView`
- `/analyst` → redirect `/ai-analyst` (vérifié en navigateur)
- Aucun `fetch` dans les composants analyste
- `useFootballAiAnalyst` → `source.getFootballAiAnalyst(matchId, cutoffAt?)`
- `HttpDataSource` : `GET /football/ai-analyst/{match_id}`
- `MockDataSource` : fixtures déterministes
- Types : alias de `components["schemas"]` générés

États : loading (skeleton, aucun chiffre), empty 404, RFC 9457 409/422/503,
identité partielle → « Information indisponible vs … », kickoff invalide →
pas d’`Invalid Date`, tennis → empty « Analyste limité au football ».

Le sélecteur de match est câblé sur les IDs mock (F-05). En HTTP, un ID
synthétique 404 correctement.

---

## 14. Dark / Light Theme

| Check | Résultat |
| --- | --- |
| défaut | `data-theme=dark`, `DEFAULT_THEME=dark` |
| dark → light | toggle `aria-label="Activer le thème clair"` → light |
| persistance | `localStorage["predicta-theme"]="light"` |
| reload / `/analyst` | light conservé, chiffres 41,7 / −16,7 inchangés |
| AI Picks | light, `aria-pressed` |
| Value Finder | light |
| Match Details | light |
| Performance / charts | tests unitaires : séries identiques dark/light |

Script inline avant hydrate + `suppressHydrationWarning` sur `<html>`.
`useSyncExternalStore` avec snapshot serveur = dark. Risque résiduel de
flash d’icône du toggle si le stored est light (F-08), pas de mismatch
métier.

---

## 15. Accessibility

- Toggle : `aria-label`, `aria-pressed`, nom accessible, `sr-only` « Thème actuel »
- Focus visible observé sur le toggle
- Headings : h1 AI Analyst, h2 Model Outlook / Information de valeur / Confiance
- Favori / valeur : texte, pas seulement la couleur (violet vs vert)
- Candidate : badge « Candidat » + notice textuelle
- Risques : puce + texte
- Confiance : « Moyenne » / « Faible », jamais haute sur le candidat
- Region « Match analysé » + combobox nommé

Le facteur `model_status` affiche « Information indisponible » parce que
`value=null` (F-06). Le statut réel est ailleurs (Data Quality).

---

## 16. Responsive

Vérifié : 1440, 1024, 820, 390 (dark et light pour le flux principal).

| Viewport | Overflow horizontal | Notes |
| --- | --- | --- |
| 1440 | non (`scrollWidth=clientWidth`) | sidebar + cards |
| 1024 | non | |
| 820 | non | nav hamburger « Ouvrir la navigation » |
| 390 | non (`390/390`) | cartes empilées, favorite/value séparés |

Aucun CTA de pari. Capture 390 instrumentée en overflow ; screenshot
automatique 390 a échoué côté harness visuel, le DOM a été mesuré.

---

## 17. Errors

| Cas | UI |
| --- | --- |
| loading | skeleton, aucun 41,7 % |
| 404 | empty « Aucune analyse disponible » |
| 409 | alert RFC 9457, **pas** de retry |
| 422 | alert, pas de retry |
| 503 | alert + `request_id` + Réessayer |
| tennis | empty football-only, pas de fixture |

409 observé : `409 · Temporal leakage` /
`/problems/temporal-leakage` / `request_id req_mock_ui_prototype`.
Aucune substitution silencieuse par le rapport Lincoln.

---

## 18. OpenAPI

```text
cd apps/web && npm run generate:api-types
git diff apps/web/src/types/generated/api.ts
```

**Diff vide.**

Le frontend alias `FootballAiAnalystReport` et sous-schémas depuis
`types/generated/api.ts`. `model_favorite`, `value.value_selection`,
`value.selection`, `confidence`, `analysis_version` sont dans le contrat
généré.

---

## 19. Regression

| Gate | Résultat |
| --- | --- |
| Frontend `npm test` | **267 passed** / 267 |
| Frontend `npm run lint` | OK |
| Frontend `npm run typecheck` | OK |
| Frontend `npm run build` | OK (`/ai-analyst`, `/analyst` générés) |
| Backend `ruff check app tests` | All checks passed |
| Backend `mypy` | Success, 71 source files |
| Backend `pytest` | **154 passed** / 154 |

Annoncé : 267 frontend, 154 backend. **Reproduit.**

Harness indépendant (hors repo, `/tmp/qa_football_ai_analyst_e2e.py`) :
Lincoln, matrice sémantique, PIT µs, RFC 9457, confiance, DTO grounding,
déterminisme provider → PASS. Deux FAIL volontaires de challenge
(résumé 80 %, nom inventé). Un FAIL faux positif (`"random"` dans le mot
« randomness » du docstring).

---

## 20. Performance

Pas de boucle de requêtes observée. Un `useQuery` par `matchId`.
Provider déterministe sans réseau. Formatage d’affichage seulement
(`formatProbability`, `Math.round` sur l’âge des cotes en secondes).
Aucun recalcul d’EV. Rien à signaler au-delà du normal React Query.

---

## 21. Findings

### F-01 — `assert_grounded` ne borne pas les nombres ni les entités du résumé

- **Severity :** HIGH
- **Component :** `apps/api/app/ai_analyst/grounding.py`
- **Evidence :** provider qui réécrit `summary` en « 80,0 % … Cote 9.99, EV +200% » → rapport 200, DTO HOME toujours 0.60. « Real Madrid est favori » accepté sur un contexte sans noms.
- **Reproduction :** `SummaryOnlyHallucinationProvider` / `InventTeamProvider` injectés dans `FootballAnalystService.explain`.
- **Impact :** un futur LLM peut narrer des probabilités ou des équipes hors contexte. Les DTOs restent justes ; l’explication, non.
- **Recommendation :** scorer tout nombre du résumé/factors/risks contre `AnalystEvidence` ; refuser les tokens hors whitelist d’identité.
- **Blocking :** NO — le provider actuel est déterministe et grounded. Condition bloquante **avant** un LLM.

### F-02 — Match Details historique sans deep-link AI Analyst

- **Severity :** HIGH
- **Component :** `apps/web/src/features/matches/match-detail-view.tsx`
- **Evidence :** `HistoricalIdentityContent` n’a pas le lien. Lincoln
  (`mth_football-sportmonks-19719892`) est ce variant. Le lien
  `Ouvrir dans l'AI Analyst` n’existe que sur `MatchDetail` catalogue, avec
  `?match_id=mth_northgate_harbor`, id **hors** univers analyste → 404.
- **Reproduction :** `/matches/mth_football-sportmonks-19719892` vs
  `/matches/mth_northgate_harbor`.
- **Impact :** le match canonique n’a pas le parcours Match Details → Analyst.
  `/ai-analyst` reste utilisable via la nav et le sélecteur.
- **Recommendation :** lier `identity.match_id` depuis l’identité archivée ;
  ne pas lier un id catalogue non couvert.
- **Blocking :** NO

### F-03 — L’EV AWAY n’est pas exposée par le DTO analyste

- **Severity :** MEDIUM
- **Component :** `AnalystContext.to_value_dto` + `ValueInformation`
- **Evidence :** contrat OpenAPI : `odds`/`ev` portent sur `value.selection`
  (favori). AWAY +56,3 % n’apparaît nulle part sur `/ai-analyst`.
- **Reproduction :** comparer `GET /football/value/{id}` et le rapport analyste.
- **Impact :** « Valeur détectée · Extérieur » n’est pas vérifiable dans la page.
  Ce n’est pas un swap HOME/AWAY ; c’est une absence contractuelle.
- **Recommendation :** documenter, ou ajouter un bloc informatif
  `value_selection` **copié** du Value Engine (sans recalcul frontend).
- **Blocking :** NO

### F-04 — Fixture mock 41,7 % vs API 41,6 %

- **Severity :** MEDIUM
- **Component :** `apps/web/src/data/mock/ai-analyst.ts`
- **Evidence :** mock `0.4165` → 41,7 %. API `0.416363…` → résumé 41,6 %.
- **Reproduction :** UI mock vs `TestClient` GET analyst.
- **Impact :** HTTP vs mock ne racontent pas le même arrondi. Pas un
  recalcul UI.
- **Recommendation :** aligner la fixture sur le payload API.
- **Blocking :** NO

### F-05 — Sélecteur de match hardcodé sur les fixtures mock

- **Severity :** MEDIUM
- **Component :** `AiAnalystView` `SELECTABLE_IDS` / `analystMatchOptions`
- **Evidence :** import depuis `@/data/mock/ai-analyst` pour le picker, même
  si la ressource est HTTP.
- **Impact :** en HTTP, « Identité partielle » 404. Le `match_id` d’URL reste
  le contrat correct.
- **Recommendation :** ne lister que des ids servis par la source active.
- **Blocking :** NO

### F-06 — Facteur `model_status` rendu « Information indisponible »

- **Severity :** MEDIUM
- **Component :** `formatFactorValue` + `KeyFactors`
- **Evidence :** `value: null` → `UNKNOWN_IDENTITY_LABEL`. Le statut
  `candidate` est pourtant publié ailleurs.
- **Impact :** faux vide à côté d’un facteur qui existe.
- **Recommendation :** afficher `model_status` depuis
  `report.prediction.model_status`, ou ne pas émettre un facteur numérique nul.
- **Blocking :** NO

### F-07 — Labels Domicile/Extérieur au lieu de HOME/AWAY + noms d’équipe

- **Severity :** LOW
- **Component :** `ModelFavoriteBadge`, `ValueInformation`
- **Evidence :** UI `ccad413` : « Favori du modèle · Domicile », « Valeur
  détectée · Extérieur ». Lincoln / Inter Club seulement dans le titre.
  Model Outlook utilise déjà HOME/DRAW/AWAY.
- **Impact :** dualité de vocabulaire. Sémantique conservée via le disclaimer.
- **Recommendation :** afficher le token backend (HOME/AWAY) **et** le nom
  d’équipe publié, sans inventer.
- **Blocking :** NO

### F-08 — Hydration thème : snapshot serveur toujours dark

- **Severity :** LOW
- **Component :** `theme-store.getServerThemeSnapshot` + script inline
- **Evidence :** `getServerThemeSnapshot()` = dark. Couleurs page corrigées
  par le script `localStorage`. L’icône du toggle peut diverger un frame.
- **Impact :** cosmétique. Chiffres métier inchangés.
- **Recommendation :** acceptable V0.1 ; garder le script inline.
- **Blocking :** NO

---

## 22. Final Verdict

**GO WITH CONDITIONS**

Invariants essentiels **validés** :

- HOME favori / AWAY value_selection, métriques HOME copiées, pas d’EV AWAY collée sur HOME
- frontend = présentation, pas moteur de picks
- candidat jamais high / jamais production
- PIT µs + snapshots
- data_mode backend, pas d’env guessing
- RFC 9457, pas de mock de substitution
- OpenAPI types inchangés
- 267 + 154 tests verts
- thème dark défaut, persistance light, responsive sans overflow

Conditions d’exploitation :

1. **Ne pas brancher de LLM** tant que F-01 n’est pas fermé.
2. Le parcours Match Details → AI Analyst du match PIT n’existe pas (F-02) ;
   entrer par `/ai-analyst`.
3. L’analyste V0.1 explique le **favori modèle**. L’EV de
   `value_selection` se lit sur Value Engine / AI Picks (F-03).
4. UI locale mock : arrondi 41,7 % (F-04). HTTP : 41,6 %.
5. Modèle toujours `candidate`, cotes mock, pas un produit de paris.

Aucun finding **Blocking: YES**.
