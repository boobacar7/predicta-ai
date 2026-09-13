# Validation scientifique — candidat Elo Football 1X2

**Statut : candidate. Pas production. Pas de promotion backend.**

Commande :

```bash
cd workers/ml
python -m predicta_ml validate-elo \
  --dataset ../ingestion/var/football-1x2-history.parquet
```

Artefact local (gitignoré) : `workers/ml/var/registry/football-elo-v1-candidate/`
(`registry.json` + `artefact.joblib` rechargeable).
Cartes versionnées (git) :
`workers/ml/reports/football-elo-v1-candidate.registry.json` et
`workers/ml/reports/football-elo-v1-candidate.summary.json`.
Model card : [model-card-football-elo.md](model-card-football-elo.md).

Aucun boosting supplémentaire, aucune donnée externe, aucune cote, aucun Value Engine.

---

## 1. Sensibilité K × home advantage

Reconstruction causale des ratings à partir des labels 1X2 du dataset 0.3
(snapshot `event_at`, update `event_at + 3h`). Accord avec `elo_diff` figé à
K=20 / HA=80 : **MAE = 0**.

Même folds temporels que le benchmark. Draw transform refit sur le train de
chaque fold. Grille de robustesse, **pas** une recherche d'hyperparamètres :
K=20 HA=80 reste le candidat même si une autre cellule est un peu meilleure.

Walk-forward mean log-loss :

| K \ HA | 0 | 40 | 60 | 80 | 100 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 1.0395 | 1.0302 | 1.0292 | 1.0306 | 1.0343 |
| 15 | 1.0320 | 1.0225 | 1.0214 | 1.0227 | 1.0262 |
| 20 | 1.0276 | 1.0180 | 1.0168 | **1.0179** | 1.0213 |
| 25 | 1.0250 | 1.0152 | 1.0139 | 1.0150 | 1.0182 |
| 30 | 1.0236 | 1.0137 | 1.0123 | 1.0132 | 1.0164 |

- Min 1.0123 (K=30, HA=60) — **non promu**.
- Max 1.0395 (K=10, HA=0).
- Amplitude 0.027. Le candidat est **9e / 25**, à +0.0056 du minimum.
- HA=0 est systématiquement plus mauvais que HA ∈ {40,60,80}.
- Conclusion : le signal Elo est stable ; K=20 / +80 n'est pas un pic isolé.

Accuracy / Brier / ECE du candidat (K=20, HA=80) : 50.56% / 0.6080 / 0.0291,
identiques au benchmark (même `elo_diff` dataset).

---

## 2. Nul (Draw)

P(Draw) n'est **jamais** supprimée. Sur le test raw et la validation walk-forward :
`draw_never_removed = true`, 3 colonnes, min P(Draw) > 0.

| Fenêtre | n | argmax Draw | max P(Draw) | mean P(Draw) | Draw réel | ECE classe Draw |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Walk-forward val | 3804 | **0** | 0.279 | ~0.23 | 24.1% | 0.023 |
| Test raw | 387 | **0** | 0.277 | 0.235 | 25.6% | 0.021 |

Distributions test raw :

| | min | p10 | p50 | p90 | max | mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P(Home) | 0.198 | 0.360 | 0.442 | 0.591 | 0.826 | 0.464 |
| P(Draw) | 0.105 | 0.179 | 0.246 | 0.272 | 0.277 | 0.235 |
| P(Away) | 0.069 | 0.203 | 0.283 | 0.438 | 0.680 | 0.301 |

À elo_diff = 0 : expected home score = 0.613 à cause du +80. Avec draw_base=0.277,
P(Home) ≈ 0.443 > P(Draw) = 0.277. P(Draw) ne dépasse **jamais** P(Home)
(0 ligne). Donc l'argmax ne peut pas être Draw. Ce n'est pas un bug de
pipeline : c'est la géométrie HA + transform. Les nuls restent scorés dans
le log-loss.

Calibration Draw (test) : presque toute la masse est dans [0.1, 0.3]. Bin
0.1–0.2 (n=68) : prévu 0.171 vs observé 0.176. Bin 0.2–0.3 (n=319) : 0.249 vs
0.273. Légère sous-estimation du nul, pas un crash.

---

## 3. Performance par compétition

Walk-forward validation poolée (n=3804) :

