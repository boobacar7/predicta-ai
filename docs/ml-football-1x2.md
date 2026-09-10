# Football 1X2 — premier pipeline ML

Benchmark figé. Aucun branchement backend, aucune prédiction live, aucune cote,
aucun Value/EV. Dataset exclusivement `football-1x2-history-0.3`.

Worker : `workers/ml` (`predicta_ml`).
Modèle enregistré au benchmark : `football-1x2-model-0.1` = **Elo + calibration sigmoid**.
Candidat scientifique (non production) : `football-elo-v1-candidate` —
voir [validation](ml/elo-candidate-validation.md) et
[model card](ml/model-card-football-elo.md).
Seed : **42**. Code : `0.1.0+e8b76d7`.
Parquet SHA-256 : `0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5`.

La sélection utilise le walk-forward (log-loss) et une fenêtre de calibration.
Le test final `2026-07-01` → `2026-09-10` n'a pas servi à choisir le modèle.

---

## 1. Audit du dataset

| Champ | Valeur réelle |
| --- | --- |
| Dataset | `football-1x2-history-0.3` |
| Feature schema | `football-1x2-features-0.3` |
| Lignes | 5729 |
| Features | 27 |
| Cible | `target` ∈ {HOME, DRAW, AWAY} |
| Doublons `match_id` | 0 |
| Nulls (features + identité) | 0 |
| Ordre chronologique | oui |
| `data_mode` | `live` uniquement |
| Cutoff | `pre_kickoff` |
| Période | 2024-02-22 01:00 UTC → 2026-09-10 02:30 UTC |
| Compétitions | 7 (MLS 1419, La Liga 801, Premier League 790, Serie A 790, CL 662, Ligue 1 637, Bundesliga 630) |
| Saisons | 2024, 2024/2025, 2025, 2025/2026, 2026, 2026/2027 |
| 1/X/2 | 2546 / 1389 / 1794 (44.4% / 24.2% / 31.3%) |
| Elo disponible | 5729/5729 (`elo_available` constant = 1) |
| Standings | absents (conforme 0.3) |
| Odds / scores du match cible | absents |

### Écarts par rapport à la spécification 0.3

Le schéma des **27 features** est identique à `docs/ml-dataset.md`. Écarts d'emballage, pas de contenu :

- `event_at` est stocké en **string ISO-8601** dans le parquet, pas en timestamp Arrow. Le loader le parse en UTC.
- Les cold-starts ne sont pas des JSON `null` : fenêtres vides = `0` + flag `*_available=0`.
- `elo_available` n'apporte aucune variance ; il reste dans le schéma mais n'est **utilisé par aucun estimateur**.
- Les colonnes d'identité (`match_id`, équipes, compétition, saison, provider, `dataset_version`, …) et la cible ne font pas partie des 27 features. Elles servent au split, au reporting et aux gardes anti-leakage.

Le dataset Data n'a pas été modifié.

### Catalogue des 27 features

Toutes sont Point-in-Time (`event_at < T` et `available_at < T` côté Data). Source : parquet 0.3 reconstruit par `predicta_ingestion.ml` depuis PostgreSQL Sportmonks.

| Feature | Type parquet | Source | Null | Utilisée par |
| --- | --- | --- | --- | --- |
| `home_elo_pre` | float64 | snapshot Elo global au kickoff | 0 | Elo, XGB, LGBM |
| `away_elo_pre` | float64 | snapshot Elo global au kickoff | 0 | Elo, XGB, LGBM |
| `elo_diff` | float64 | `home_elo_pre - away_elo_pre` (sans +80 HA) | 0 | Elo, XGB, LGBM |
| `elo_available` | int64 | 1 si les deux Elo existent | 0 | **aucune** (constante) |
| `home_form_5` / `away_form_5` | int64 | points 3/1/0, fenêtre 5 | 0 | XGB, LGBM |
| `home_form_10` / `away_form_10` | int64 | points, fenêtre 10 | 0 | XGB, LGBM |
| `home_form_5_available` / `away_form_5_available` | int64 | ≥ 5 matchs PIT | 0 | Poisson, XGB, LGBM |
| `home_form_10_available` / `away_form_10_available` | int64 | ≥ 10 matchs PIT | 0 | XGB, LGBM |
| `home_goals_for_5` / `home_goals_against_5` | int64 | buts rolling home | 0 | Poisson, XGB, LGBM |
| `away_goals_for_5` / `away_goals_against_5` | int64 | buts rolling away | 0 | Poisson, XGB, LGBM |
| `home_goals_for_10` / `home_goals_against_10` | int64 | buts rolling 10 | 0 | XGB, LGBM |
| `away_goals_for_10` / `away_goals_against_10` | int64 | buts rolling 10 | 0 | XGB, LGBM |
| `h2h_home_wins` / `h2h_draws` / `h2h_away_wins` | int64 | H2H PIT | 0 | XGB, LGBM |
| `h2h_available` | int64 | 1 si ≥ 2 H2H (2168/5729) | 0 | XGB, LGBM |
| `h2h_matches` | int64 | nombre de H2H PIT | 0 | XGB, LGBM |
| `home_matches_played` / `away_matches_played` | int64 | volume PIT toutes compétitions | 0 | XGB, LGBM |

