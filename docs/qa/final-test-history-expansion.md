# Final Test Historical Expansion

**Branche :** `agent/data/expand-final-test-history`  
**Nature :** collecte + scoring. Aucun modèle, seuil, ranking, bookmaker, snapshot ou règle PIT n'a été modifié.  
**Fenêtres figées avant scoring :** `docs/qa/final-test-windows.json` (`final-test-windows-v1`)  
**CLI persist :** `python -m predicta_ingestion expand-final-test-history` (**sans** `--dry-run`)  
**CLI scoring :** `python -m app.backtesting persisted-final-test-history` (0 crédit)  
**Artefacts gitignorés (`var/`) :** `workers/ingestion/var/expand-final-test-history.json`, `workers/ingestion/var/persisted-final-test-history-score.json`  
**Modèle :** `football-elo-v1-candidate` — non promu  
**Value Engine :** `value-engine-0.1`  
**AI Picks :** `ai-picks-0.1`  
**Verdict dataset :** **GO WITH CONDITIONS**

**Performance descriptive sur l'échantillon étudié ; insuffisante pour conclure à une rentabilité future.**

Cette branche n'optimise pas le ROI. Elle construit un univers historique défini **avant** le scoring, pour mesurer la stabilité d'AI Picks 0.1 sur plusieurs fenêtres d'évaluation indépendantes.

---

## 1. Executive Summary

L'échantillon officiel `final_test` août–septembre 2026 (53 matchs / 68 AI Picks, ROI **−10,2 %**) est trop petit pour distinguer une fluctuation d'un signal. Cette branche ajoute **324** matchs PL + Ligue 1 terminés sur trois fenêtres 2024-25, dont **308** identity-matched avec cotes PIT 1X2, et **459** AI Picks.

Les dates ont été gelées dans `final-test-windows.json` **avant** tout scoring. Aucune fenêtre n'a été choisie, gardée ou écartée selon son ROI.

| Contrôle | Résultat |
| --- | --- |
| Fenêtres additionnelles | `final_test_window_01` 2024-08-16→10-01 ; `02` 10-01→12-01 ; `03` 12-01→2025-01-01 |
| Partition Elo honnête | `final_train` — **pas** un OOS Elo |
| Fenêtre officielle existante | `final_test_window_existing` 2026-08-21→09-07, **0 fetch** |
| Ligues | Premier League + Ligue 1 uniquement |
| Requêtes historical this run | **95** (cap 120 ; pas de grille 5 minutes) |
| Crédits `x-requests-last` | **950** prévus / **950** consommés |
| Δ `x-requests-used` | **940** (740 → 1680 ; remaining 19260 → 18320) |
| `--dry-run` | **false** |
| Matchs SQL additionnels | **324** (PL 188 / L1 136) |
| Avec cotes PIT 1X2 | **308** / 324 |
| AI Picks additionnels | **459** / 324 matchs |
| PIT / anti-leakage / Value parity / AI Picks parity / reproductibilité | **PASS** |
| `stale_odds` | **0** (âge max PIT ≈ 7,59 h < 24 h) |
| Candidat promu | **non** |

Table principale — AI Picks, 1 unité par pick, fenêtres **indépendantes** :

| Fenêtre | Matchs | Picks | Hit rate | ROI | Drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| `final_test_window_01` | 114 | 158 | 17,1 % | **−33,5 %** | 52,94 u |
| `final_test_window_02` | 124 | 168 | 22,0 % | **+3,3 %** | 18,92 u |
| `final_test_window_03` | 86 | 133 | 25,6 % | **+6,4 %** | 12,57 u |
| Ensemble additionnel (descriptif) | 324 | 459 | 21,4 % | **−8,5 %** | 67,66 u |
| Officiel existant (`final_test` Elo) | 53 | 68 | 20,6 % | **−10,2 %** | 15,00 u |

Le comportement n'est **pas** stable d'une fenêtre à l'autre. La fenêtre 01 est fortement négative ; 02 et 03 sont modestement positives. L'officiel août–septembre 2026 reste à −10,2 %. L'agrégat additionnel (−8,5 %) ne doit pas être lu comme une validation, ni comme une réfutation définitive.

Aucun seuil modifié. Aucun HOME/AWAY flip. Aucun match créé depuis les cotes. Aucun alias Reims ajouté. Mai 2026 / calibration / walk-forward **non requalifiés**.

---

## 2. Objective

Tester si le ROI AI Picks `final_test` actuel ≈ **−10,2 %** est :

- une fluctuation d'échantillon,
- dépendant d'une période,
- dépendant d'une ligue,
- ou potentiellement structurel.

Ce n'est **pas** la question « quel est le ROI global ? ».

Cible : **300–500** matchs additionnels propres, minimum acceptable ~250. Univers comparable au pilote : football, Premier League + Ligue 1, marché `h2h` → `1X2`, région `eu`.

Cette branche **ne décide pas** entre : poursuivre la collecte, revoir Elo, revoir Value, lancer un vrai backtest OOS, ou conclure que le signal n'est pas robuste. Elle produit les données et les mesures.

---