| Compétition | n | Log-loss | Brier | Accuracy | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Premier League | 572 | 1.032 | 0.617 | 50.0% | 0.021 |
| Ligue 1 | 474 | 0.994 | 0.593 | 52.7% | 0.026 |
| La Liga | 579 | 0.988 | 0.587 | 52.0% | 0.036 |
| Bundesliga | 477 | 1.032 | 0.616 | 48.6% | 0.027 |
| Serie A | 582 | 1.023 | 0.611 | 50.5% | 0.034 |
| Champions League | 362 | **0.981** | **0.585** | **53.3%** | 0.046 |
| MLS | 758 | 1.050 | 0.631 | 48.3% | 0.017 |

Aucune ligue ne s'effondre vs la fréquence (seuil +0.02 log-loss). MLS est la
plus faible mais reste meilleure que la fréquence (1.050 vs 1.064).

Test raw (n=387, slices petites hors MLS/CL) :

| Compétition | n | Log-loss | Brier | Accuracy | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Premier League | 30 | 0.998 | 0.596 | 43.3% | 0.144 |
| Ligue 1 | 27 | **1.121** | 0.678 | 40.7% | 0.131 |
| La Liga | 41 | 0.966 | 0.574 | 48.8% | 0.108 |
| Bundesliga | 18 | 0.940 | 0.553 | 44.4% | 0.242 |
| Serie A | 30 | **0.872** | **0.506** | **63.3%** | 0.202 |
| Champions League | 102 | 0.999 | 0.596 | 55.9% | 0.099 |
| MLS | 139 | 1.089 | 0.657 | 43.9% | 0.053 |

Ligue 1 test est le point faible (n=27). Bundesliga ECE élevé = bruit de
petit n (log-loss encore meilleur que la fréquence 1.009). MLS test ≈
fréquence (1.089 vs 1.089).

---

## 4. Performance par saison

Walk-forward val :

| Saison | n | Log-loss | Brier | Accuracy | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024/2025 | 1014 | 1.012 | 0.603 | 49.8% | 0.038 |
| 2025 | 540 | 1.058 | 0.636 | 47.0% | 0.023 |
| 2025/2026 | 2032 | **1.009** | **0.602** | **51.7%** | 0.016 |
| 2026 | 218 | 1.031 | 0.619 | 51.4% | 0.052 |

Test :

| Saison | n | Log-loss raw | Brier | Accuracy | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026 (MLS) | 139 | 1.089 | 0.657 | 43.9% | 0.053 |
| 2026/2027 | 248 | 0.987 | 0.587 | 51.6% | 0.059 |

La saison MLS 2025 (walk-forward) et le test MLS 2026 sont plus difficiles que
les saisons européennes 2025/2026–2026/2027. Pas d'effondrement brutal.

---

## 5. Calibration raw vs sigmoid

| Fenêtre | raw ll | sigmoid ll | raw ECE | sigmoid ECE |
| --- | ---: | ---: | ---: | ---: |
| calibration_select (n=263) | 1.0589 | **1.0508** | 0.049 | **0.038** |
| **test (n=387)** | **1.0238** | 1.0280 | **0.046** | 0.063 |

Sigmoid améliore la fenêtre de sélection, **pas** le test hors échantillon.
Brier et accuracy test favorisent aussi raw. Le candidat n'est pas retouché
avec le test ; l'artefact conserve sigmoid comme choix de protocole, et cette
divergence **interdit une promotion production**.

---

## 6. Stabilité fold par fold

| Fold | n | Elo ll | Fréquence ll | Brier | Acc | ECE | argmax Draw |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1305 | 1.0274 | 1.0745 | 0.614 | 48.4% | 0.030 | 0 |
| 2 | 1251 | **1.0017** | 1.0601 | 0.597 | 53.0% | 0.041 | 0 |
| 3 | 1248 | 1.0245 | 1.0710 | 0.613 | 50.2% | 0.017 | 0 |

Spread log-loss : 0.026. Pire fold = fold 1, toujours nettement au-dessus de
la fréquence. Collapse vs fréquence par compétition walk-forward : **aucun**.

Segments à surveiller (pas des collapses walk-forward) : MLS, test Ligue 1
(n faible), ECE Bundesliga test (n=18).

---

## 7–8. Model card et registry

- Model card : [model-card-football-elo.md](model-card-football-elo.md)
- `model_version` : `football-elo-v1-candidate`
- Reload test probabilities : OK (`allclose` 1e-12)
- `promoted_to_production` : **false**

Régénérer l'artefact joblib (non commité, dossier `var/`) :

```bash
python -m predicta_ml validate-elo --dataset ../ingestion/var/football-1x2-history.parquet
```
