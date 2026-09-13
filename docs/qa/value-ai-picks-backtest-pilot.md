# Value Engine / AI Picks — premier pilote de backtest

**Branche :** `agent/ml/value-backtest-pilot`  
**Modèle :** `football-elo-v1-candidate` — **non promu**  
**Value Engine :** `value-engine-0.1` — **formules non modifiées**  
**AI Picks :** `ai-picks-0.1` — ranking, seuils et exclusions **non modifiés**  
**Analyst :** `deterministic-v0.1` — LLM réel **OFF**  
**Provider cotes :** `the-odds-api-v4` (fixtures historical déjà commises ; aucun nouvel appel)  
**Verdict :** **GO WITH CONDITIONS**

Ce pilote construit un pipeline de backtest temporellement correct
(Prediction PIT → cotes PIT → Value Engine → AI Picks → résultat après T).
Il **ne** prouve **pas** que AI Picks est rentable.

Deux univers sont séparés volontairement :

1. **Fixture descriptive** (CI, reproductible) : 3 matchs matchés + cotes
   historical commises. Mesure le pipeline Value / AI Picks.
2. **Weekend live labellisé** (parquet local) : 17 matchs PL + Ligue 1 du
   21–24 août 2026. Mesure le **modèle** uniquement. Les 756 snapshots
   historical de ce weekend n'ont pas été persistés (`--dry-run`).

Il n'y a **pas** de train / calibration / out-of-sample. L'échantillon est
trop petit. Résultat présenté comme **descriptive pilot**.

---

## 1. Objectif

Répondre :

> Les signaux Value de PREDICTA apportent-ils un intérêt historique mesurable
> lorsque prediction ET odds respectent strictement le même cutoff temporel ?

Le pipeline doit être scientifique, reproductible et sans fuite. Il ne
cherche pas à maximiser le ROI.

---

## 2. Dataset

### 2.1 Déjà disponible (aucune API)

| Source | Statut | Usage |
| --- | --- | --- |
| Fixtures historical commises (`soccer_*_historical_pilot*.json`) | Git | Univers Value / AI Picks CI |
| Parquet `football-1x2-history-0.3` | local, gitignoré | 17 matchs labellisés + Elo PIT |
| Artefact `football-elo-v1-candidate` | local, gitignoré | Scoring modèle live |
| Rapport `docs/qa/historical-odds-pilot.md` | Git | 19 / 17 / 2 / 756, dry-run |
| Raw The Odds API du 11 sept. 2026 | local | Cotes **courantes**, hors fenêtre |

### 2.2 Manquant (non inventé, non retéléchargé)

Les 756 snapshots canonical du weekend 21–24 août 2026 n'ont **pas** été
écrits (pilote odds `--dry-run`). Sans ces cotes persistées, Value Engine et
AI Picks ne peuvent pas être scorés sur les 17 matchs réels.

Aucun nouveau backfill. Aucun appel The Odds API dans ce pilote.

### 2.3 Compteurs fixture (CI)

| Grandeur | n |
| --- | ---: |
| Matchs catalogue | 4 |
| Events odds uniques | 6 |
| Matchés | 3 |
| Rejetés | 3 |
| Snapshots 1X2 complets | 8 |
| Prédictions | 3 |
| AI Picks éligibles | 3 |
| Matchs sans cotes | 1 (Rennes/PSG, orientation canonique sans event matché) |

Rejets events : Unknown Borough (unmatched) ; Paris FC (isolé) ;
PSG/Rennes inversé.

---

## 3. Période

| Univers | Fenêtre | Rôle |
| --- | --- | --- |
| Fixture | 2026-08-16 | Pipeline Value / AI Picks |
| Live | 2026-08-21T00:00Z → 2026-08-25T00:00Z | Performance modèle, sans Value |

Pas de split TRAIN / OOS : fabriquer un faux out-of-sample sur n = 3 ou
n = 17 serait une validation cosmétique.

---

## 4. Compétitions