## 3. Existing Dataset

Référence : `docs/qa/expanded-value-ai-picks-analysis.md` et `docs/qa/expanded-historical-odds-value-ai-picks-pilot.md`.

| Univers | Partition Elo | Matchs | Picks | ROI AI Picks |
| --- | --- | ---: | ---: | ---: |
| Mai 2026 | `calibration_select` | 66 | 93 | **+21,9 %** |
| Août–septembre 2026 | `final_test` | 53 | 68 | **−10,2 %** |
| Agrégat | mélange | 119 | 161 | **+8,3 %** |

Le +8,3 % agrégé est porté par mai. Ce n'est **pas** une validation. PIT, anti-leakage, parités et reproductibilité du pilote élargi : **PASS**. Aucune anomalie moteur identifiée. Elo reste candidate.

Constantes Elo **non modifiées** : `FINAL_TRAIN_END=2026-01-01`, `CALIBRATION_FIT_END=2026-05-01`, `FINAL_TEST_START=2026-07-01`.

L'Elo `final_test` officiel (≥ 2026-07-01) ne peut pas fournir 300 matchs PL+L1 terminés supplémentaires : la saison 2026-27 vient de commencer. Les fenêtres additionnelles sont donc des **évaluations de stratégie gelée** sur `final_train`, pas un OOS du modèle.

---

## 4. New Final-Test Windows

Trois fenêtres additionnelles + une fenêtre de réutilisation. Définies dans le code (`FINAL_TEST_WINDOWS`) et dans `docs/qa/final-test-windows.json` **avant** ingestion live et avant scoring.

| `window_id` | Bornes UTC | Fetch | Additionnel | Partition Elo | SQL (PL / L1) | League-days |
| --- | --- | --- | --- | --- | ---: | ---: |
| `final_test_window_01` | 2024-08-16 → 2024-10-01 | oui | oui | `final_train` | 114 (60 / 54) | 33 |
| `final_test_window_02` | 2024-10-01 → 2024-12-01 | oui | oui | `final_train` | 124 (66 / 58) | 38 |
| `final_test_window_03` | 2024-12-01 → 2025-01-01 | oui | oui | `final_train` | 86 (62 / 24) | 24 |
| `final_test_window_existing` | 2026-08-21 → 2026-09-07 | **non** | non | `final_test` | 57 (30 / 27) | 21 |

Cible additionnelle à la définition : **324** matchs terminés. Obtenu SQL : **324**. Scorés avec cotes : **308**.

Chevauchements : **aucun** entre fenêtres additionnelles (`[start, end)`). Aucun chevauchement avec mai 2026 ni avec l'officiel août–septembre 2026. `window_03` s'arrête exactement à `FINAL_TRAIN_END` (exclus).

---

## 5. Window Definition

Critères objectifs, documentés dans l'artefact (`defined_before_scoring=true`, `defined_at=2026-09-11T17:30:00Z`) :

1. disponibilité Sportmonks PL + Ligue 1 en PostgreSQL (premier bloc 2024-25) ;
2. couverture historical The Odds API depuis 2020-06-06 ;
3. volume de matchs terminés avec résultat ;
4. journées consécutives, pas une concaténation opportuniste de tout l'historique ;
5. distance aux périodes de calibration / sélection de modèle ;
6. réutilisation des snapshots déjà persistés pour l'officiel 2026.

**Non-critères :** ROI, hit rate, bookmaker, snapshot « proche qui marche mieux ».

Périodes **exclues** à dessein (non requalifiées en `final_test`) :

| Période | Bornes UTC | Raison |
| --- | --- | --- |
| `fold_1_validation` | 2025-01-01 → 2025-07-01 | validation walk-forward (K / HA) |
| `fold_2_validation` (dont ouverture 2025-26) | 2025-07-01 → 2026-01-01 | validation walk-forward, analogue calendaire de l'officiel |
| `calibration_fit` | 2026-01-01 → 2026-05-01 | calibration Elo |
| `calibration_select` mai 2026 | 2026-05-01 → 2026-07-01 | déjà scoré ; +21,9 % ne doit pas être recyclé |
| reste officiel non terminé | 2026-09-07 → 2026-09-12 | 0 match PL+L1 terminé supplémentaire au freeze |

Cadence : **1 snapshot historical par ligue et par jour de coup d'envoi**. `as_of` = premier kickoff du jour, afin que le provider renvoie le snapshot le plus proche **≤** kickoff. Pas de grille 5 minutes.

---

## 6. API Budget

Estimation **avant** le live run, cap dur `MAX_FINAL_TEST_REQUESTS=120` (1200 crédits documentés). Reliquat provider largement supérieur. `stop_reason=null`. Fenêtre officielle **non refetchée**.

| Poste | Valeur |
| --- | ---: |
| Matchs SQL union | 381 (324 fetch + 57 reuse) |
| League-days à fetch | 95 (49 PL + 46 L1) |
| Crédits documentés / requête | 10 |
| Crédits prévus | **950** |
| Cap | 120 requêtes / 1200 crédits |
| Skip déjà persistés (fetch windows) | 0 |
| `--estimate-only` préalable | oui |

