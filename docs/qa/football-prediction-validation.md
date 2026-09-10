# Football 1X2 Prediction Service — QA Validation

**Branche validée :** `agent/backend/football-prediction-service` @ `31e714b`  
**Branche QA :** `agent/qa/football-prediction-validation`  
**Verdict :** **GO**

Le service peut passer à l’étape Odds + Value Engine. La chaîne ML → PIT → API
reproduit l’artefact candidat sans mock d’inférence, sans fuite temporelle
acceptée, et sans présenter le modèle comme production.

---

## 1. Scope

Validation de `GET /api/v1/football/predictions/{match_id}` avant Odds / EV /
Value Engine / AI Picks.

Inclus :

- parité inférence ML de référence ↔ API ;
- simplex 1X2 et bornes (0, 1) ;
- PIT / anti-leakage (`cutoff_at`) ;
- reproductibilité ;
- métadonnées candidat ;
- erreurs RFC 9457 ;
- contrat OpenAPI ;
- tests automatisés et gates `ruff` / `mypy` / `pytest` ;
- revue de `apps/api/app/predictions/` et des intégrations.

Exclus (volontairement non implémentés ici) :

- cotes, implied probability, expected value, Value Engine, recommandations ;
- modification du dataset ML ou de l’artefact ;
- promotion `champion` / production ;
- modification frontend.

`GET /api/v1/matches/{match_id}/prediction` reste le DTO frontend mock et n’est
pas remplacé.

---

## 2. Environment

| Item | Valeur |
| --- | --- |
| API commit | `31e714b feat(api): serve candidate football Elo 1X2 probabilities` |
| `model_version` | `football-elo-v1-candidate` |
| `dataset_version` | `football-1x2-history-0.3` |
| `feature_schema_version` | `football-1x2-features-0.3` |
| `model_status` | `candidate` |
| Dataset local | `workers/ingestion/var/football-1x2-history.parquet` (330K, **gitignoré**) |
| Artefact local | `workers/ml/var/registry/football-elo-v1-candidate/artefact.joblib` (**gitignoré**) |
| SHA-256 dataset | `0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5` |
| SHA-256 carte registre | identique |
| Lignes dataset | 5729, `data_mode=live` uniquement |
| Compétitions | Premier League, Ligue 1, La Liga, Bundesliga, Serie A, Champions League, MLS |
| Fenêtre événements | 2024-02-22 → 2026-09-10 |
| Harness API | `TestClient` (`PREDICTA_API_ENV=test`, repository mock, clock figée) |
| Référence ML | `predicta_ml.registry.artifact.load_registry` → `predictors["elo"].predict_diffs` → `calibrators["elo"].transform` |

Les fichiers `var/` ne sont pas versionnés. La validation ci-dessous a été
exécutée avec les copies locales présentes sur cette machine. Un clone Git
seul ne suffit pas à servir l’endpoint.

---

## 3. Tests exécutés

| Gate | Commande | Résultat |
| --- | --- | --- |
| Parité ML ↔ API (14 matchs, 7 compétitions) | probe HTTP + artefact joblib | PASS (Δ = 0.0) |
| Simplex + bornes | 14 réponses 200 + tests | PASS |
| PIT kickoff / avant / après | HTTP `cutoff_at` | PASS (200 / 422 / 409) |
| Reproductibilité | 2 appels identiques | PASS |
| RFC 9457 503 / 422 / 409 | HTTP réel | PASS |
| Contrat frontend mock | `GET /matches/{id}/prediction` | PASS (inchangé) |
| Revue de code | `app/predictions/` + router/deps/container/config/errors/schemas/OpenAPI | voir §10–11 |
| `ruff check app tests` | `apps/api` | PASS |
| `mypy` | `apps/api` (43 fichiers) | PASS |
| `pytest` | `apps/api` — 43 passed | PASS |

Référence ML : inférence directe sur l’artefact, **sans** passer par
`CandidateEloAdapter` pour le vecteur attendu, afin de détecter un bug
d’adaptateur. L’API applique ensuite `renormalize_1x2` ; l’écart maximal
observé vs sortie calibrée brute est 1 ULP (`1.11e-16`), donc négligeable.

---

## 4. ML ↔ API parity

Tolérance : égalité exacte des `float` JSON pour la sortie renormalisée.
Aucun écart documenté.