Fréquence historique : **aucune feature** (priors du train uniquement).

Distributions notables : Elo home mean 1513.13 [1332.08, 1793.02] ; `h2h_available` = 37.8% ; form_5 disponible ~90% ; form_10 ~82%.

---

## 2. Split temporel

Protocol : expanding walk-forward + test final jamais vu. **Aucun split aléatoire.**
Bornes exclusives, UTC. Juin 2026 : 0 matchs terminés dans 0.3 (trou réel).

| Fenêtre | Start (inclus) | End (exclus) | Lignes |
| --- | --- | --- | --- |
| Fold 1 train | 2024-02-22 | 2025-01-01 | 1538 |
| Fold 1 val | 2025-01-01 | 2025-07-01 | 1305 |
| Fold 2 train | 2024-02-22 | 2025-07-01 | 2843 |
| Fold 2 val | 2025-07-01 | 2026-01-01 | 1251 |
| Fold 3 train | 2024-02-22 | 2026-01-01 | 4094 |
| Fold 3 val | 2026-01-01 | 2026-07-01 | 1248 |
| Final train | 2024-02-22 | 2026-01-01 | 4094 |
| Calibration fit | 2026-01-01 | 2026-05-01 | 985 |
| Calibration select | 2026-05-01 | 2026-07-01 | 263 |
| **Test final** | **2026-07-01** | **2026-09-10 02:30:01** | **387** |

Règle : `max(event_at train) < min(event_at val) < min(event_at test)`.
Les labels de test n'entrent ni dans le fit, ni dans la calibration, ni dans le choix d'ensemble.

---

## 3. Baselines

1. **Fréquence 1X2** : proportions HOME/DRAW/AWAY du train, constantes sur la fenêtre future.
2. **Elo** : `P(home expected) = 1 / (1 + 10^(-(elo_diff + 80)/400))` avec HA=+80 et scale=400 du dataset 0.3. Masse nulle (draw) : `clip(base * exp(-decay * |elo_diff| / 400))`, `base`/`decay` ajustés **sur le train uniquement** (L-BFGS-B). Fit final : `draw_base=0.2774`, `draw_decay=1.1096`.
3. **Poisson** : λ home/away depuis les taux de buts fenêtre 5 (fallback = moyenne train si `*_available=0`). Multiplicateur d'avantage domicile en grille sur le log-loss 1X2 du train. Pas de scores du match cible (ils ne sont pas dans 0.3).

Walk-forward (moyenne des 3 folds, probabilités **brutes**) :

| Modèle | Log-loss | Brier | Accuracy | ECE |
| --- | ---: | ---: | ---: | ---: |
| **elo** | **1.0179** | **0.6080** | **0.5056** | 0.0291 |
| poisson | 1.0505 | 0.6327 | 0.4730 | 0.0473 |
| xgboost | 1.0598 | 0.6314 | 0.4820 | 0.0662 |
| frequency | 1.0685 | 0.6464 | 0.4422 | **0.0176** |
| lightgbm | 1.0778 | 0.6402 | 0.4735 | 0.0875 |

Détail des folds (log-loss) :

| Fold | frequency | elo | poisson | xgboost | lightgbm |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 (n=1305) | 1.0745 | **1.0274** | 1.0479 | 1.0836 | 1.1131 |
| 2 (n=1251) | 1.0601 | **1.0017** | 1.0464 | 1.0376 | 1.0474 |
| 3 (n=1248) | 1.0710 | **1.0245** | 1.0572 | 1.0582 | 1.0730 |