Le coût 950 crédits est inférieur au cap. Pas d'arrêt anticipé. Pas de backfill massif.

---

## 7. API Requests

Live run : `dry_run=false`, `estimate_only=false`, 95 requêtes, marché `h2h`, région `eu`, 1X2 uniquement.

| Poste | Valeur |
| --- | ---: |
| Requêtes planifiées | 95 |
| Requêtes exécutées | 95 |
| Ligues | 46 Ligue 1 + 49 Premier League |
| Crédits prévus (`x-requests-last`) | **950** |
| Crédits `sum(x-requests-last)` | **950** |
| `x-requests-used` première réponse | 740 (`remaining` 19260) |
| `x-requests-used` dernière réponse | 1680 (`remaining` 18320) |
| Δ `used` / `remaining` | **940** |
| Backfill 5 minutes | **0** |
| Nouvelles compétitions | **0** |
| Events envelope / requête | 6–25 (somme enveloppes 1696) |
| Snapshots `available_at` > `as_of` | **0** |

Le runner facture ce run à **950** via `x-requests-last` (toujours 10). Les compteurs cumulés `used`/`remaining` ont bougé de **940**. Écart **documenté**, pas masqué — même classe que le pilote élargi (Δ used ≠ sum last). Causes possibles : autre consommateur de la même clé, retries non reflétés dans `last`, ou comptabilité provider. Le cap 120 n'a pas été dépassé.

Raw payload ids this run : 95 enveloppes immuables `raw_the-odds-api-odds-*` (liste dans le JSON gitignoré).

---

## 8. Match Universe

Défini **avant** le scoring, à partir de Sportmonks déjà en base. Les cotes ne créent jamais de matchs.

| Grandeur | n |
| --- | ---: |
| Matchs SQL additionnels (fenêtres 01–03) | **324** |
| Premier League / Ligue 1 | 188 / 136 |
| Parquet labellisé (terminé + résultat) | 324 |
| Identity-matched (event Odds → Sportmonks) | 308 events / 308 matchs |
| SQL sans cote persistée | **16** |
| Prédictions Elo | 324 |
| AI Picks éligibles additionnels | **459** |
| Issues 1X2 évaluées (analytical) | 324 × 3 = 972 |
| `negative_ev` | 465 |
| `invalid_odds` (16 matchs × 3) | 48 |
| Compte fermé | 459 + 465 + 48 = 972 |
| Fenêtre officielle reuse SQL / scorés / picks | 57 / 53 / 68 |

Issues réelles additionnelles (324) : HOME 140, DRAW 84, AWAY 100.

Les 16 matchs sans cote restent dans l'univers SQL. Ils ne sont pas fabriqués, ni forcés, ni aliasés.

---

## 9. Identity Matching

Règle inchangée : event The Odds API → match Sportmonks **existant** → match canonique. Clé naturelle exacte, puis aliases **déjà validés**. Ambigu : REJECT / quarantine. Pas de fuzzy, pas de guess, pas de flip HOME/AWAY, pas de création de match.

This run (events in-window) :

| Grandeur | n |
| --- | ---: |
| Events in-window | 330 |
| Exact matches | **308** |
| Alias matches | 0 |
| False matches | **0** |
| Rejected events | **22** |
| Match rate | 93,3 % |
| Quarantine `unmatched_odds_event` | 1547 (répétitions book-level) |

Rejets (22 events) :

1. **15 × `Stade de Reims` vs Sportmonks `Reims`** — variante de nom sans alias existant. **Aucun alias ajouté** (règles de matching non modifiées sur cette branche). Ce sont les 15 matchs Ligue 1 sans cote.
2. **Ipswich Town vs Everton** — Odds `2024-10-19T14:00:00Z` vs Sportmonks `14:15:00Z`. Mismatch de kickoff → REJECT. 1 match PL sans cote (`mth_football-sportmonks-19134515`).
3. **6 events enveloppe** (Lyon–Monaco, quatre 15:00 du 15 sept., Everton–Liverpool 12:30) — kickoff Odds ≠ Sportmonks. Les matchs SQL correspondants ont été matched via **un autre** event à l'horaire exact. Pas de trou SQL supplémentaire.

Isolations **conservées** : Paris / Paris FC / PSG (`tm_football-sportmonks-4508`) ; exclusion Rennes/PSG `mth_football-sportmonks-19715631` sur la fenêtre officielle. Fenêtre existante : 4 identity rejected (ledger Paris / Rennes-PSG), 53 scorés — identique au pilote.

Aucun flip. Aucun match créé depuis les cotes.

---

## 10. Persisted Odds

Append-only, idempotent. Provenance complète : raw payload, canonical odds, snapshots, selections, `ingestion_run_id`, `collected_at`, `available_at`, `data_mode=live`, `raw_payload_id`.

| Poste | Valeur |
| --- | ---: |
| Raw payloads this run | 95 |
| Records accepted this run | **23396** snapshots |
| Duplicates this run | 0 |
| Scoring `loaded_snapshots` (PG, toutes fenêtres) | 27279 |
| dont fenêtre existante | 3816 |
| Bookmakers observés (région `eu`) | 19 |
| Marché | `h2h` → `1X2` HOME / DRAW / AWAY uniquement |
| Bookmaker de sélection PIT | **non choisi pour le ROI** |