| Match | Competition | ML Home | API Home | ML Draw | API Draw | ML Away | API Away | Result |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `mth_football-sportmonks-19722183` | Premier League | 0.6070582350689889 | 0.6070582350689889 | 0.2221384101565397 | 0.2221384101565397 | 0.1708033547744714 | 0.1708033547744714 | PASS |
| `mth_football-sportmonks-19427636` | Premier League | 0.49870403668657354 | 0.49870403668657354 | 0.25567188625019976 | 0.25567188625019976 | 0.24562407706322675 | 0.24562407706322675 | PASS |
| `mth_football-sportmonks-19715615` | Ligue 1 | 0.4658083966775415 | 0.4658083966775415 | 0.26595840958359734 | 0.26595840958359734 | 0.26823319373886123 | 0.26823319373886123 | PASS |
| `mth_football-sportmonks-19433871` | Ligue 1 | 0.4763183089732987 | 0.4763183089732987 | 0.26265215844210615 | 0.26265215844210615 | 0.2610295325845951 | 0.2610295325845951 | PASS |
| `mth_football-sportmonks-19732709` | La Liga | 0.4287852650036876 | 0.4287852650036876 | 0.2755087982378774 | 0.2755087982378774 | 0.29570593675843504 | 0.29570593675843504 | PASS |
| `mth_football-sportmonks-19439410` | La Liga | 0.45683903291807254 | 0.45683903291807254 | 0.26879906202813186 | 0.26879906202813186 | 0.2743619050537956 | 0.2743619050537956 | PASS |
| `mth_football-sportmonks-19735185` | Bundesliga | 0.42126627946245054 | 0.42126627946245054 | 0.2727266122019809 | 0.2727266122019809 | 0.30600710833556866 | 0.30600710833556866 | PASS |
| `mth_football-sportmonks-19433601` | Bundesliga | 0.17247139484804005 | 0.17247139484804005 | 0.20845379447264822 | 0.20845379447264822 | 0.6190748106793118 | 0.6190748106793118 | PASS |
| `mth_football-sportmonks-19713588` | Serie A | 0.3735742608321212 | 0.3735742608321212 | 0.25831154862211475 | 0.25831154862211475 | 0.3681141905457641 | 0.3681141905457641 | PASS |
| `mth_football-sportmonks-19425048` | Serie A | 0.5818369770067714 | 0.5818369770067714 | 0.23000356293277172 | 0.23000356293277172 | 0.18815946006045692 | 0.18815946006045692 | PASS |
| `mth_football-sportmonks-19873242` | Champions League | 0.4711544720656066 | 0.4711544720656066 | 0.26427386241415685 | 0.26427386241415685 | 0.26457166552023653 | 0.26457166552023653 | PASS |
| `mth_football-sportmonks-19568492` | Champions League | 0.3245519245721345 | 0.3245519245721345 | 0.24593062023912377 | 0.24593062023912377 | 0.4295174551887417 | 0.4295174551887417 | PASS |
| `mth_football-sportmonks-19609793` | MLS | 0.42502614904415176 | 0.42502614904415176 | 0.27408995094561733 | 0.27408995094561733 | 0.30088390001023096 | 0.30088390001023096 | PASS |
| `mth_football-sportmonks-19606710` | MLS | 0.4954479951473962 | 0.4954479951473962 | 0.25668294174171796 | 0.25668294174171796 | 0.24786906311088583 | 0.24786906311088583 | PASS |

Pour chaque ligne : `home + draw + away = 1.0` exactement en JSON, et
`0 < p < 1`.

Le modèle n’utilise que `elo_diff` (plus renormalisation 1X2). Les labels
`target` / `home_win` / `draw` / `away_win` / `y` présents dans le parquet
ne sont pas injectés dans `PitEloFeatures`.

---

## 5. PIT / Temporal Leakage

Store : `ParquetPitFeatureStore` lit une ligne figée `football-1x2-history-0.3`.
`validate_elo_snapshot` est le unique garde-fou cutoff.

| `cutoff_at` | Attendu | Observé |
| --- | --- | --- |
| omis (= kickoff) | 200 si snapshot PIT | 200 |
| égal au kickoff | 200 | 200 |
| 1 s avant kickoff | 422 `/problems/pit-features-unavailable` | 422 |
| 1 s après kickoff | 409 `/problems/temporal-leakage` | 409 |
| `data_mode=mock` | 422 | 422 (store mémoire) |
| match inconnu | 422 | 422 |
| `elo_available=0` | 422 | couvert par validation (dataset 0.3 : toujours 1) |