---

## 4. ML (XGBoost / LightGBM)

Features : les 26 colonnes du schéma **sauf** `elo_available`.
Pas de recherche massive d'hyperparamètres. Seed 42, `n_jobs=1`.

XGBoost : 200 arbres, depth 4, lr 0.05, subsample 0.8, colsample 0.8, min_child_weight 5, `tree_method=hist`.

LightGBM : 200 arbres, `num_leaves=16`, depth 4, lr 0.05, subsample 0.8, colsample 0.8, `deterministic=True`, `force_row_wise=True`.

Les boosting **ne battent pas Elo** en walk-forward. LightGBM est sous la fréquence en log-loss moyen (overfit fold 1 : 1.113). Échantillon ~2.5 saisons, H2H sparse, pas d'xG ni de cotes : résultat attendu, pas un bug d'évaluation.

---

## 5. Calibration

Comparaison sur `calibration_select` (263 matchs, **pas le test**). Fit des calibrateurs sur `calibration_fit` (985 matchs).

Méthodes : brut, Platt/sigmoid OvR + renormalisation simplex, isotonic OvR si n≥200 et ≥30 par classe (éligible ici).

| Modèle | raw ll | sigmoid ll | isotonic ll | Choix |
| --- | ---: | ---: | ---: | --- |
| elo | 1.0589 | **1.0508** | 1.3101 | sigmoid |
| frequency | **1.0763** | 1.0766 | 1.0766 | raw |
| poisson | 1.1148 | **1.0825** | 1.1089 | sigmoid |
| xgboost | 1.1212 | **1.0598** | 1.1773 | sigmoid |
| lightgbm | 1.1282 | **1.0521** | 1.1861 | sigmoid |

L'isotonic **dégrade** fortement Elo/XGB/LGBM sur cette taille de fenêtre. Sigmoid aide les boosting (réduction de log-loss et d'ECE vs brut).

Le calibrateur **final** du modèle enregistré est refit sur l'union `calibration_fit ∪ calibration_select` (toujours avant le test).

---

## 6. Ensemble

Candidats (hors fréquence) : elo, lightgbm, xgboost, poisson. Moyenne pondérée par l'inverse du log-loss de `calibration_select`.

| | Log-loss | Brier | Accuracy | ECE |
| --- | ---: | ---: | ---: | ---: |
| Elo sigmoid (meilleur simple) | **1.0508** | **0.6323** | 0.4905 | **0.0379** |
| Ensemble pondéré | 1.0538 | 0.6348 | 0.4791 | 0.0523 |

L'ensemble **n'améliore pas** le log-loss hors échantillon. Conservé : **Elo seul**.

---

## 7. Test final (n=387, jamais utilisé pour la sélection)

| Modèle | Calibrage | Log-loss | Brier | Accuracy | ECE |
| --- | --- | ---: | ---: | ---: | ---: |
| **elo (enregistré)** | sigmoid | **1.0280** | **0.6159** | 0.4832 | 0.0629 |
| xgboost | sigmoid | 1.0382 | 0.6229 | 0.4884 | 0.0356 |
| lightgbm | sigmoid | 1.0385 | 0.6229 | **0.5013** | 0.0380 |
| poisson | sigmoid | 1.0481 | 0.6312 | 0.4625 | 0.0261 |
| frequency | raw | 1.0671 | 0.6445 | 0.4574 | **0.0133** |

LightGBM a une meilleure accuracy test. Ce n'est **pas** un critère de promotion (AGENTS.md / architecture : log-loss, Brier, calibration). Le walk-forward et le log-loss test favorisent Elo. Aucun hyperparamètre n'a été retouché après lecture du test.

### Confusion Elo calibré (lignes = vrai HOME / DRAW / AWAY)

|  | pred HOME | pred DRAW | pred AWAY |
| --- | ---: | ---: | ---: |
| HOME (177) | 158 | 0 | 19 |
| DRAW (99) | 84 | 0 | 15 |
| AWAY (111) | 82 | 0 | 29 |

Argmax : 324 HOME, 0 DRAW, 63 AWAY. L'Elo 1X2 **n'élit jamais le nul** : P(DRAW) max reste sous P(HOME) à cause du +80 HA. Les probabilités de nul restent utiles (log-loss / Brier) ; l'accuracy 1X2 sous-estime ce modèle.