Uniquement Premier League et Ligue 1, comme le pilote historical odds.

La Liga, Bundesliga, Serie A, Champions League et MLS sont hors périmètre.

---

## 5. Cutoff policy

Pour chaque match de coup d'envoi T :

```
Prediction(T)          features_available_at, cutoff = T = kickoff
Odds PIT               available_at <= T   (OddsService live, value-engine-0.1)
Value Engine           formules 0.1
AI Picks               kickoff transmis comme cutoff canonique
Résultat réel          lu seulement au settlement, après T
```

Deux couches PIT, déjà documentées dans le pilote odds :

1. **Cotes** : `available_at <= cutoff` (API Value). `event_at` identifie le
   match ; il n'exclut pas les cotes pre-match du match cible.
2. **Features ML** : cutoff `pre_kickoff` égal au coup d'envoi. Un cutoff
   post-kickoff lève `TemporalLeakageError`. Le match cible n'entre pas dans
   Elo / forme / H2H (features parquet pré-calculées).

Aucune information post-T n'entre dans la prédiction, les cotes, le
bookmaker, le ranking ou les seuils.

---

## 6. Prediction

`football-elo-v1-candidate` exclusivement. K, home advantage, dataset,
schema, calibration, registry et code modèle **inchangés**.
`model_status=candidate`.

- Fixture CI : le service de prédiction porte la même version / le même
  statut candidate. Les probabilités stub rendent le settlement
  **bit-reproductible** sans artefact gitignoré.
- Weekend live : artefact réel chargé. Features parquet
  `home_elo_pre` / `away_elo_pre` / `elo_diff` au cutoff kickoff. Les labels
  `target` / scores ne sont pas lus par le feature store.

---

## 7. Odds

Uniquement `the-odds-api-v4`, marché `h2h` → `1X2`.

Fixture : 4 fichiers historical déjà dans Git. Mapping via
`map_the_odds_api_events` (même contrat live).

Weekend live : **0** snapshot persisté. Les cotes raw du 11 septembre
concernent des matchs au 12–14 septembre. Elles ne sont pas utilisées.

---

## 8. PIT

**PASS**

| Contrôle | Résultat |
| --- | --- |
| Snapshot `available_at` ≤ kickoff sélectionné | oui |
| Snapshot après kickoff exclu (Helix 14:55 vs T=14:00) | oui |
| Snapshot plus récent injecté après T | non sélectionné |
| Cutoff features > kickoff | `TemporalLeakageError` |
| Résultat futur modifié | prédiction / Value inchangés |

Marseille (kickoff 18:45) **peut** utiliser le snapshot 14:58 : il est
toujours pre-match. Helix / Bournemouth (kickoff 14:00) ne le peuvent pas.
Le cutoff du backtest est le **kickoff du match**, pas le T=14:00 du pilote
odds (test de snapshot).

---

## 9. Value Engine

**PASS** — parité live.

Formules **exclusives**, version `value-engine-0.1` :

```
implied_probability = 1 / odds
overround = Σ implied_probability
no_vig_probability = implied_probability / overround
edge = model_probability - implied_probability
EV = model_probability × odds - 1
```

Aucune autre formule métier. Tests : `value_parity_errors` vide.

---

## 10. AI Picks

Moteur `AiPicksEngine` existant. Pas de second ranking.

- Score : `opportunity_score = EV + Edge`
- Tri : score, EV, edge, fraîcheur, `match_id`, sélection
- Seuils V0.1 : `min_edge=0`, `min_ev=0`, `min_p=0`, `max_odds_age=24h`
- Une opportunité par `match/marché/sélection` si éligible

Exclusions comptabilisées (jamais silencieuses) :
`isolated_team`, `inverted_home_away`, `unmatched_odds_event`,
`odds_unavailable`, plus les raisons AI Picks.

---

## 11. Bookmaker policy

Règle déterministe **inchangée** :