Anti-leakage (revue + tests) :

- pas de score, résultat, événements, classement ou stats post-cutoff dans
  les features d’inférence ;
- `PitEloFeatures` n’a pas de champs label / score / standing ;
- un match ultérieur avec Elo extrême ne change pas la prédiction du match
  demandé (`test_later_match_row_cannot_leak_into_requested_match`) ;
- l’Elo n’est pas recalculé à la requête : snapshot pré-coup d’envoi uniquement ;
- refus explicite si `cutoff_at > kickoff` (pas de fallback silencieux).

Limite d’architecture (pas un défaut d’inférence) : le candidat ne possède
qu’un snapshot au kickoff. Un cutoff antérieur est refusé, même si d’autres
features historiques existeraient. C’est le comportement documenté dans
OpenAPI (`CutoffAt`).

Le parquet historique contient les labels 1X2 des matchs **terminés**. Ils
ne sont pas lus pour prédire, mais l’API ne peut servir que des `match_id`
présents dans ce fichier.

---

## 6. Reproducibility

Même `match_id` + même `cutoff_at` (omis vs kickoff explicite) :

- `home_probability` / `draw_probability` / `away_probability` identiques
  bit-à-bit ;
- `generated_at` identique sous clock figée de test (`2026-09-09T18:00:00Z`) ;
- deux chargements de l’artefact produisent le même vecteur.

Elo + calibration sigmoïde sont déterministes. Pas de RNG à l’inférence.

---

## 7. Metadata

Réponse 200 vérifiée :

| Champ | Attendu | Observé |
| --- | --- | --- |
| `model_version` | `football-elo-v1-candidate` | oui |
| `dataset_version` | `football-1x2-history-0.3` | oui |
| `feature_schema_version` | `football-1x2-features-0.3` | oui |
| `model_status` | `candidate` | oui |
| `cutoff_policy` | `pre_kickoff` | oui |
| `sport` / `market` | `football` / `1X2` | oui |
| `data_mode` (enveloppe) | `live` | oui (forcé, même si le reste de l’API test est mock) |

Aucun endpoint football 1X2 ne renvoie `model_status=champion`. Le chargeur
refuse un artefact dont le statut n’est pas `candidate`, un selected ≠ `elo`,
ou une version ≠ `football-elo-v1-candidate`.

La copie mock dashboard (`fixtures/store.py`) mentionne « champion football »
dans un insight fictif : hors de cet endpoint, non contractuel pour le modèle
candidat.

---

## 8. RFC9457 Error Handling

Tous les cas demandés ont été exercés via HTTP.

| Cas | HTTP | `type` | Content-Type | `request_id` |
| --- | ---: | --- | --- | --- |
| Artefact absent | 503 | `/problems/model-artefact-not-found` | `application/problem+json` | présent, = `X-Request-ID` |
| PIT indisponible | 422 | `/problems/pit-features-unavailable` | `application/problem+json` | présent |
| Fuite temporelle | 409 | `/problems/temporal-leakage` | `application/problem+json` | présent |

Payload : `type`, `title`, `status`, `detail`, `instance` (nullable),
`request_id`. Valide contre `ProblemDetails` OpenAPI (`additionalProperties:
false`). Pas de stack, pas de fallback JSON FastAPI `{detail: ...}`.

---

## 9. OpenAPI Contract

Comparaison `contracts/openapi.yaml` ↔ `router.py` / `FootballModelPrediction` :

| Élément | Contrat | Implémentation | Écart |
| --- | --- | --- | --- |
| Path | `/football/predictions/{match_id}` sous server `/api/v1` | `GET /api/v1/football/predictions/{match_id}` | aucun |
| Query `cutoff_at` | Timestamp optionnel | `datetime \| None` | aucun |
| 200 | `FootballModelPredictionEnvelope` | envelope + schema Pydantic | aucun |
| Probabilités | `(0, 1)` exclusif, somme 1 | `gt=0, lt=1` + validator `1e-9` | aucun |
| `model_status` | `candidate \| champion` | V1 toujours `candidate` | enum volontairement ouvert |
| 409 / 503 | `Problem` `application/problem+json` | oui | aucun |
| 422 | `ValidationProblem` (même schéma ProblemDetails) | type métier `/problems/pit-features-unavailable` | sémantique plus précise, schéma OK |
| Frontend | `/matches/{match_id}/prediction` | inchangé, `data_mode=mock` | aucun |