Politique snapshot Value inchangée : dernier 1X2 complet avec `available_at ≤ cutoff`, ordre `(available_at, collected_at, snapshot.id)`. Pinnacle n'est pas préféré.

Une ré-exécution identique ne refetch pas ces league-days (ids déjà persistés). Le scoring se rejoue à 0 crédit.

---

## 11. PIT

Cutoff = kickoff. Informations utilisables : `available_at < cutoff_at` (odds : `available_at ≤ kickoff` via OddsService / value-engine-0.1) et `event_at < cutoff_at` pour les features ML.

| Contrôle | Résultat |
| --- | --- |
| Politique PIT | **inchangée** |
| `maximum_odds_age` | **24 h, inchangé** |
| Snapshot post-cutoff | rejeté |
| Snapshot futur | rejeté |
| `as_of` vs `snapshot_timestamp` | tous ≤ `as_of` |
| Âge PIT des picks additionnels | min 0,07 h / moy. 1,77 h / max **7,59 h** |
| `stale_odds` | **0** |
| Horloge de scoring | `2026-09-07T00:00:00Z` (tous les matchs scorés sont antérieurs et terminés) |

Le snapshot n'est **pas** choisi rétroactivement pour maximiser le ROI.

---

## 12. Anti-Leakage

Tests renforcés (`apps/api/tests/test_final_test_history_scoring.py`, `workers/ingestion/tests/test_final_test_history.py`) :

- `available_at` du snapshot retenu ≤ kickoff ;
- snapshot post-cutoff rejeté ;
- snapshot futur rejeté ;
- PIT déterministe (même fingerprint sur double eval) ;
- pas de résultat futur dans les features ;
- fenêtres pré-déclarées = artefact versionné ;
- `elo_temporal_split=final_train` sur les fenêtres additionnelles ;
- Paris isolé hors scoring ;
- `optimized_on_test=false`.

Live scoring : PIT **PASS** sur chaque fenêtre et sur l'agrégat.

---

## 13. Prediction

Uniquement `football-elo-v1-candidate`. Pas de ré-entraînement, pas de nouveau K, pas de nouvelle home advantage, pas de recalibration, pas de comparaison de modèles, **pas de promotion**.

Horloge `2026-09-07T00:00:00Z`. Features PIT du dataset `football-1x2-history-0.3`. Les 16 matchs sans cote ont malgré tout une prédiction Elo (le modèle ne dépend pas des cotes).

---

## 14. Value Engine

`value-engine-0.1`, formules inchangées :

```text
implied = 1 / odds
overround = Σ implied
no_vig = implied / overround
edge = model_probability − implied
EV = model_probability × odds − 1
profit = (odds − 1) si hit sinon −1    # mise 1 u
ROI = Σ profit / n
```

Parité Value **PASS** sur chaque fenêtre. Aucune autre implémentation. Aucun recaclul parallèle.