> Last complete 1X2 snapshot with `available_at <= cutoff`, ordered by
> `(available_at, collected_at, snapshot.id)`. Bookmaker identity is not a
> selection criterion; Pinnacle is not preferred because it looks better.

Helix : Betfair Exchange (10:49) retenu, Pinnacle (10:48) écarté. Une table
descriptive par book existe et n'alimente **pas** la sélection.

---

## 12. Seuils

Seuils **exactement** ceux de `AiPicksThresholds` V0.1.

Aucune grille de 50 seuils. Aucune optimisation sur l'échantillon de
mesure.

---

## 13. Baselines

Même ensemble de matchs **avec cotes Value** pour la fixture (n = 3) :

| Stratégie | n | Hit rate | ROI théorique |
| --- | ---: | ---: | ---: |
| Naive HOME | 3 | 33.3 % | −39.3 % |
| Elo argmax, sans filtre Value | 3 | 100 % | +189 % |
| AI Picks Value | 3 | 100 % | +189 % |

Sur **cette** fixture, Elo argmax et AI Picks ont sélectionné les **mêmes**
trois issues. Le pilote ne distingue donc pas encore MODEL PERFORMANCE et
VALUE STRATEGY PERFORMANCE.

Weekend live (n = 17, **sans cotes**) :

| Stratégie | n | Hit rate |
| --- | ---: | ---: |
| Fréquence (prior PL+L1, n_prior = 1370, classe HOME) | 17 | 52.94 % |
| Naive HOME | 17 | 52.94 % |
| Elo argmax, sans Value | 17 | 52.94 % |
| AI Picks Value | 0 | indisponible |

Fréquence ajustée **uniquement** sur `event_at < 2026-08-21`. HOME est la
classe majoritaire a priori (43.9 %). Elo n'améliore pas always-HOME sur
ce weekend. n = 17 : échantillon insuffisant pour conclure.

---

## 14. Résultats

### Fixture (descriptive, n = 3 picks)

| Métrique | Valeur |
| --- | --- |
| Matchs évalués avec Value | 3 |
| Picks éligibles | 3 |
| HOME / DRAW / AWAY | 1 / 1 / 1 |
| Cote moyenne | 2.89 |
| Edge moyen | 0.0950 |
| EV moyen | 0.306 |
| Hit rate | 100 % (n = 3) |
| Profit théorique | +5.67 u |
| ROI théorique | +189 % |
| Drawdown max | 0 u / 0 % |

**échantillon insuffisant pour conclure.** Ces trois labels fixture sont
synthétiques. Ce n'est pas un résultat football réel.

### Weekend live (modèle, n = 17)

| Métrique | Valeur |
| --- | --- |
| Matchs fenêtre PL+L1 | 19 |
| Identité matchée (rapport odds) | 17 |
| Rejets identité | 2 |
| Prédictions candidate | 17 |
| AI Picks | 0 (cotes non persistées) |
| Hit rate Elo | 9/17 = 52.94 % |

---

## 15. ROI théorique

Présenté uniquement comme **rendement théorique du backtest**, jamais
comme gains garantis.