### Performance 1 / X / 2 (Elo test)

| Issue | Support | Recall | Precision | P moyenne | Brier classe | Log-loss OvR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| HOME | 177 | 0.893 | 0.488 | 0.462 | 0.233 | 0.658 |
| DRAW | 99 | 0.000 | 0.000 | 0.262 | 0.189 | 0.564 |
| AWAY | 111 | 0.261 | 0.460 | 0.333 | 0.194 | 0.575 |

### Par compétition (Elo test)

| Compétition | n | Log-loss | Brier | Accuracy | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| serie-a | 30 | 0.902 | 0.526 | 0.633 | 0.169 |
| bundesliga | 18 | 0.955 | 0.567 | 0.444 | 0.257 |
| la-liga | 41 | 0.995 | 0.592 | 0.463 | 0.161 |
| champions-league | 102 | 1.010 | 0.604 | 0.559 | 0.118 |
| premier-league | 30 | 1.013 | 0.605 | 0.433 | 0.166 |
| mls | 139 | 1.077 | 0.650 | 0.432 | 0.036 |
| ligue-1 | 27 | 1.100 | 0.666 | 0.407 | 0.049 |

n faibles hors MLS/CL : les ECE par ligue sont bruyants.

### Par saison (Elo test)

| Saison | n | Log-loss | Brier | Accuracy | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026 (MLS) | 139 | 1.077 | 0.650 | 0.432 | 0.036 |
| 2026/2027 | 248 | 1.001 | 0.597 | 0.512 | 0.088 |

### Calibration (confiance = max p, 10 bins, Elo test)

Bins non vides : 0.3–0.4 (n=55, acc 0.255 vs conf 0.385), 0.4–0.5 (n=249, 0.466 vs 0.440), 0.5–0.6 (n=66, 0.636 vs 0.540), 0.6–0.7 (n=17, 0.882 vs 0.621). ECE globale 0.063.

---

## 8. Robustesse

| Contrôle | Résultat |
| --- | --- |
| Leakage temporel train/val/test | 0 overlap, ordre strict |
| Feature future (`*_post`, `future_*`) | aucune |
| Cible dans les features | refusée |
| Doublons | 0 |
| Nulls | 0 |
| Dataset ≠ 0.3 | refus au load |
| `data_mode=mock` | refus au load |
| Split aléatoire | non implémenté |
| Seed | 42, documentée |
| `n_jobs` boosting | 1 |
| Reload artefact → mêmes P test | `allclose` 1e-12 |

---

## 9. Model registry

Artefacts gitignorés : `workers/ml/var/registry/football-1x2-model-0.1/`
(`registry.json` + `artefact.joblib`).

| Champ | Valeur |
| --- | --- |
| `model_version` | `football-1x2-model-0.1` |
| `dataset_version` | `football-1x2-history-0.3` |
| `feature_schema_version` | `football-1x2-features-0.3` |
| `training_period` | 2024-02-22 → 2026-01-01 (4094) |
| `validation_period` | calib fit 2026-01-01→2026-05-01 ; calib select 2026-05-01→2026-07-01 |
| `test_period` | 2026-07-01 → 2026-09-10 02:30:01 (387) |
| `features` | `home_elo_pre`, `away_elo_pre`, `elo_diff` |
| `hyperparameters` | HA=80, scale=400, draw_base=0.2774, draw_decay=1.1096 |
| `calibration_method` | sigmoid (Platt OvR + renormalize) |
| `random_seed` | 42 |
| `code_version` | `0.1.0+e8b76d7` |
| `selected_model` | `elo` |
| `ensemble_used` | false |

Résumé commit-able : `workers/ml/reports/football-1x2-model-0.1.summary.json`.

Non fait (volontaire, STOP après benchmark) :

- pas d'API / pas de table `predictions`
- pas d'inférence live
- pas d'odds, pas d'edge, pas d'EV

---

## Reproduction

```bash
cd workers/ml
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m ruff check src tests && python -m mypy && python -m pytest
python -m predicta_ml audit --dataset ../ingestion/var/football-1x2-history.parquet
python -m predicta_ml benchmark --dataset ../ingestion/var/football-1x2-history.parquet
python -m predicta_ml validate-elo --dataset ../ingestion/var/football-1x2-history.parquet
```

Depuis la racine : `npm run verify:ml`.