Value settled = 1 sélection par match identity-matched **avec cotes** (typiquement l'argmax Elo au marché). Ce n'est **pas** AI Picks.

---

## 15. AI Picks

`ai-picks-0.1`, seuils inchangés :

| Seuil | Valeur |
| --- | --- |
| `minimum_edge` | 0 |
| `minimum_ev` | 0 |
| `minimum_model_probability` | 0 |
| `maximum_odds_age` | 24 h |
| Ranking / tie-breakers | inchangés |
| `optimized_on_test` | **false** |

Parité AI Picks **PASS**. Ranking **indépendant par fenêtre** (pas un rerank global 2024-08 + 2024-12). Stake : **1 unité par pick / opportunité**, pas 1 unité par match.

---

## 16. Window-by-Window Results

AI Picks, fenêtres indépendantes. Aucune fenêtre défavorable n'est masquée.

| Fenêtre | Matchs | Picks | Hits | Hit rate | Profit | ROI | Drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `final_test_window_01` (ouverture 2024-25) | 114 | 158 | 27 | 17,1 % | −52,94 u | **−33,5 %** | 52,94 u (33,5 % stake) |
| `final_test_window_02` (automne) | 124 | 168 | 37 | 22,0 % | +5,46 u | **+3,3 %** | 18,92 u (11,3 % stake) |
| `final_test_window_03` (décembre) | 86 | 133 | 34 | 25,6 % | +8,47 u | **+6,4 %** | 12,57 u (9,5 % stake) |
| Ensemble additionnel | 324 | 459 | 98 | 21,4 % | −39,01 u | **−8,5 %** | 67,66 u (14,7 % stake) |
| `final_test_window_existing` (officiel) | 53 | 68 | 14 | 20,6 % | −6,93 u | **−10,2 %** | 15,00 u (22,1 % stake) |

`matches_with_odds` : 108 / 116 / 84 / 53. Les 16 trous (15 Reims + Ipswich–Everton) réduisent surtout la Ligue 1 des fenêtres 01–03.

Variance inter-fenêtres : ROI de **−33,5 %** à **+6,4 %**. Ce n'est pas un bloc homogène. L'ensemble −8,5 % est tiré par la fenêtre 01.

**Performance descriptive sur l'échantillon étudié ; insuffisante pour conclure à une rentabilité future.**

---

## 17. Model Performance

Argmax Elo sur les 324 matchs identity-matched additionnels (y compris 16 sans cote). **Ce n'est pas un ROI.**

| Univers | n | Accuracy | Log loss | Brier | ECE | Argmax H / D / A |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Window 01 | 114 | 40,4 % | 1,075 | 0,650 | 0,042 | 114 / 0 / 0 |
| Window 02 | 124 | 48,4 % | 1,040 | 0,626 | 0,070 | 120 / 0 / 4 |
| Window 03 | 86 | 46,5 % | 1,034 | 0,621 | 0,123 | 76 / 0 / 10 |
| Ensemble additionnel | **324** | **45,1 %** | **1,051** | **0,633** | **0,025** | **310 / 0 / 14** |
| Officiel existant | 53 | 43,4 % | 1,044 | 0,627 | 0,074 | 43 / 0 / 10 |

Par ligue, ensemble additionnel : Premier League 188, accuracy 43,6 %, log loss 1,059 ; Ligue 1 136, accuracy 47,1 %, log loss 1,039.

Matrice de confusion additionnelle (lignes = vrai, colonnes = prédit HOME / DRAW / AWAY) :

```text
HOME  138   0   2
DRAW   80   0   4
AWAY   92   0   8
```

Elo **ne prédit jamais DRAW** sur cet échantillon. Accuracy ~45 % est cohérente avec un modèle 1X2 à trois classes, pas avec un edge.

Par ligue et fenêtre (accuracy) :

| Fenêtre | PL n | PL acc. | L1 n | L1 acc. |
| --- | ---: | ---: | ---: | ---: |
| 01 | 60 | 35,0 % | 54 | 46,3 % |
| 02 | 66 | 51,5 % | 58 | 44,8 % |
| 03 | 62 | 43,5 % | 24 | 54,2 % |
| Officiel | 30 | 43,3 % | 23 | 43,5 % |

---

## 18. Value Performance

Settled 1X2 du favori modèle, 1 unité par match **avec cotes**. Distinct d'AI Picks.

| Fenêtre | n | Hit rate | Profit | ROI | Edge moy. | EV moy. | Odds moy. | Drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | 108 | 41,7 % | −21,68 u | **−20,1 %** | −4,0 % | +0,114 | 2,59 | 24,18 u |
| 02 | 116 | 49,1 % | +7,60 u | **+6,6 %** | −4,8 % | +0,066 | 2,49 | 13,47 u |
| 03 | 84 | 47,6 % | −7,59 u | **−9,0 %** | −6,3 % | +0,049 | 2,45 | 17,70 u |
| Ensemble add. | 308 | 46,1 % | −21,67 u | **−7,0 %** | — | — | — | — |
| Officiel | 53 | 43,4 % | −11,09 u | **−20,9 %** | −6,2 % | −0,067 | 2,08 | 13,75 u |

Value n'est pas AI Picks : cotes courtes (~2,5 vs ~5,2), presque uniquement HOME, edge moyen **négatif** (overround). Un EV moyen positif avec edge négatif sur l'argmax est le compte overround / settlement du favori — ce n'est pas un signal de tuning.

---

## 19. AI Picks Performance

| Fenêtre | n | Hits | Hit rate | Profit | ROI | Edge moy. | EV moy. | Odds moy. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | 158 | 27 | 17,1 % | −52,94 u | **−33,5 %** | 8,8 % | 0,591 | 5,18 |
| 02 | 168 | 37 | 22,0 % | +5,46 u | **+3,3 %** | 7,9 % | 0,486 | 5,10 |
| 03 | 133 | 34 | 25,6 % | +8,47 u | **+6,4 %** | 7,9 % | 0,511 | 5,30 |
| Ensemble add. | **459** | **98** | **21,4 %** | **−39,01 u** | **−8,5 %** | **8,2 %** | **0,529** | **5,19** |
| Officiel | 68 | 14 | 20,6 % | −6,93 u | **−10,2 %** | 5,9 % | 0,316 | 4,74 |

Cote moyenne additionnelle **5,19** : la stratégie continue de sélectionner des issues longues (DRAW / AWAY / outsiders), pas l'argmax Elo.

L'ensemble −8,5 % (n = 459) est du même ordre de grandeur que l'officiel −10,2 % (n = 68), **mais** la décomposition par fenêtre montre une variance élevée. Ce n'est pas une preuve de stationnarité.

**Performance descriptive sur l'échantillon étudié ; insuffisante pour conclure à une rentabilité future.**

---

## 20. Premier League vs Ligue 1

AI Picks, par fenêtre. Petits sous-échantillons : ne pas surinterpréter.

| Fenêtre | PL picks | PL hit | PL ROI | L1 picks | L1 hit | L1 ROI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | 97 | 15,5 % | **−35,7 %** | 61 | 19,7 % | **−30,0 %** |
| 02 | 99 | 22,2 % | **+2,7 %** | 69 | 21,7 % | **+4,0 %** |
| 03 | 100 | 28,0 % | **+20,2 %** | 33 | 18,2 % | **−35,5 %** |
| Ensemble add. | **296** | **22,0 %** | **−4,0 %** | **163** | **20,2 %** | **−16,7 %** |
| Officiel | 38 | 21,1 % | −15,5 % | 30 | 20,0 % | −3,5 % |

Ligue 1 additionnelle est plus négative (−16,7 %) que la Premier League (−4,0 %), et privée de 15 matchs Reims. Ce n'est pas une conclusion structurelle ligue ; c'est une observation d'échantillon, concentré sur 2024-25, avec un trou d'identité Reims.

---

## 21. HOME / DRAW / AWAY

AI Picks, ensemble additionnel (459) :

| Sélection | n | Hits | Hit rate | Profit | ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| HOME | 140 | 41 | 29,3 % | −4,16 u | −3,0 % |
| DRAW | 175 | 37 | 21,1 % | −4,52 u | −2,6 % |
| AWAY | 144 | 20 | 13,9 % | **−30,33 u** | **−21,1 %** |

Par fenêtre (ROI) :

| Fenêtre | HOME n / ROI | DRAW n / ROI | AWAY n / ROI |
| --- | --- | --- | --- |
| 01 | 50 / −28,5 % | 58 / −13,2 % | 50 / **−62,1 %** |
| 02 | 50 / +20,2 % | 62 / −20,1 % | 56 / +14,0 % |
| 03 | 40 / −0,1 % | 55 / +28,4 % | 38 / −18,7 % |
| Officiel | 25 / −24,0 % | 20 / −33,3 % | 23 / +24,9 % |

AWAY de la fenêtre 01 (−62,1 %, n = 50) pèse lourdement sur l'agrégat. L'AWAY officiel était **positif** (+24,9 %, n = 23). Même sélection, signes opposés : dépendance à la période, pas une constante de marché.

---

## 22. Odds Distribution

Descriptif uniquement. **Ne pas** en déduire un nouveau seuil.

Ensemble additionnel :

| Bin | n | Hits | Hit rate | ROI |
| --- | ---: | ---: | ---: | ---: |
| <2 | 0 | — | — | — |
| 2–3 | 51 | 21 | 41,2 % | +7,2 % |
| 3–5 | 242 | 54 | 22,3 % | −13,3 % |
| 5–10 | 142 | 20 | 14,1 % | −14,1 % |
| >10 | 24 | 3 | 12,5 % | +39,6 % |

Le bin >10 (n = 24) a un ROI positif porté par **3 hits**. Ce n'est pas un signal actionnable. Le cœur de l'échantillon (3–10, n = 384) est négatif. Toujours **zéro** pick <2 — la stratégie EV≥0 évite les favoris courts, comme sur le pilote.

Fenêtre 01, bin 5–10 : ROI **−78,0 %** (2 hits / 48). Fenêtre 02, même bin : **+16,3 %**. Encore la variance.

Officiel : <2 n = 1 (non interprétable) ; 2–3 n = 12 ROI −39,0 % ; 3–5 n = 33 ROI −11,5 % ; 5–10 n = 20 ROI +14,3 % ; >10 n = 2 ROI −100 %.

---

## 23. Edge / EV Distribution

Descriptif. **Ne pas** chercher le « meilleur » seuil.

Edge, ensemble additionnel :

| Edge | n | Hit rate | ROI |
| --- | ---: | ---: | ---: |
| <5 % | 175 | 24,6 % | −11,0 % |
| 5–10 % | 122 | 25,4 % | +5,7 % |
| 10–20 % | 135 | 15,6 % | −14,4 % |
| 20–30 % | 27 | 11,1 % | −26,7 % |
| >30 % | 0 | — | — |

EV :

| EV | n | Hit rate | ROI |
| --- | ---: | ---: | ---: |
| 0–0,15 | 152 | 26,3 % | −9,1 % |
| 0,15–0,40 | 120 | 24,2 % | −8,2 % |
| 0,40–1,00 | 119 | 19,3 % | −0,5 % |
| ≥1,00 | 68 | 8,8 % | −21,6 % |

Le bucket EV ≥ 1,00 reste le plus mauvais hit rate (8,8 %) — même pattern que le pilote (longues cotes, EV élevé, hits rares). Aucune tranche n'est utilisée pour retuner.

---

## 24. Multiple Picks

Convention AI Picks 0.1 : **1 unité par opportunité**. Un match à 2 picks contribue 2 au dénominateur du ROI.

| | 0 pick | 1 pick | 2 picks | 3 picks | Eligible | Picks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Window 01 | 13 | 44 | 57 | 0 | 114 | 158 |
| Window 02 | 18 | 44 | 62 | 0 | 124 | 168 |
| Window 03 | 6 | 27 | 53 | 0 | 86 | 133 |
| Ensemble add. | **37** | **115** | **172** | **0** | **324** | **459** |
| Officiel | 4 | 30 | 19 | 0 | 53 | 68 |

Les 37 « 0 pick » additionnels incluent les 16 matchs `invalid_odds`. Jamais 3 picks (plafond mécanique inchangé). 172 matchs à 2 picks : le ROI n'est pas un ROI « par match ».

---

## 25. P&L

Chronologique par `(kickoff_at, match_id, selection)`. Aucun look-ahead. 1 u par pick.

| Univers | n | Profit | Equity finale |
| --- | ---: | ---: | ---: |
| Window 01 | 158 | −52,94 u | −52,94 u |
| Window 02 | 168 | +5,46 u | +5,46 u (fenêtre seule) |
| Window 03 | 133 | +8,47 u | +8,47 u (fenêtre seule) |
| Concaténation 01→02→03 | 459 | **−39,01 u** | **−39,01 u** |
| Officiel | 68 | −6,93 u | −6,93 u |

La concaténation additionnelle n'est **pas** un ranking global. Chaque pick a été éligibilisé dans sa fenêtre. L'equity d'ensemble commence à la fenêtre 01 (gros drawdown) puis récupère partiellement en automne / décembre, sans revenir à zéro.

---

## 26. Drawdown

Max drawdown sur la courbe d'equity chronologique, en unités et en fraction du stake de la fenêtre.

| Fenêtre | Max DD | DD / stake |
| --- | ---: | ---: |
| 01 | **52,94 u** | 33,5 % |
| 02 | 18,92 u | 11,3 % |
| 03 | 12,57 u | 9,5 % |
| Ensemble add. | **67,66 u** | 14,7 % |
| Officiel | 15,00 u | 22,1 % |

La fenêtre 01 ne se remet jamais : DD = perte finale. L'ensemble 67,66 u > 52,94 u : le drawdown concaténé traverse aussi une partie des fenêtres 02/03.

---

## 27. Reproducibility

Après ingestion :

1. scoring depuis PostgreSQL + parquet, **0 appel** The Odds API ;
2. double `_evaluate_persisted` in-process par fenêtre ;
3. fingerprints (prédictions, cotes, Value, AI Picks, métriques) identiques.

| Gate | Résultat |
| --- | --- |
| Reproductibilité par fenêtre | **PASS** |
| Reproductibilité agrégée | **PASS** |
| Value parity | **PASS** |
| AI Picks parity | **PASS** |
| Versions | `football-elo-v1-candidate` / `value-engine-0.1` / `ai-picks-0.1` / dataset `football-1x2-history-0.3` |
| `data_mode` | `live` |
| Dataset analytical | 1143 lignes (381 matchs × 3 issues) persistables sans API |

Les fenêtres sont reconstructibles : artefact JSON + `FINAL_TEST_WINDOWS` + `elo_temporal_split()`. Un autre agent peut relire **pourquoi ces dates** sans observer le ROI.

---

## 28. Limitations

1. Les 324 matchs additionnels sont en partition Elo **`final_train`**. Ce n'est pas un OOS du modèle. C'est une évaluation de la **stratégie Value / AI Picks gelée** sur un historique réel.
2. Une seule saison (ouverture → 31 déc. 2024-25). Pas de 2022-23 / 2023-24 : Sportmonks en base commence à ce bloc pour PL+L1.
3. 16 matchs sans cote (15 Reims naming, 1 kickoff Ipswich). Matching non élargi volontairement.
4. Ligue 1 fenêtre 03 : 24 matchs SQL, 33 picks — petit sous-échantillon.
5. 1 snapshot / ligue / jour, pas une grille intra-day. Suffisant pour `stale_odds=0`, pas une reconstruction du mouvement de cotes.
6. Δ `used` 940 vs `last` 950 : comptabilité provider, pas une preuve d'idempotence quota.
7. Bookmakers région `eu` hétérogènes ; le book PIT n'est pas un « closing line » unique.
8. n = 459 picks n'est pas i.i.d. (multi-picks, mêmes matchs, longues cotes). Pas d'intervalle ROI robuste ici.
9. Horloge de scoring 2026-09-07 : légitime pour des matchs 2024 déjà clos ; ne simule pas un runtime contemporain 2024.
10. Cette branche n'inclut pas La Liga / Bundesliga / Serie A / C1 / MLS, par design.

---

## 29. Findings

1. **Le dataset additionnel est utilisable** : 308 matchs propres avec cotes, 459 picks, PIT/parités/repro PASS, univers pré-déclaré.
2. **AI Picks n'est pas stable** sur les trois fenêtres : −33,5 % / +3,3 % / +6,4 %.
3. L'agrégat additionnel **−8,5 %** est du même ordre que l'officiel **−10,2 %**, mais il est **dominé par la fenêtre 01**. Ce n'est pas une preuve que −10 % est la loi des grands nombres.
4. Le +8,3 % global du pilote élargi **n'apparaît pas** sur ces fenêtres d'évaluation, ni sur l'officiel.
5. Variance par ligue et par sélection (AWAY 01 à −62 % vs AWAY officiel à +25 %). Dépendance à la période, aux longues cotes, et à AWAY.
6. Elo argmax ~45 % accuracy, jamais DRAW : inchangé dans l'esprit du candidat. Value settled additionnel **−7,0 %**. AI Picks et Value restent deux univers.
7. Le pattern EV élevé / hit rate bas se reproduit. Ce n'est pas une invitation à tuner.
8. Aucune anomalie moteur : identité stricte, pas de leakage, pas de score fabriqué.
9. 308 ≥ 250 (minimum) et ≈ 300 (cible basse). 16 matchs manquants sont un trou d'identité, pas un arrêt budget.
10. Cette branche **ne dit pas** si le signal est structurel. Elle dit que la stabilité inter-fenêtres est **faible** et que le −10,2 % officiel **n'était pas un artefact isolé d'août 2026**, sans pour autant être une constante.

---

## 30. Verdict

Le verdict porte sur la **qualité et l'utilité du dataset**, pas sur la rentabilité.

| Gate | Résultat |
| --- | --- |
| ~250–500 matchs additionnels propres | **PASS** (324 SQL / 308 avec cotes / 459 picks) |
| Plusieurs fenêtres temporelles indépendantes | **PASS** (3 + 1 reuse) |
| Fenêtres définies avant scoring | **PASS** |
| PL + Ligue 1 uniquement | **PASS** |
| Matchs terminés, scores réels | **PASS** |
| Odds historical persistées, provenance | **PASS** |
| Identité stricte, pas de match inventé, pas de flip | **PASS** |
| Pas de requalification calibration / walk-forward | **PASS** |
| PIT | **PASS** |
| Anti-leakage | **PASS** |
| Value parity | **PASS** |
| AI Picks parity | **PASS** |
| Reproductibilité (0 API au replay) | **PASS** |
| Modèle / seuils / PIT / matching inchangés | **PASS** |
| Pas d'optimisation de ROI | **PASS** |
| Budget estimé puis respecté | **PASS** (95 / 120, 950 crédits) |
| Secrets absents du git | **PASS** |
| `stale_odds` artificiel | **évité** |
| Honnêteté `temporal_split=final_train` | **PASS** (condition) |

**GO WITH CONDITIONS**

GO ne signifie pas « AI Picks rentable ». Même les fenêtres 02 et 03 à ROI positif restent :

**Performance descriptive sur l'échantillon étudié ; insuffisante pour conclure à une rentabilité future.**

Conditions :

1. `football-elo-v1-candidate` reste candidate — pas de promotion.
2. Value 0.1 et AI Picks 0.1 restent inchangés (pas de tuning, pas de meilleure tranche, pas de meilleur snapshot).
3. Ne pas présenter 308 / 459 comme un OOS Elo, ni comme une preuve de ROI futur.
4. Séparer les fenêtres. Ne pas remplacer −10,2 % par −8,5 % « donc c'est confirmé », ni par +6,4 % « donc ça marche en décembre ».
5. Conservé : Reims non aliasé ; Paris isolé ; Rennes/PSG hors univers officiel ; Ipswich kickoff rejeté.
6. Documenter `x-requests-last` (950) et Δ `used` (940) sans les confondre.
7. La prochaine décision (collecte / Elo / Value / vrai OOS / signal insuffisant) n'est **pas** prise ici.

**NO-GO évité** : persistance réelle, PIT, anti-leakage, parité, pas de flip, pas de secret, pas de promotion, cible ≥250 atteinte sans backfill 5 minutes, fenêtres pré-déclarées.

Quality gates locales (`.venv` de chaque package). CI live-off. OpenAPI inchangé. Aucun secret. Aucune promotion. `verify:all` = concaténation des quatre gates Python/web ; toutes **PASS**.

| Commande | Résultat |
| --- | --- |
| `verify:ingestion` | ruff + mypy + **177 passed**, 1 skipped |
| `verify:api` | ruff + mypy + **592 passed** |
| `verify:ml` | ruff + mypy + **29 passed** |
| `verify:web` / `verify:openapi` | openapi + typecheck + lint + **283 passed** + build |
| `verify:all` | **PASS** (les quatre gates ci-dessus via `.venv`) |

---

## 31. Recommendation

Pour le prochain agent, les faits utiles sont :

- un univers reconstructible (`final-test-windows-v1`) ;
- 308 + 53 matchs scorables sans nouvel appel API ;
- une table de stabilité qui **n'est pas plate** ;
- un trou d'identité Reims documenté, non contourné ;
- des quality gates à relancer sur cette branche.

Ne pas, sur la base de ce rapport :

- promouvoir Elo ;
- retuner `minimum_edge` / `minimum_ev` / `maximum_odds_age` ;
- jeter la fenêtre 01 ;
- aliaser Reims « pour gagner 15 matchs de ROI » ;
- concaténer mai (+21,9 %) avec ces fenêtres pour republier un +8 %.

La décision A–E (poursuivre la collecte, revoir Elo, revoir Value, vrai backtest OOS, ou constater un signal insuffisamment robuste) reste **ouverte**. Ce dataset est fait pour la prendre, pas pour la court-circuiter.