Hypothèses (moteur actuel, rien d'inventé) :

- mise fixe **1 unité** par opportunité AI Picks éligible ;
- une ligne par `match/sélection` éligible (pas de collapse « top 1 ») ;
- 1X2 : pas de push / refund ;
- pas de commission ;
- cote = snapshot last-complete au cutoff ;
- bookmaker non choisi a posteriori.

Si n < 30, le ROI n'est pas une preuve.

---

## 16. Drawdown

Fixture : equity monotone (3 wins), drawdown max = 0. Non informatif.

Live Value : non calculable (0 pick).

---

## 17. Anti-leakage

**PASS**

1. Résultat post-match modifié → prédiction inchangée.
2. Cote post-cutoff ajoutée (9.99) → snapshot sélectionné inchangé.
3. Outcome futur inversé → Value pre-match inchangée.
4. Snapshot plus récent après cutoff → non sélectionné.
5. Cutoff features après coup d'envoi → PIT refuse.
6. HOME/AWAY inversés (PSG/Rennes) → aucun matching.

---

## 18. Reproductibilité

**PASS**

Deux exécutions, même dataset, mêmes cutoffs, même modèle, mêmes cotes,
même horloge fixe `2026-08-16T19:00:00Z` :

- prédictions identiques ;
- books identiques ;
- AI Picks (match, sélection, rang) identiques ;
- ROI / hit rate identiques.

CLI : `python -m app.backtesting` depuis `apps/api` (0 crédit).

---

## 19. Limites

1. Cotes historical du weekend live non persistées (dry-run).
2. n = 3 (fixture) et n = 17 (modèle) : pas de preuve de rentabilité.
3. Fixture : labels de catalogue = supports de CI, pas des résultats
   Sportmonks présentés comme réels.
4. Sur la fixture, Value et Elo argmax coïncident.
5. Age max 24 h d'AI Picks : un snapshot J−5 serait `stale_odds`.
6. Pas de split OOS honnête.
7. 1X2 uniquement.
8. Analyst déterministe seulement.

---

## 20. HIGH / MEDIUM / LOW

### HIGH (0)

Pas de fuite temporelle, pas de faux match 1X2, pas de divergence Value,
pas de promotion du candidat, pas de secret, pas d'appel API.

### MEDIUM (4)

- **M-01** — Snapshots live du 16 août non persistés. Value/AI Picks
  impossibles sur les 17 matchs réels.
- **M-02** — n fixture = 3 ; n live = 17. Échantillon insuffisant.
- **M-03** — Elo live = always-HOME (52.94 %). Aucun signal Value mesurable.
- **M-04** — Fixture : AI Picks et Elo argmax = mêmes sélections.

### LOW (3)

- **L-01** — Last-complete peut retenir un book autre que Pinnacle (Helix /
  Betfair).
- **L-02** — `maximum_odds_age=24h` vs snapshots J−5 du pilote odds.
- **L-03** — Cold start Elo 1500 hors de ce scoring fixture.

---

## 21. Verdict

Quality gates locales (`.venv` de chaque package ; `python` n'est pas
sur le PATH système). CI live-off. OpenAPI inchangé. Aucun secret.
Aucune promotion.

| Commande | Résultat |
| --- | --- |
| `verify:api` | ruff + mypy + **577 passed** |
| `verify:ingestion` | ruff + mypy + **151 passed** |
| `verify:ml` | ruff + mypy + **29 passed** |
| `verify:web` | openapi + typecheck + lint + **283 passed** + build |
| `verify:all` | **PASS** (les quatre gates ci-dessus) |

| Gate | Résultat |
| --- | --- |
| PIT | **PASS** |
| Anti-leakage | **PASS** |
| Reproducibility | **PASS** |
| Value parity | **PASS** |
| AI Picks moteur | inchangé |
| Analyst `deterministic-v0.1` | **PASS** |
| Crédits API supplémentaires | **0** |

**GO WITH CONDITIONS**

Le pipeline de backtest est fiable : cutoff unique, matching exact +
alias + rejets isolés/inversés, Value 0.1, AI Picks 0.1, settlement
théorique documenté. **GO ne signifie pas « AI Picks rentable ».**

Conditions :

1. `football-elo-v1-candidate` reste candidate.
2. Value Engine et AI Picks inchangés.
3. Ne pas présenter n = 3 ou n = 17 comme une preuve de ROI.
4. Persister un run historical **borné** (pas un backfill 5 minutes) avant
   de scorer Value sur les 17 matchs.
5. CI live-off ; 0 appel The Odds API.

**NO-GO évité** : pas de fuite, pas de matching inversé, pas de formule
Value divergente, reproductibilité bit-à-bit sur la fixture.

---

## Crédits The Odds API

| Poste | Valeur |
| --- | ---: |
| historical data already available | fixtures Git + 756 observés au pilote odds (non persistés) |
| new API calls | **0** |
| new credits | **0** |