Pas de modification de contrat. Pas de rupture frontend : le web n’appelle
pas encore `/football/predictions/{match_id}`.

---

## 10. Automated Tests

Fichiers examinés puis étendus :

- `apps/api/tests/test_football_prediction_service.py`
- `apps/api/tests/test_football_prediction_api.py`

Trous identifiés avant QA (couverts maintenant) :

- parité ML ↔ API multi-compétitions ;
- `cutoff_at` strictement avant kickoff côté HTTP ;
- RFC 9457 complet (Content-Type, `request_id`, schéma) pour 409/422/503 ;
- `cutoff_policy` et bornes de probabilités ;
- snapshot PIT sans labels ;
- SHA-256 dataset runtime = carte d’artefact.

Déjà présents et conservés : artefact 503, PIT 422, leakage 409, simplex,
refus des rows mock, isolation inter-matchs, DTO frontend mock inchangé.

---

## 11. Findings

### BLOCKER

Aucun.

### HIGH

1. **Artefact et dataset gitignorés (`var/`).** L’API charge
   `workers/ml/var/registry/football-elo-v1-candidate/artefact.joblib` et
   `workers/ingestion/var/football-1x2-history.parquet`. Un déploiement ou une
   CI depuis Git seul obtiendra 503/422. **Ne pas « corriger » dans cette
   branche.** Correction séparée recommandée : publier l’artefact candidat et
   le parquet 0.3 dans un registry/object store versionné, pinner SHA-256
   (déjà dans `registry.json`), et échouer au boot si le hash diverge.
2. **Surface de serving = matchs déjà présents dans le parquet historique.**
   Les 5729 lignes sont des matchs terminés (labels 1X2 dans le fichier).
   Un fixture à venir absent du parquet → 422. Odds + Value Engine peuvent
   démarrer **sur ce set historique**. Un serving pre-match live exigera un
   store PIT distinct (hors scope).

### MEDIUM

1. Les tests live font `pytest.fail` si `var/` est absent (volontaire : pas de
   mock d’inférence). Même dépendance que le HIGH #1 pour la CI.
2. Labels post-match cohabitent dans le parquet avec les features Elo. Isolation
   code OK ; un futur store « live » ne devra pas charger `target` / `y` pour
   inférer.

### LOW

1. Starlette déprécie `HTTP_422_UNPROCESSABLE_ENTITY` au profit de
   `UNPROCESSABLE_CONTENT`. Cosmétique, hors comportement métier.
2. Insight mock dashboard parle d’un « champion football » : fiction UI, pas
   l’endpoint candidat.
3. OpenAPI nomme la 422 `ValidationProblem` alors que PIT est un 422 métier.
   Le schéma reste `ProblemDetails`.

### INFO

- `data_mode=live` est forcé sur cet endpoint même lorsque le catalogue reste
  mock : cohérent (vraies features PIT) mais hybride pour le client.
- Double renormalisation (`clip_proba` ML puis `renormalize_1x2` API) : écart
  ≤ 1 ULP.
- `generated_at` est tronqué à la seconde (`to_rfc3339`).
- Aucun mock d’inférence en runtime. `InMemoryPitFeatureStore` est test-only.

---

## 12. Final Verdict

**GO**

La chaîne ML → PIT → API est assez fiable pour commencer l’intégration des
cotes et du Value Engine **sur les matchs du dataset 0.3**.

Conditions de poursuite (hors cette branche) :

- ne pas promouvoir le candidat ;
- ne pas brancher le DTO frontend mock sur ce nouvel endpoint sans décision
  produit ;
- traiter le provisioning d’artefact/dataset (HIGH #1) avant un deploy hors
  machine de développement ;
- garder Value Engine déterministe à partir de ces probabilités, sans relire
  les labels pour « corriger » une cote.

**NO-GO n’est pas retenu** : aucun écart ML/API, aucune fuite temporelle
acceptée, aucun modèle mocké, métadonnées candidat correctes.
