# Football fullstack E2E — Lincoln

**Branche QA :** `agent/qa/fullstack-football-e2e`  
**Base CI :** `agent/infra/ci-foundation` @ `24f8168`  
**Cutover inclus :** `agent/frontend/football-product-cutover` @ `d169927`  
**Modèle :** `football-elo-v1-candidate` (`model_status=candidate`) — **non production**  
**Odds :** `predicta-mock-odds-v0.1` (`data_mode=mock`)  
**Value Engine :** `value-engine-0.1`  
**AI Picks :** `ai-picks-0.1`  
**AI Analyst :** `ai-analyst-0.1` — narrative LLM **untrusted**  
**Verdict :** **GO WITH CONDITIONS**

Aucun BLOCKER. Le parcours Lincoln
Dashboard → Match Details → Prediction → Value → AI Picks → AI Analyst
partage une seule vérité métier. Le candidat n’est pas promu. Aucun
fournisseur live n’est branché. Les erreurs HTTP ne retombent pas sur un
mock.

---

## 1. Executive summary

Sur `mth_football-sportmonks-19719892` (Lincoln Red Imps vs Inter Club
d'Escaldes, Champions League, kickoff `2026-07-07T16:00:00Z`) :

| Couche | Source | Observation |
| --- | --- | --- |
| Identité | `GET /matches/{id}` | `data_mode=live`, identité structurelle uniquement |
| Prediction | `GET /football/predictions/{id}` | PIT `data_mode=live`, candidat Elo, simplex = 1 |
| Odds / Value | `GET /football/value/{id}` | provider mock explicite, `data_mode=mock` |
| AI Picks | `GET /football/ai-picks` | copies Prediction + Value, ranking déterministe |
| AI Analyst | `GET /football/ai-analyst/{id}` | même contexte, LLM jamais rendu directement |

Prediction live/PIT et odds mock **coexistent** et restent distinguables.

---

## 2. Environment

| Item | Valeur |
| --- | --- |
| Match | `mth_football-sportmonks-19719892` |
| HOME / AWAY | Lincoln Red Imps / Inter Club d'Escaldes |
| League | Champions League |
| Kickoff / cutoff | `2026-07-07T16:00:00Z` / `pre_kickoff` |
| Harness | FastAPI `TestClient`, horloge `2026-09-09T18:00:00Z` |
| Artefact | `workers/ml/var/registry/football-elo-v1-candidate/artefact.joblib` (**gitignoré**) |
| PIT | `workers/ingestion/var/football-1x2-history.parquet` (**gitignoré**) |
| Archive raw | `workers/ingestion/var/raw` (**gitignoré**) |

Un clone nu **skip** explicitement (`gitignored PIT parquet / football-elo-v1-candidate artefact / raw archive are absent; CI does not download live sports data`). En local avec `var/`, le modèle réel est chargé. Il n’est jamais mocké.

---

## 3. Lincoln business truth (HTTP réel)

| Champ | Valeur |
| --- | --- |
| HOME | 0.41636357413992076 (41,6 %) |
| DRAW | 0.2710215458899908 (27,1 %) |
| AWAY | 0.31261487997008847 (31,3 %) |
| `model_favorite` | HOME |
| Odds mock | HOME 2.00 / DRAW 4.00 / AWAY 5.00 |
| Overround `Σ implied` | 0.95 |
| EV HOME | −0.1672728517201585 |
| EV AWAY | +0.5630743998504424 |
| AI Picks rank 1 | AWAY (`opportunity_score` 0.6756892798205308) |
| AI Picks rank 2 | DRAW |
| Exclusion HOME | `negative_ev` |
| `value_selection` Analyst | AWAY |
| `value.selection` Analyst | HOME (favori, EV HOME) |

Les formules `value-engine-0.1` sont reproduites à partir des cotes et des
probabilités publiées :

- `implied = 1 / odds`
- `overround = Σ implied`
- `no_vig = implied / overround`
- `edge = model_probability - implied`
- `EV = model_probability × odds − 1`

---

## 4. Coverage

### API — `tests/test_football_fullstack_e2e.py`

1. Identité partagée (`match_id`, HOME/AWAY, league, kickoff)
2. Prediction candidat, PIT `data_mode`, simplex, parité artefact joblib, pas de score/résultat
3. Odds mock identifiés, snapshot PIT `available_at` < kickoff
4. Value Engine cohérent avec Prediction/Odds
5. AI Picks copies + ranking déterministe + exclusion structurée
6. AI Analyst même prediction/value/identité/model_status
7. Isolation mock/live, pas de fallback silencieux
8. Cutoff valide / avant kickoff (422) / après kickoff (409) / snapshot odds absent (422)
9. Même claims + narratives malveillantes ⇒ même résumé LLM
10. Surface HTTP ne promeut pas le candidat

### Frontend

- `features/e2e/football-fullstack-lincoln.test.tsx` — parcours des 5 vues
- `lib/football/no-frontend-business-math.test.ts` — endpoints canoniques, pas de recalcul EV/no-vig/edge/ranking/favorite
- `lib/football/value-rows.test.ts` — copie des lignes publiées, même si incohérentes

Dashboard, Match Details et Value Finder lisent `/football/value` et
`/football/predictions` (cutover). AI Picks → `/football/ai-picks`. AI Analyst →
`/football/ai-analyst`.

---

## 5. Quality gates

| Gate | Résultat |
| --- | --- |
| `verify:api` ruff + mypy + pytest | **534 passed** |
| dont fullstack E2E | **7 passed** (exécution réelle, `var/` présent) |
| `verify:ingestion` | **107 passed** |
| `verify:ml` | **27 passed** |
| `verify:web` OpenAPI / tsc / eslint / vitest / next build | **283 passed**, types inchangés, build OK |

OpenAPI non modifié. Tests existants non réécrits pour faire passer l’E2E.

---

## 6. Findings

Aucun BLOCKER. Aucun HIGH.

### L-01 — Fixtures frontend HOME arrondies

- **Severity :** LOW
- **Evidence :** mock `lincolnFootballPrediction.home_probability = 0.4165` vs HTTP `0.41636357413992076`. Affichage 41,7 % dans les deux cas.
- **Impact :** le prototype mock n’est pas bit-exact avec le candidat. Le backend E2E l’est.
- **Blocking :** NO

### L-02 — Copy Match Details encore « prédiction indisponible »

- **Severity :** LOW
- **Evidence :** la page Lincoln affiche les panneaux `GET /football/predictions` et `GET /football/value`, puis un `Unavailable` « Statistiques, cotes, prédiction et chronologie » pour l’identité archivée.
- **Impact :** confusion de lecture, pas de chiffre inventé.
- **Blocking :** NO

### L-03 — AI Picks mock contient d’autres matchs fictifs

- **Severity :** LOW
- **Evidence :** le DataSource mock liste Silverpark / Castleford en plus de Lincoln. L’API HTTP n’évalue que `PREDICTA_API_AI_PICKS_CANDIDATE_MATCH_IDS` (Lincoln).
- **Impact :** le prototype UI est plus large que l’univers moteur. Les figures Lincoln restent copiées.
- **Blocking :** NO

---

## 7. Conditions du GO

1. `football-elo-v1-candidate` reste **candidate**, pas production.
2. Les cotes restent **mock** (`predicta-mock-odds-v0.1`). Pas de provider live.
3. Le calendrier Dashboard reste un catalogue prototype (`fb-ens-*`), explicitement labellisé, distinct du moteur.
4. Cette branche QA **inclut** le merge du cutover frontend. `agent/infra/ci-foundation` seul n’expose pas encore Dashboard / Value Finder sur `/football/*`.
5. Le narrator LLM reste derrière le renderer ; le défaut HTTP est `deterministic-v0.1`.

Hors conditions : ne pas ajouter Postgres/Redis, vendor LLM, ni second Value Engine / ranking.

---

## 8. Reproduction

```bash
# Clone nu : skip documenté
npm run test:api -- tests/test_football_fullstack_e2e.py

# Local avec var/ : exécution réelle contre l’artefact candidat
PATH="apps/api/.venv/bin:$PATH" npm run verify:api
npm run test --prefix apps/web -- src/features/e2e/football-fullstack-lincoln.test.tsx
```
